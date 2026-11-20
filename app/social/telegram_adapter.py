"""Telegram message adapter for social intelligence."""
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app.social.base import BaseSocialAdapter
from app.social.models import RawSocialPost

logger = logging.getLogger("meco.social.telegram")


class TelegramSocialAdapter(BaseSocialAdapter):
    """Adapter bridging Telegram messages into normalized RawSocialPost objects."""

    def __init__(self) -> None:
        super().__init__(source_name="telegram")
        self._handler: Callable[[RawSocialPost], Any] | None = None

    async def start(self, post_handler: Callable[[RawSocialPost], Any]) -> None:
        self._running = True
        self._handler = post_handler
        logger.info("Telegram social adapter started")

    async def stop(self) -> None:
        self._running = False
        self._handler = None
        logger.info("Telegram social adapter stopped")

    def transform_telegram_message(
        self,
        message_id: int | str,
        channel_id: int | str,
        channel_title: str | None,
        text: str,
        date: datetime | None,
        views: int = 0,
        forwards: int = 0,
    ) -> RawSocialPost:
        """Convert Telegram raw event data into normalized RawSocialPost."""
        pub_date = date.astimezone(timezone.utc) if date and date.tzinfo else (date or datetime.now(timezone.utc))
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)

        external_id = f"tg_{channel_id}_{message_id}"
        author_id = str(channel_id)

        return RawSocialPost(
            source="telegram",
            external_id=external_id,
            author_id=author_id,
            author_username=channel_title or f"channel_{channel_id}",
            content=text or "",
            published_at=pub_date,
            ingested_at=datetime.now(timezone.utc),
            likes_count=0,
            reposts_count=max(0, forwards),
            replies_count=0,
            views_count=max(0, views),
            language="en",
            raw_metadata={
                "channel_id": channel_id,
                "message_id": message_id,
                "channel_title": channel_title,
                "forwards": forwards,
                "views": views,
            },
        )

    async def poll_once(self) -> list[RawSocialPost]:
        """Telegram is primarily push/event-driven via Telethon client."""
        return []
