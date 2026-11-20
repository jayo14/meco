"""Data transfer objects and models for social intelligence."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class RawSocialPost:
    """Normalized in-memory social post from any permitted public source."""

    source: str  # "x", "telegram", "rss", "news"
    external_id: str
    author_id: str
    author_username: str | None
    content: str
    published_at: datetime
    ingested_at: datetime
    likes_count: int = 0
    reposts_count: int = 0
    replies_count: int = 0
    views_count: int = 0
    referenced_mints: list[str] = field(default_factory=list)
    referenced_symbols: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    language: str = "en"
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""


@dataclass
class TokenMatchResult:
    """Result of matching a social post to a canonical token."""

    token_id: int
    mint_address: str
    match_type: str  # "mint_address", "cashtag_symbol", "project_url", "name_exact"
    confidence: float
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class NarrativeMatchResult:
    """Result of matching a social post or token to a narrative."""

    narrative_id: int
    slug: str
    confidence: float
    matched_keywords: list[str] = field(default_factory=list)


@dataclass
class SocialMetricsResult:
    """Computed point-in-time social metrics."""

    window_seconds: int
    snapshot_time: datetime
    mention_count: int
    mention_velocity: float  # mentions per hour
    unique_authors_count: int
    author_concentration: float  # HHI 0.0 to 1.0
    total_engagement: int
    engagement_velocity: float
    sentiment_positive: float
    sentiment_negative: float
    sentiment_neutral: float
    spam_score: float  # 0.0 to 1.0


@dataclass
class SocialFindingResult:
    """Structured social intelligence finding."""

    finding_type: str
    title: str
    summary: str
    confidence: float
    supporting_evidence: dict[str, Any]
    source_references: list[dict[str, Any]]
    observed_at: datetime
    expires_at: datetime | None = None
    token_id: int | None = None
    narrative_id: int | None = None
