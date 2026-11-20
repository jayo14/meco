import logging
from datetime import datetime, timezone
from typing import Any

from solders.pubkey import Pubkey
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    DiscoveryCheckpoint,
    DiscoveryEvent,
    StreamHealth,
    Token,
    TokenSource,
)

logger = logging.getLogger("meco.identity.registry")


def is_valid_solana_address(address: str | None) -> bool:
    """Validate that a string is a well-formed Solana Base58 public key."""
    if not address or not isinstance(address, str):
        return False
    address = address.strip()
    if len(address) < 32 or len(address) > 44:
        return False
    try:
        Pubkey.from_string(address)
        return True
    except ValueError:
        return False


class TokenRegistry:
    """
    Manages canonical token identities, discovery events, token sources,
    and ingestion stream health.
    """

    @staticmethod
    async def get_token_by_mint(
        session: AsyncSession,
        mint_address: str,
    ) -> Token | None:
        """Fetch canonical token by mint address."""
        stmt = select(Token).where(Token.mint_address == mint_address)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def resolve_or_create_token(
        session: AsyncSession,
        *,
        mint_address: str,
        source: str,
        discovered_at: datetime | None = None,
        name: str | None = None,
        symbol: str | None = None,
        decimals: int | None = None,
        total_supply: int | None = None,
        metadata_uri: str | None = None,
        verification_status: str = "unverified",
    ) -> tuple[Token, bool]:
        """
        Resolve existing canonical token or create a new one.
        Returns a tuple of (token, is_new).
        Guarantees that multiple concurrent discoveries of the same mint address
        safely resolve to a single canonical token record.
        """
        if not is_valid_solana_address(mint_address):
            raise ValueError(f"Invalid Solana mint address: {mint_address}")

        ts = discovered_at or datetime.now(timezone.utc)
        existing = await TokenRegistry.get_token_by_mint(session, mint_address)
        if existing is not None:
            # Update fields if newly available
            updated = False
            if name and not existing.name:
                existing.name = name
                updated = True
            if symbol and not existing.symbol:
                existing.symbol = symbol
                updated = True
            if decimals is not None and existing.decimals is None:
                existing.decimals = decimals
                updated = True
            if total_supply is not None and existing.total_supply is None:
                existing.total_supply = total_supply
                updated = True
            if metadata_uri and not existing.metadata_uri:
                existing.metadata_uri = metadata_uri
                updated = True
            if updated:
                existing.updated_at = datetime.now(timezone.utc)
                await session.flush()
            return existing, False

        new_token = Token(
            mint_address=mint_address,
            name=name,
            symbol=symbol,
            decimals=decimals,
            total_supply=total_supply,
            first_discovered_at=ts,
            first_discovery_source=source,
            verification_status=verification_status,
            metadata_uri=metadata_uri,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(new_token)

        try:
            await session.flush()
            await session.refresh(new_token)
            return new_token, True
        except IntegrityError:
            # Another concurrent transaction inserted the token
            await session.rollback()
            existing = await TokenRegistry.get_token_by_mint(session, mint_address)
            if existing is not None:
                return existing, False
            raise

    @staticmethod
    async def record_discovery_event(
        session: AsyncSession,
        *,
        mint_address: str,
        source: str,
        token_id: int | None = None,
        event_type: str = "token_created",
        source_event_id: str | None = None,
        signature: str | None = None,
        slot: int | None = None,
        commitment: str | None = None,
        source_timestamp: datetime | None = None,
        received_at: datetime | None = None,
        raw_payload: dict[str, Any] | None = None,
        is_duplicate: bool = False,
        error_message: str | None = None,
    ) -> DiscoveryEvent:
        """Persist a discovery event with raw payload and timings."""
        now = datetime.now(timezone.utc)
        rec_time = received_at or now

        event = DiscoveryEvent(
            token_id=token_id,
            mint_address=mint_address,
            source=source,
            event_type=event_type,
            source_event_id=source_event_id,
            signature=signature,
            slot=slot,
            commitment=commitment,
            source_timestamp=source_timestamp,
            received_at=rec_time,
            raw_payload=raw_payload,
            processed_at=now,
            is_duplicate=is_duplicate,
            error_message=error_message,
            created_at=now,
        )
        session.add(event)
        await session.flush()
        await session.refresh(event)
        return event

    @staticmethod
    async def associate_token_source(
        session: AsyncSession,
        *,
        token_id: int,
        source: str,
        seen_at: datetime | None = None,
        source_metadata: dict[str, Any] | None = None,
    ) -> TokenSource:
        """
        Associate a source with a canonical token. If the source has already
        observed this token, increment observation count and update last_seen_at.
        """
        now = seen_at or datetime.now(timezone.utc)
        stmt = select(TokenSource).where(
            TokenSource.token_id == token_id,
            TokenSource.source == source,
        )
        result = await session.execute(stmt)
        token_source = result.scalar_one_or_none()

        if token_source is not None:
            token_source.event_count += 1
            token_source.last_seen_at = now
            if source_metadata:
                merged = dict(token_source.source_metadata or {})
                merged.update(source_metadata)
                token_source.source_metadata = merged
            token_source.updated_at = datetime.now(timezone.utc)
        else:
            token_source = TokenSource(
                token_id=token_id,
                source=source,
                first_seen_at=now,
                last_seen_at=now,
                event_count=1,
                source_metadata=source_metadata,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(token_source)

        try:
            await session.flush()
            await session.refresh(token_source)
            return token_source
        except IntegrityError:
            await session.rollback()
            stmt = select(TokenSource).where(
                TokenSource.token_id == token_id,
                TokenSource.source == source,
            )
            result = await session.execute(stmt)
            token_source = result.scalar_one_or_none()
            if token_source is not None:
                token_source.event_count += 1
                token_source.last_seen_at = now
                await session.flush()
                return token_source
            raise

    @staticmethod
    async def upsert_stream_health(
        session: AsyncSession,
        *,
        source: str,
        status: str | None = None,
        last_connected_at: datetime | None = None,
        last_disconnected_at: datetime | None = None,
        last_event_at: datetime | None = None,
        last_error: str | None = None,
        reconnect_increment: int = 0,
        events_received_increment: int = 0,
        valid_events_increment: int = 0,
        invalid_events_increment: int = 0,
        duplicate_events_increment: int = 0,
        new_tokens_increment: int = 0,
        processing_failures_increment: int = 0,
        last_processing_latency_ms: float | None = None,
        last_source_latency_ms: float | None = None,
    ) -> StreamHealth:
        """Update stream health state and metrics for a discovery source."""
        stmt = select(StreamHealth).where(StreamHealth.source == source)
        result = await session.execute(stmt)
        health = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if health is None:
            health = StreamHealth(
                source=source,
                status=status or "disconnected",
                last_connected_at=last_connected_at,
                last_disconnected_at=last_disconnected_at,
                last_event_at=last_event_at,
                last_error=last_error,
                last_error_at=now if last_error else None,
                reconnect_count=reconnect_increment,
                events_received=events_received_increment,
                valid_events=valid_events_increment,
                invalid_events=invalid_events_increment,
                duplicate_events=duplicate_events_increment,
                new_tokens_count=new_tokens_increment,
                processing_failures=processing_failures_increment,
                last_processing_latency_ms=last_processing_latency_ms,
                last_source_latency_ms=last_source_latency_ms,
                updated_at=now,
            )
            session.add(health)
        else:
            if status is not None:
                health.status = status
            if last_connected_at is not None:
                health.last_connected_at = last_connected_at
            if last_disconnected_at is not None:
                health.last_disconnected_at = last_disconnected_at
            if last_event_at is not None:
                health.last_event_at = last_event_at
            if last_error is not None:
                health.last_error = last_error
                health.last_error_at = now
            health.reconnect_count += reconnect_increment
            health.events_received += events_received_increment
            health.valid_events += valid_events_increment
            health.invalid_events += invalid_events_increment
            health.duplicate_events += duplicate_events_increment
            health.new_tokens_count += new_tokens_increment
            health.processing_failures += processing_failures_increment
            if last_processing_latency_ms is not None:
                health.last_processing_latency_ms = last_processing_latency_ms
            if last_source_latency_ms is not None:
                health.last_source_latency_ms = last_source_latency_ms
            health.updated_at = now

        await session.flush()
        await session.refresh(health)
        return health

    @staticmethod
    async def get_stream_health(
        session: AsyncSession,
        source: str,
    ) -> StreamHealth | None:
        """Fetch stream health record for a given source."""
        stmt = select(StreamHealth).where(StreamHealth.source == source)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all_stream_health(
        session: AsyncSession,
    ) -> list[StreamHealth]:
        """Fetch stream health records for all sources."""
        stmt = select(StreamHealth).order_by(StreamHealth.source.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_checkpoint(
        session: AsyncSession,
        *,
        source: str,
        last_signature: str | None = None,
        last_slot: int | None = None,
        last_event_at: datetime | None = None,
    ) -> DiscoveryCheckpoint:
        """Update discovery checkpoint for a stream."""
        stmt = select(DiscoveryCheckpoint).where(DiscoveryCheckpoint.source == source)
        result = await session.execute(stmt)
        cp = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if cp is None:
            cp = DiscoveryCheckpoint(
                source=source,
                last_signature=last_signature,
                last_slot=last_slot,
                last_event_at=last_event_at or now,
                updated_at=now,
            )
            session.add(cp)
        else:
            if last_signature is not None:
                cp.last_signature = last_signature
            if last_slot is not None:
                cp.last_slot = last_slot
            if last_event_at is not None:
                cp.last_event_at = last_event_at
            cp.updated_at = now

        await session.flush()
        await session.refresh(cp)
        return cp

    @staticmethod
    async def record_telegram_signal_discovery(
        session: AsyncSession,
        *,
        chat_id: int,
        message_id: int,
        message_text: str,
        token_address: str,
        message_created_at: datetime,
        received_at: datetime,
        source_name: str | None = None,
        source_username: str | None = None,
        decimals: int | None = None,
        supply: int | None = None,
        validation_status: str = "unverified",
    ) -> Token | None:
        """
        Integrates a Telegram signal into the canonical token registry and discovery events.
        Ensures Telegram calls resolve to the same canonical token identity.
        """
        if not is_valid_solana_address(token_address):
            return None

        token, is_new = await TokenRegistry.resolve_or_create_token(
            session,
            mint_address=token_address,
            source="telegram",
            discovered_at=received_at,
            decimals=decimals,
            total_supply=supply,
            verification_status=validation_status,
        )

        # Record discovery event
        source_event_id = f"{chat_id}:{message_id}"
        await TokenRegistry.record_discovery_event(
            session,
            token_id=token.id,
            mint_address=token_address,
            source="telegram",
            event_type="signal_call",
            source_event_id=source_event_id,
            source_timestamp=message_created_at,
            received_at=received_at,
            raw_payload={
                "chat_id": chat_id,
                "message_id": message_id,
                "message_text": message_text,
                "source_name": source_name,
                "source_username": source_username,
            },
            is_duplicate=not is_new,
        )

        # Associate token source
        await TokenRegistry.associate_token_source(
            session,
            token_id=token.id,
            source="telegram",
            seen_at=received_at,
            source_metadata={
                "source_name": source_name,
                "source_username": source_username,
                "chat_id": chat_id,
            },
        )

        return token

