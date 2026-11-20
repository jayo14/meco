"""Point-in-time social intelligence metrics, sentiment, and spam burst scoring."""
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    SocialMetricsSnapshot,
    SocialNarrativeAssociation,
    SocialPost,
    SocialTokenAssociation,
)
from app.social.models import SocialMetricsResult

logger = logging.getLogger("meco.social.metrics")

# Lightweight deterministic lexicon for crypto sentiment
BULLISH_KEYWORDS = {
    "bullish", "moon", "gem", "alpha", "pump", "breakout", "accumulate",
    "undervalued", "ath", "long", "buy", "holding", "diamond", "based",
    "rocket", "send", "utility", "100x", "10x", "parabolic", "fire",
}

BEARISH_KEYWORDS = {
    "bearish", "dump", "rug", "scam", "honeypot", "fake", "sell", "dumping",
    "dead", "rekt", "crash", "exit", "liar", "fraud", "exploit", "bleeding",
    "down", "loser", "fag", "short", "shitcoin", "warning",
}


def calculate_lexicon_sentiment(text: str) -> tuple[float, float, float]:
    """Calculate deterministic (positive, negative, neutral) sentiment ratios."""
    words = text.lower().split()
    if not words:
        return 0.0, 0.0, 1.0

    pos_count = sum(1 for w in words if w.strip(".,!?#$") in BULLISH_KEYWORDS)
    neg_count = sum(1 for w in words if w.strip(".,!?#$") in BEARISH_KEYWORDS)
    total_sentiment_words = pos_count + neg_count

    if total_sentiment_words == 0:
        return 0.0, 0.0, 1.0

    pos_score = round(pos_count / (total_sentiment_words + len(words) * 0.1), 4)
    neg_score = round(neg_count / (total_sentiment_words + len(words) * 0.1), 4)
    neutral_score = max(0.0, round(1.0 - (pos_score + neg_score), 4))

    return pos_score, neg_score, neutral_score


def calculate_author_concentration_hhi(authors: list[str]) -> float:
    """Calculate normalized Herfindahl-Hirschman Index (0.0 to 1.0) of author distribution."""
    if not authors:
        return 0.0
    total = len(authors)
    counts = Counter(authors)
    # HHI = sum of squared market shares
    hhi = sum((cnt / total) ** 2 for cnt in counts.values())
    return round(hhi, 4)


def calculate_spam_score(posts: list[SocialPost]) -> float:
    """Calculate spam burst score (0.0 to 1.0) based on content duplication and rapid repetition."""
    if not posts:
        return 0.0
    total = len(posts)
    if total < 2:
        return 0.0

    # 1. Content hash duplication ratio
    unique_hashes = len({p.content_hash for p in posts if p.content_hash})
    hash_duplication_penalty = 1.0 - (unique_hashes / total)

    # 2. Author concentration penalty
    authors = [p.author_id for p in posts]
    author_hhi = calculate_author_concentration_hhi(authors)

    # 3. Burst interval penalty (<30s between posts from same or few authors)
    sorted_posts = sorted(posts, key=lambda x: x.published_at)
    rapid_intervals = 0
    for i in range(1, len(sorted_posts)):
        delta = (sorted_posts[i].published_at - sorted_posts[i - 1].published_at).total_seconds()
        if delta < 30.0:
            rapid_intervals += 1

    rapid_ratio = rapid_intervals / (total - 1)

    # Weighted composite score
    spam_score = (0.45 * hash_duplication_penalty) + (0.35 * author_hhi) + (0.20 * rapid_ratio)
    return min(1.0, max(0.0, round(spam_score, 4)))


