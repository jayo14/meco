"""Cross-source market correlation and social intelligence finding generator."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    SocialIntelligenceFinding,
    SocialPost,
    SocialTokenAssociation,
    Token,
    TokenMarketSnapshot,
)
from app.social.metrics import SocialMetricsCalculator
from app.social.models import SocialFindingResult

logger = logging.getLogger("meco.social.correlation")


class SocialMarketCorrelator:
    """Correlates social activity with on-chain and DEX market state without lookahead leakage."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.metrics_calculator = SocialMetricsCalculator(session_factory)

    async def evaluate_token_social_correlations(
        self,
        session: AsyncSession,
        token_id: int,
        as_of_time: datetime | None = None,
    ) -> list[SocialFindingResult]:
        """Evaluate point-in-time relationships between social attention and market activity."""
        now = as_of_time or datetime.now(timezone.utc)

        # 1. Fetch token and earliest market snapshot up to `now`
        token_stmt = select(Token).where(Token.id == token_id)
        token = (await session.execute(token_stmt)).scalar_one_or_none()
        if not token:
            return []

        # Latest market snapshot before `now`
        market_stmt = (
            select(TokenMarketSnapshot)
            .where(
                TokenMarketSnapshot.token_id == token_id,
                TokenMarketSnapshot.observed_at <= now,
            )
            .order_by(TokenMarketSnapshot.observed_at.desc())
            .limit(1)
        )
        market_snap = (await session.execute(market_stmt)).scalar_one_or_none()

        # Earliest social post for this token
        earliest_post_stmt = (
            select(SocialPost)
            .join(SocialTokenAssociation, SocialPost.id == SocialTokenAssociation.social_post_id)
            .where(
                SocialTokenAssociation.token_id == token_id,
                SocialPost.published_at <= now,
            )
            .order_by(SocialPost.published_at.asc())
            .limit(1)
        )
        first_post = (await session.execute(earliest_post_stmt)).scalar_one_or_none()

        # Current 1h social metrics
        metrics_1h = await self.metrics_calculator.calculate_token_metrics(
            session, token_id, as_of_time=now, window_seconds=3600
        )

        findings: list[SocialFindingResult] = []

        # Finding 1: Bot / Coordinated Shill Burst
        if metrics_1h.mention_count >= 5 and metrics_1h.spam_score >= 0.65:
            findings.append(
                SocialFindingResult(
                    finding_type="suspicious_bot_coordination",
                    title=f"Coordinated Bot / Spam Activity Detected for ${token.symbol or 'TOKEN'}",
                    summary=(
                        f"Detected {metrics_1h.mention_count} mentions in the past hour with high author "
                        f"concentration (HHI {metrics_1h.author_concentration:.2f}) and spam score "
                        f"{metrics_1h.spam_score:.2f}."
                    ),
                    confidence=min(0.95, 0.50 + metrics_1h.spam_score * 0.5),
                    supporting_evidence={
                        "mention_count": metrics_1h.mention_count,
                        "author_concentration": metrics_1h.author_concentration,
                        "unique_authors": metrics_1h.unique_authors_count,
                        "spam_score": metrics_1h.spam_score,
                    },
                    source_references=[{"source": "social_metrics", "window": "1h"}],
                    observed_at=now,
                    expires_at=now + timedelta(hours=3),
                    token_id=token.id,
                )
            )

        # Finding 2: Pre-Market Buzz (Social attention preceding liquidity / pool establishment)
        if first_post and market_snap:
            pool_created_ts = market_snap.earliest_pair_created_at
            # Earliest pool creation converted to datetime
            pool_dt = (
                datetime.fromtimestamp(pool_created_ts / 1000.0, tz=timezone.utc)
                if pool_created_ts and pool_created_ts > 10000000000
                else (
                    datetime.fromtimestamp(pool_created_ts, tz=timezone.utc)
                    if pool_created_ts
                    else None
                )
            )

            if pool_dt and first_post.published_at < pool_dt:
                lead_seconds = (pool_dt - first_post.published_at).total_seconds()
                if lead_seconds >= 60.0:
                    findings.append(
                        SocialFindingResult(
                            finding_type="pre_market_buzz",
                            title=f"Social Attention Preceded DEX Liquidity for ${token.symbol or 'TOKEN'}",
                            summary=(
                                f"Earliest social post ({first_post.source}) appeared {lead_seconds / 60:.1f} minutes "
                                f"before the first active DEX trading pool was deployed."
                            ),
                            confidence=0.85,
                            supporting_evidence={
                                "first_post_time": first_post.published_at.isoformat(),
                                "pool_created_time": pool_dt.isoformat(),
                                "lead_seconds": lead_seconds,
                                "first_post_external_id": first_post.external_id,
                            },
                            source_references=[
                                {"source": first_post.source, "external_id": first_post.external_id}
                            ],
                            observed_at=now,
                            expires_at=now + timedelta(hours=12),
                            token_id=token.id,
                        )
                    )

        # Finding 3: Liquidity Divergence (Mentions accelerating while pool liquidity drops)
        if (
            market_snap
            and market_snap.liquidity_usd is not None
            and market_snap.liquidity_usd < 10000.0
            and metrics_1h.mention_velocity >= 5.0
            and metrics_1h.spam_score < 0.50
        ):
            findings.append(
                SocialFindingResult(
                    finding_type="liquidity_social_divergence",
                    title=f"High Social Attention with Thin Liquidity on ${token.symbol or 'TOKEN'}",
                    summary=(
                        f"Social velocity is {metrics_1h.mention_velocity:.1f} mentions/hr, but total liquidity "
                        f"is low (${market_snap.liquidity_usd:,.2f}), creating high slippage and volatility risk."
                    ),
                    confidence=0.78,
                    supporting_evidence={
                        "mention_velocity": metrics_1h.mention_velocity,
                        "liquidity_usd": market_snap.liquidity_usd,
                        "volume_1h": market_snap.volume_1h,
                    },
                    source_references=[{"source": "dexscreener", "snapshot_id": market_snap.id}],
                    observed_at=now,
                    expires_at=now + timedelta(hours=2),
                    token_id=token.id,
                )
            )

        # Finding 4: Late Chase Warning (High attention following massive price drop or post-pump)
        if (
            market_snap
            and market_snap.price_change_1h is not None
            and market_snap.price_change_1h <= -20.0
            and metrics_1h.sentiment_positive > 0.60
            and metrics_1h.mention_velocity >= 4.0
        ):
            findings.append(
                SocialFindingResult(
                    finding_type="attention_lagging_pump",
                    title=f"Late Retail Attention on Declining Price for ${token.symbol or 'TOKEN'}",
                    summary=(
                        f"Social sentiment remains strongly positive despite a {market_snap.price_change_1h:.1f}% "
                        f"price drop in the past hour, indicating lagging retail chasing."
                    ),
                    confidence=0.82,
                    supporting_evidence={
                        "price_change_1h": market_snap.price_change_1h,
                        "sentiment_positive": metrics_1h.sentiment_positive,
                        "mention_velocity": metrics_1h.mention_velocity,
                    },
                    source_references=[{"source": "market_snapshot", "snapshot_id": market_snap.id}],
                    observed_at=now,
                    expires_at=now + timedelta(hours=3),
                    token_id=token.id,
                )
            )

        return findings

    async def save_findings(
        self,
        session: AsyncSession,
        findings: list[SocialFindingResult],
    ) -> list[SocialIntelligenceFinding]:
        """Persist generated social findings to database."""
        persisted: list[SocialIntelligenceFinding] = []
        for f in findings:
            record = SocialIntelligenceFinding(
                token_id=f.token_id,
                narrative_id=f.narrative_id,
                finding_type=f.finding_type,
                title=f.title,
                summary=f.summary,
                confidence=f.confidence,
                supporting_evidence=f.supporting_evidence,
                source_references=f.source_references,
                observed_at=f.observed_at,
                expires_at=f.expires_at,
            )
            session.add(record)
            persisted.append(record)
        await session.flush()
        return persisted
