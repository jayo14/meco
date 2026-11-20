"""Narrative discovery, classification, and association engine."""
import logging
import re
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Narrative, SocialNarrativeAssociation, SocialPost
from app.social.models import NarrativeMatchResult

logger = logging.getLogger("meco.social.narratives")

# Seed baseline Solana ecosystem narratives
BASELINE_NARRATIVES: list[dict[str, Any]] = [
    {
        "name": "AI Agents & Autonomous Systems",
        "slug": "ai_agents",
        "category": "technology",
        "keywords": ["ai", "agent", "autonomous", "swarm", "eliza", "virtuals", "terminal", "llm", "intelligence"],
        "description": "Autonomous AI agents, agent frameworks, and synthetic intelligence on Solana.",
    },
    {
        "name": "Pump.fun Ecosystem & Graduations",
        "slug": "pump_graduations",
        "category": "launchpad",
        "keywords": ["pump", "pumpportal", "bonding curve", "raydium migration", "graduated", "pumpfun"],
        "description": "Tokens launching and migrating through Pump.fun and bonding curve mechanics.",
    },
    {
        "name": "DePIN & Decentralized Hardware",
        "slug": "depin",
        "category": "infrastructure",
        "keywords": ["depin", "render", "helium", "nosana", "gpu", "sensors", "wireless", "compute"],
        "description": "Decentralized physical infrastructure networks and compute hardware on Solana.",
    },
    {
        "name": "Solana Memes & Cultural Meta",
        "slug": "solana_memes",
        "category": "culture",
        "keywords": ["meme", "wif", "bonk", "popcat", "doge", "pepe", "cat", "dog", "meta", "viral"],
        "description": "Solana community memes, animal tokens, and viral internet cultural movements.",
    },
    {
        "name": "Solana DeFi & Yield Protocols",
        "slug": "solana_defi",
        "category": "finance",
        "keywords": ["defi", "dex", "jupiter", "raydium", "meteora", "kamino", "orca", "yield", "staking"],
        "description": "Decentralized exchanges, liquidity pools, lending, and yield infrastructure.",
    },
    {
        "name": "Celebrity & Influencer Launches",
        "slug": "celebrity_tokens",
        "category": "social",
        "keywords": ["celebrity", "influencer", "famous", "musician", "athlete", "presidential", "trump"],
        "description": "Tokens launched by or associated with mainstream public figures and celebrities.",
    },
]

# Stopwords to filter out during n-gram burst detection
STOPWORDS = {
    "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of", "with", "is",
    "are", "was", "were", "this", "that", "it", "from", "by", "as", "be", "has", "have",
    "will", "solana", "sol", "crypto", "token", "coin", "buy", "sell", "new", "just",
}


class NarrativeEngine:
    """Manages narrative catalog, keyword matching, and emerging narrative burst detection."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def initialize_baseline_narratives(self, session: AsyncSession) -> None:
        """Ensure baseline narratives exist in database."""
        for base in BASELINE_NARRATIVES:
            stmt = select(Narrative).where(Narrative.slug == base["slug"])
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                narrative = Narrative(
                    name=base["name"],
                    slug=base["slug"],
                    category=base["category"],
                    keywords=base["keywords"],
                    description=base["description"],
                    status="active",
                )
                session.add(narrative)
                logger.info("Initialized baseline narrative '%s' (%s)", base["name"], base["slug"])
        await session.flush()

    async def match_post_narratives(
        self,
        session: AsyncSession,
        post: SocialPost,
    ) -> list[NarrativeMatchResult]:
        """Match a social post to relevant narratives based on keywords."""
        stmt = select(Narrative).where(Narrative.status == "active")
        narratives = (await session.execute(stmt)).scalars().all()

        text = post.sanitized_content.lower()
        results: list[NarrativeMatchResult] = []

        for narrative in narratives:
            keywords = narrative.keywords or []
            matched: list[str] = []
            for kw in keywords:
                # Word boundary match for exact keyword/phrase
                pattern = r"\b" + re.escape(kw.lower()) + r"\b"
                if re.search(pattern, text):
                    matched.append(kw)

            if matched:
                # Confidence proportional to keyword count and uniqueness
                confidence = min(0.95, 0.40 + 0.15 * len(matched))
                results.append(
                    NarrativeMatchResult(
                        narrative_id=narrative.id,
                        slug=narrative.slug,
                        confidence=confidence,
                        matched_keywords=matched,
                    )
                )

        return results

    async def associate_post_narratives(
        self,
        session: AsyncSession,
        post: SocialPost,
    ) -> list[SocialNarrativeAssociation]:
        """Find matching narratives and persist associations."""
        matches = await self.match_post_narratives(session, post)
        associations: list[SocialNarrativeAssociation] = []

        for m in matches:
            stmt = select(SocialNarrativeAssociation).where(
                SocialNarrativeAssociation.social_post_id == post.id,
                SocialNarrativeAssociation.narrative_id == m.narrative_id,
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                assoc = SocialNarrativeAssociation(
                    social_post_id=post.id,
                    narrative_id=m.narrative_id,
                    confidence=m.confidence,
                    matched_keywords=m.matched_keywords,
                )
                session.add(assoc)
                associations.append(assoc)
            else:
                associations.append(existing)

        await session.flush()
        return associations

    @staticmethod
    def extract_emerging_ngrams(
        posts: list[SocialPost],
        n: int = 2,
        min_freq: int = 3,
    ) -> list[tuple[str, int]]:
        """Extract top n-gram phrases across a recent batch of posts for narrative emergence."""
        phrase_counter: Counter[str] = Counter()

        for p in posts:
            words = [
                re.sub(r"[^\w]", "", w.lower())
                for w in p.sanitized_content.split()
                if len(w) >= 3 and w.lower() not in STOPWORDS
            ]
            words = [w for w in words if w]
            for i in range(len(words) - n + 1):
                phrase = " ".join(words[i : i + n])
                phrase_counter[phrase] += 1

        return [(phrase, count) for phrase, count in phrase_counter.most_common(20) if count >= min_freq]