class SocialMetricsCalculator:
    """Calculates point-in-time metrics across rolling windows for tokens and narratives."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def calculate_token_metrics(
        self,
        session: AsyncSession,
        token_id: int,
        as_of_time: datetime | None = None,
        window_seconds: int = 3600,
    ) -> SocialMetricsResult:
        """Calculate point-in-time metrics for a canonical token over a window."""
        now = as_of_time or datetime.now(timezone.utc)
        start_time = now - timedelta(seconds=window_seconds)

        # Query posts associated with this token within [start_time, now]
        stmt = (
            select(SocialPost)
            .join(SocialTokenAssociation, SocialPost.id == SocialTokenAssociation.social_post_id)
            .where(
                SocialTokenAssociation.token_id == token_id,
                SocialPost.published_at >= start_time,
                SocialPost.published_at <= now,
            )
            .order_by(SocialPost.published_at.asc())
        )
        posts = (await session.execute(stmt)).scalars().all()

        mention_count = len(posts)
        hours = max(window_seconds / 3600.0, 0.01)
        mention_velocity = round(mention_count / hours, 2)

        authors = [p.author_id for p in posts]
        unique_authors_count = len(set(authors))
        author_concentration = calculate_author_concentration_hhi(authors)

        total_engagement = sum(
            (p.likes_count or 0) + (p.reposts_count or 0) + (p.replies_count or 0) for p in posts
        )
        engagement_velocity = round(total_engagement / hours, 2)

        combined_text = " ".join(p.sanitized_content for p in posts)
        pos, neg, neu = calculate_lexicon_sentiment(combined_text)
        spam_score = calculate_spam_score(posts)

        return SocialMetricsResult(
            window_seconds=window_seconds,
            snapshot_time=now,
            mention_count=mention_count,
            mention_velocity=mention_velocity,
            unique_authors_count=unique_authors_count,
            author_concentration=author_concentration,
            total_engagement=total_engagement,
            engagement_velocity=engagement_velocity,
            sentiment_positive=pos,
            sentiment_negative=neg,
            sentiment_neutral=neu,
            spam_score=spam_score,
        )

    async def save_token_metrics_snapshot(
        self,
        session: AsyncSession,
        token_id: int,
        metrics: SocialMetricsResult,
    ) -> SocialMetricsSnapshot:
        """Persist a computed token metrics snapshot."""
        snapshot = SocialMetricsSnapshot(
            token_id=token_id,
            narrative_id=None,
            window_seconds=metrics.window_seconds,
            snapshot_time=metrics.snapshot_time,
            mention_count=metrics.mention_count,
            mention_velocity=metrics.mention_velocity,
            unique_authors_count=metrics.unique_authors_count,
            author_concentration=metrics.author_concentration,
            total_engagement=metrics.total_engagement,
            engagement_velocity=metrics.engagement_velocity,
            sentiment_positive=metrics.sentiment_positive,
            sentiment_negative=metrics.sentiment_negative,
            sentiment_neutral=metrics.sentiment_neutral,
            spam_score=metrics.spam_score,
        )
        session.add(snapshot)
        await session.flush()
        return snapshot

    async def calculate_narrative_metrics(
        self,
        session: AsyncSession,
        narrative_id: int,
        as_of_time: datetime | None = None,
        window_seconds: int = 3600,
    ) -> SocialMetricsResult:
        """Calculate point-in-time metrics for a narrative over a window."""
        now = as_of_time or datetime.now(timezone.utc)
        start_time = now - timedelta(seconds=window_seconds)

        stmt = (
            select(SocialPost)
            .join(SocialNarrativeAssociation, SocialPost.id == SocialNarrativeAssociation.social_post_id)
            .where(
                SocialNarrativeAssociation.narrative_id == narrative_id,
                SocialPost.published_at >= start_time,
                SocialPost.published_at <= now,
            )
            .order_by(SocialPost.published_at.asc())
        )
        posts = (await session.execute(stmt)).scalars().all()

        mention_count = len(posts)
        hours = max(window_seconds / 3600.0, 0.01)
        mention_velocity = round(mention_count / hours, 2)

        authors = [p.author_id for p in posts]
        unique_authors_count = len(set(authors))
        author_concentration = calculate_author_concentration_hhi(authors)

        total_engagement = sum(
            (p.likes_count or 0) + (p.reposts_count or 0) + (p.replies_count or 0) for p in posts
        )
        engagement_velocity = round(total_engagement / hours, 2)

        combined_text = " ".join(p.sanitized_content for p in posts)
        pos, neg, neu = calculate_lexicon_sentiment(combined_text)
        spam_score = calculate_spam_score(posts)

        return SocialMetricsResult(
            window_seconds=window_seconds,
            snapshot_time=now,
            mention_count=mention_count,
            mention_velocity=mention_velocity,
            unique_authors_count=unique_authors_count,
            author_concentration=author_concentration,
            total_engagement=total_engagement,
            engagement_velocity=engagement_velocity,
            sentiment_positive=pos,
            sentiment_negative=neg,
            sentiment_neutral=neu,
            spam_score=spam_score,
        )
