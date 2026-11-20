import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
import logging
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import SessionLocal
from app.discovery.base import BaseDiscoveryAdapter
from app.discovery.models import (
    NormalizedDiscoveryEvent,
    SourceHealthSnapshot,
)
from app.identity.registry import TokenRegistry, is_valid_solana_address

logger = logging.getLogger("meco.discovery.engine")


class DiscoveryEngine:
    """
    Coordinates discovery adapters, validates and normalises incoming events,
    persists events and canonical token identities, handles deduplication,
    and publishes discovery notifications to downstream subscribers.
    """

    def __init__(self, session_factory=SessionLocal) -> None:
        self.session_factory = session_factory
        self.adapters: dict[str, BaseDiscoveryAdapter] = {}
        self._subscribers: list[
            Callable[[Any, NormalizedDiscoveryEvent, bool], Awaitable[None]]
        ] = []
        self._running = False

    def register_adapter(self, adapter: BaseDiscoveryAdapter) -> None:
        """Register a discovery adapter."""
        if adapter.source_name in self.adapters:
            raise ValueError(f"Adapter '{adapter.source_name}' already registered")
        self.adapters[adapter.source_name] = adapter
        adapter.on_event(self.handle_source_event)
        logger.info("Registered discovery adapter: %s", adapter.source_name)

    def subscribe_token_discovered(
        self,
        callback: Callable[[Any, NormalizedDiscoveryEvent, bool], Awaitable[None]],
    ) -> None:
        """Register a subscriber callback for token discovery notifications."""
        self._subscribers.append(callback)

    async def start(self) -> None:
        """Start all registered discovery adapters."""
        if self._running:
            return
        self._running = True
        logger.info("Starting DiscoveryEngine with %s adapters...", len(self.adapters))
        for adapter in self.adapters.values():
            await adapter.start()

    async def stop(self) -> None:
        """Stop all registered discovery adapters."""
        self._running = False
        logger.info("Stopping DiscoveryEngine...")
        for adapter in self.adapters.values():
            await adapter.stop()

    async def handle_source_event(
        self,
        event: NormalizedDiscoveryEvent,
    ) -> None:
        """
        Process an incoming discovery event through the 10-step pipeline.
        Ensures provider isolation: any failure in processing does not crash
        the caller or other adapters.
        """
        start_time = time.perf_counter()
        source = event.source
        adapter = self.adapters.get(source)

        try:
            # Step 1 & 2: Validate structure
            if not event.mint_address or not event.source:
                logger.warning("Rejected malformed event (missing mint or source): %s", event)
                if adapter:
                    adapter.health.invalid_events += 1
                return

            # Step 3 & 4: Validate mint format
            clean_mint = event.mint_address.strip()
            if not is_valid_solana_address(clean_mint):
                logger.warning(
                    "Rejected event with invalid Solana mint format: %s from %s",
                    event.mint_address,
                    source,
                )
                if adapter:
                    adapter.health.invalid_events += 1
                return

            if adapter:
                adapter.health.valid_events += 1

            # Step 5 to 9: Persistence, canonical identity resolution & deduplication
            async with self.session_factory() as session:
                async with session.begin():
                    # Check if token already exists to determine is_new / duplicate
                    existing = await TokenRegistry.get_token_by_mint(session, clean_mint)
                    is_new = existing is None

                    # Resolve or create canonical token
                    token, created = await TokenRegistry.resolve_or_create_token(
                        session,
                        mint_address=clean_mint,
                        source=source,
                        discovered_at=event.received_at,
                        name=event.name,
                        symbol=event.symbol,
                        decimals=event.decimals,
                        total_supply=event.total_supply,
                        metadata_uri=event.metadata_uri,
                    )

                    # Persist raw event
                    db_event = await TokenRegistry.record_discovery_event(
                        session,
                        token_id=token.id,
                        mint_address=clean_mint,
                        source=source,
                        event_type=event.event_type,
                        source_event_id=event.source_event_id,
                        signature=event.signature,
                        slot=event.slot,
                        commitment=event.commitment,
                        source_timestamp=event.source_timestamp,
                        received_at=event.received_at,
                        raw_payload=event.raw_payload,
                        is_duplicate=not is_new,
                    )

                    # Associate source with token
                    await TokenRegistry.associate_token_source(
                        session,
                        token_id=token.id,
                        source=source,
                        seen_at=event.received_at,
                        source_metadata=event.source_metadata,
                    )

                    # Update checkpoint if signature or slot is provided
                    if event.signature or event.slot:
                        await TokenRegistry.update_checkpoint(
                            session,
                            source=source,
                            last_signature=event.signature,
                            last_slot=event.slot,
                            last_event_at=event.received_at,
                        )

            # Update in-memory adapter metrics
            proc_latency_ms = (time.perf_counter() - start_time) * 1000.0
            if adapter:
                adapter.health.last_processing_latency_ms = round(proc_latency_ms, 2)
                if is_new:
                    adapter.health.new_tokens_count += 1
                else:
                    adapter.health.duplicate_events += 1

            logger.info(
                "TOKEN DISCOVERED | mint=%s | source=%s | is_new=%s | latency=%.2fms",
                clean_mint,
                source,
                is_new,
                proc_latency_ms,
            )

            # Step 10: Dispatch to downstream subscribers
            for subscriber in self._subscribers:
                try:
                    await subscriber(token, event, is_new)
                except Exception as sub_err:
                    logger.exception(
                        "Error in discovery subscriber callback for mint %s: %s",
                        clean_mint,
                        sub_err,
                    )

        except Exception as exc:
            logger.exception(
                "Failed processing discovery event from %s for mint %s: %s",
                source,
                getattr(event, "mint_address", None),
                exc,
            )
            if adapter:
                adapter.health.processing_failures += 1

    def get_all_health(self) -> dict[str, SourceHealthSnapshot]:
        """Collect current health snapshot across all registered adapters."""
        return {
            name: adapter.get_health()
            for name, adapter in self.adapters.items()
        }
