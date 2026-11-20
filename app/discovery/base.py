import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
import logging
from typing import Any

from app.discovery.models import (
    ConnectionState,
    NormalizedDiscoveryEvent,
    SourceCapabilities,
    SourceHealthSnapshot,
)

logger = logging.getLogger("meco.discovery.base")


class BaseDiscoveryAdapter:
    """
    Abstract base adapter for discovery sources.
    Each adapter isolates provider-specific connection handling, message formatting,
    reconnection, and health reporting.
    """

    def __init__(
        self,
        source_name: str,
        capabilities: SourceCapabilities,
        *,
        reconnect_min_delay: float = 1.0,
        reconnect_max_delay: float = 60.0,
    ) -> None:
        self.source_name = source_name
        self.capabilities = capabilities
        self.reconnect_min_delay = reconnect_min_delay
        self.reconnect_max_delay = reconnect_max_delay

        self._running = False
        self._task: asyncio.Task | None = None
        self._event_handlers: list[Callable[[NormalizedDiscoveryEvent], Awaitable[None]]] = []
        self._error_handlers: list[Callable[[Exception], Awaitable[None]]] = []

        self.health = SourceHealthSnapshot(
            source=source_name,
            status=ConnectionState.DISCONNECTED,
        )

    @property
    def is_running(self) -> bool:
        return self._running

    def on_event(
        self,
        handler: Callable[[NormalizedDiscoveryEvent], Awaitable[None]],
    ) -> None:
        """Register an event handler for normalized discovery events."""
        self._event_handlers.append(handler)

    def on_error(
        self,
        handler: Callable[[Exception], Awaitable[None]],
    ) -> None:
        """Register an error handler for adapter failures."""
        self._error_handlers.append(handler)

    async def emit_event(self, event: NormalizedDiscoveryEvent) -> None:
        """Dispatch a normalized event to all registered listeners."""
        self.health.events_received += 1
        self.health.last_event_at = datetime.now(timezone.utc)
        if event.source_timestamp and event.received_at:
            delta = (event.received_at - event.source_timestamp).total_seconds() * 1000.0
            if delta >= 0:
                self.health.last_source_latency_ms = round(delta, 2)

        for handler in self._event_handlers:
            try:
                res = handler(event)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.exception(
                    "Error executing event handler in adapter %s: %s",
                    self.source_name,
                    e,
                )

    async def emit_error(self, exc: Exception) -> None:
        """Dispatch an error to registered error handlers and update health."""
        now = datetime.now(timezone.utc)
        self.health.last_error = f"{type(exc).__name__}: {str(exc)}"
        self.health.last_error_at = now
        for handler in self._error_handlers:
            try:
                res = handler(exc)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.exception("Error executing error handler in adapter %s: %s", self.source_name, e)

    def mark_connected(self) -> None:
        self.health.status = ConnectionState.CONNECTED
        self.health.last_connected_at = datetime.now(timezone.utc)
        logger.info("Discovery adapter connected: %s", self.source_name)

    def mark_disconnected(self) -> None:
        self.health.status = ConnectionState.DISCONNECTED
        self.health.last_disconnected_at = datetime.now(timezone.utc)
        logger.warning("Discovery adapter disconnected: %s", self.source_name)

    def mark_reconnecting(self) -> None:
        self.health.status = ConnectionState.RECONNECTING
        self.health.reconnect_count += 1
        logger.info(
            "Discovery adapter reconnecting (attempt %s): %s",
            self.health.reconnect_count,
            self.source_name,
        )

    def get_health(self) -> SourceHealthSnapshot:
        return self.health

    async def start(self) -> None:
        """Start the adapter in the background."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stop the adapter cleanly."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.health.status = ConnectionState.STOPPED
        logger.info("Discovery adapter stopped: %s", self.source_name)

    async def _run_loop(self) -> None:
        """
        Main run loop with automatic reconnection and exponential backoff.
        Subclasses implement `_connect_and_listen()`.
        """
        delay = self.reconnect_min_delay
        while self._running:
            try:
                self.mark_reconnecting()
                await self._connect_and_listen()
                # If listen exits cleanly without error, reset backoff
                delay = self.reconnect_min_delay
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.mark_disconnected()
                await self.emit_error(exc)
                logger.warning(
                    "Adapter %s encountered error: %s. Reconnecting in %.1fs...",
                    self.source_name,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, self.reconnect_max_delay)

    async def _connect_and_listen(self) -> None:
        """Subclasses implement connection and message listening loop."""
        raise NotImplementedError
