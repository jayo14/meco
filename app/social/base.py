"""Base class for social intelligence source adapters."""
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app.social.models import RawSocialPost

logger = logging.getLogger("meco.social.base")


class BaseSocialAdapter(ABC):
    """Abstract base class for permitted public social data sources."""

    def __init__(self, source_name: str) -> None:
        self.source_name = source_name
        self._running: bool = False
        self._last_poll_time: datetime | None = None
        self._last_error: str | None = None
        self._error_count: int = 0
        self._posts_ingested_count: int = 0
        self._rate_limited_until: datetime | None = None

    @abstractmethod
    async def start(self, post_handler: Callable[[RawSocialPost], Any]) -> None:
        """Start the adapter and route incoming posts to post_handler."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the adapter gracefully."""

    @abstractmethod
    async def poll_once(self) -> list[RawSocialPost]:
        """Poll the source once and return newly fetched posts."""

    def is_rate_limited(self) -> bool:
        """Check if adapter is currently in a rate limit backoff period."""
        if not self._rate_limited_until:
            return False
        return datetime.now(timezone.utc) < self._rate_limited_until

    def set_rate_limit(self, retry_after_seconds: float) -> None:
        """Mark adapter as rate limited until a future timestamp."""
        now = datetime.now(timezone.utc)
        self._rate_limited_until = datetime.fromtimestamp(now.timestamp() + retry_after_seconds, tz=timezone.utc)
        logger.warning(
            "Adapter %s rate-limited for %.1f seconds (until %s)",
            self.source_name,
            retry_after_seconds,
            self._rate_limited_until.isoformat(),
        )

    def record_success(self, count: int = 1) -> None:
        """Record successful poll and reset consecutive error count."""
        self._last_poll_time = datetime.now(timezone.utc)
        self._error_count = 0
        self._last_error = None
        self._posts_ingested_count += count

    def record_error(self, error_msg: str) -> None:
        """Record an error during poll or stream."""
        self._last_poll_time = datetime.now(timezone.utc)
        self._error_count += 1
        self._last_error = error_msg
        logger.warning("Adapter %s error (#%d): %s", self.source_name, self._error_count, error_msg)

    def get_health_status(self) -> dict[str, Any]:
        """Return diagnostic health status."""
        return {
            "source": self.source_name,
            "running": self._running,
            "last_poll_time": self._last_poll_time.isoformat() if self._last_poll_time else None,
            "posts_ingested_count": self._posts_ingested_count,
            "error_count": self._error_count,
            "last_error": self._last_error,
            "is_rate_limited": self.is_rate_limited(),
            "rate_limited_until": self._rate_limited_until.isoformat() if self._rate_limited_until else None,
        }
