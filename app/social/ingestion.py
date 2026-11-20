"""Social ingestion service for deduplication and persistence."""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import SocialPost
from app.social.extractor import (
    compute_content_hash,
    extract_cashtags,
    extract_solana_mints,
    extract_urls,
    sanitize_social_text,
)
from app.social.models import RawSocialPost

logger = logging.getLogger("meco.social.ingestion")


class SocialIngestionService:
    """Service to process raw social posts, enrich them with entities, and persist idempotently."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def ingest_post(
        self,
        session: AsyncSession,
        post: RawSocialPost,
    ) -> SocialPost | None:
        """Ingest a single post idempotently.

        Returns the persisted SocialPost or None if duplicate.
        """
        # 1. Check for existing post by (source, external_id)
        stmt = select(SocialPost).where(
            SocialPost.source == post.source,
            SocialPost.external_id == str(post.external_id),
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            # Optionally update engagement metrics if newer
            if (
                post.likes_count > existing.likes_count
                or post.reposts_count > existing.reposts_count
                or post.replies_count > existing.replies_count
                or post.views_count > existing.views_count
            ):
                existing.likes_count = max(existing.likes_count, post.likes_count)
                existing.reposts_count = max(existing.reposts_count, post.reposts_count)
                existing.replies_count = max(existing.replies_count, post.replies_count)
                existing.views_count = max(existing.views_count, post.views_count)
                await session.flush()
            return existing

        # 2. Extract and sanitize
        sanitized = sanitize_social_text(post.content)
        content_hash = post.content_hash or compute_content_hash(post.content)

        mints = post.referenced_mints or extract_solana_mints(post.content)
        symbols = post.referenced_symbols or extract_cashtags(post.content)
        urls = post.urls or extract_urls(post.content)

        # Also extract mints that might be in URLs (e.g., pump.fun/coin/<MINT>, dexscreener.com/solana/<MINT>)
        for u in urls:
            url_mints = extract_solana_mints(u)
            for m in url_mints:
                if m not in mints:
                    mints.append(m)

        db_post = SocialPost(
            source=post.source,
            external_id=str(post.external_id),
            author_id=str(post.author_id),
            author_username=post.author_username,
            content=post.content,
            sanitized_content=sanitized,
            published_at=post.published_at or datetime.now(timezone.utc),
            ingested_at=post.ingested_at or datetime.now(timezone.utc),
            likes_count=max(0, post.likes_count),
            reposts_count=max(0, post.reposts_count),
            replies_count=max(0, post.replies_count),
            views_count=max(0, post.views_count),
            referenced_mints=mints,
            referenced_symbols=symbols,
            urls=urls,
            language=post.language or "en",
            raw_metadata=post.raw_metadata or {},
            content_hash=content_hash,
        )

        session.add(db_post)
        await session.flush()
        logger.debug(
            "Ingested %s post #%s (author=%s, mints=%d, symbols=%d)",
            db_post.source,
            db_post.external_id,
            db_post.author_id,
            len(mints),
            len(symbols),
        )
        return db_post

    async def ingest_batch(
        self,
        posts: list[RawSocialPost],
    ) -> list[SocialPost]:
        """Ingest a batch of posts in an atomic transaction."""
        results: list[SocialPost] = []
        async with self.session_factory() as session, session.begin():
            for p in posts:
                try:
                    res = await self.ingest_post(session, p)
                    if res is not None:
                        results.append(res)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Error ingesting post #%s from %s: %s", p.external_id, p.source, exc)
        return results
