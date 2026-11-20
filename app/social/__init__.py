"""Social intelligence, narrative discovery, and cross-source market correlation package."""
from app.social.base import BaseSocialAdapter
from app.social.correlation import SocialMarketCorrelator
from app.social.extractor import (
    compute_content_hash,
    extract_cashtags,
    extract_solana_mints,
    extract_urls,
    is_probable_solana_address,
    sanitize_social_text,
)
from app.social.ingestion import SocialIngestionService
from app.social.matcher import TokenSocialMatcher
from app.social.metrics import (
    SocialMetricsCalculator,
    calculate_author_concentration_hhi,
    calculate_lexicon_sentiment,
    calculate_spam_score,
)
from app.social.models import (
    NarrativeMatchResult,
    RawSocialPost,
    SocialFindingResult,
    SocialMetricsResult,
    TokenMatchResult,
)
from app.social.narratives import NarrativeEngine
from app.social.rss_adapter import RSSSocialAdapter
from app.social.telegram_adapter import TelegramSocialAdapter
from app.social.x_adapter import XSocialAdapter

__all__ = [
    "BaseSocialAdapter",
    "NarrativeEngine",
    "NarrativeMatchResult",
    "RSSSocialAdapter",
    "RawSocialPost",
    "SocialFindingResult",
    "SocialIngestionService",
    "SocialMarketCorrelator",
    "SocialMetricsCalculator",
    "SocialMetricsResult",
    "TelegramSocialAdapter",
    "TokenMatchResult",
    "TokenSocialMatcher",
    "XSocialAdapter",
    "calculate_author_concentration_hhi",
    "calculate_lexicon_sentiment",
    "calculate_spam_score",
    "compute_content_hash",
    "extract_cashtags",
    "extract_solana_mints",
    "extract_urls",
    "is_probable_solana_address",
    "sanitize_social_text",
]
