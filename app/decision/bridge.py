"""
Intelligence Bridge: Reconstructs TokenDecisionInput from database models
and connects AgentOrchestrator investigation results to the Decision Engine.
"""
from datetime import datetime, timezone
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.base import (
    AgentFinding,
    AgentOutput,
    AgentStatus,
    EvidenceItem,
    FindingType,
    HardRiskCondition,
    SoftWarning,
)
from app.database.models import (
    AgentInvestigationResult,
    DiscoveryEvent,
    MarketObservation,
    MarketPairObservation,
    SocialMetricsSnapshot,
    Token,
    TokenHolderSnapshot,
    TokenInvestigation,
    TokenSecurityProfile,
)
from app.decision.models import TokenDecisionInput

logger = logging.getLogger("meco.decision.bridge")


async def build_decision_input_from_db(
    session: AsyncSession,
    mint_address: str,
    investigation_id: str | None = None,
    as_of: datetime | None = None,
) -> TokenDecisionInput:
    """
    Query database models up to timestamp as_of to build a rich,
    zero-leakage TokenDecisionInput.
    """
    eval_time = as_of or datetime.now(timezone.utc)
    if eval_time.tzinfo is None:
        eval_time = eval_time.replace(tzinfo=timezone.utc)

    # 1. Canonical Token
    token_stmt = select(Token).where(Token.mint_address == mint_address)
    token_res = await session.execute(token_stmt)
    token = token_res.scalar_one_or_none()
    token_id = token.id if token else None

    canonical_token = {}
    if token:
        canonical_token = {
            "mint_address": token.mint_address,
            "name": token.name,
            "symbol": token.symbol,
            "decimals": token.decimals,
            "total_supply": token.total_supply,
            "verification_status": token.verification_status,
            "lifecycle_state": token.lifecycle_state,
        }

    input_timestamps: dict[str, datetime] = {}

    # 2. Discovery History
    disc_stmt = (
        select(DiscoveryEvent)
        .where(
            DiscoveryEvent.mint_address == mint_address,
            DiscoveryEvent.discovered_at <= eval_time,
        )
        .order_by(DiscoveryEvent.discovered_at.asc())
    )
    disc_res = await session.execute(disc_stmt)
    disc_events = [
        {
            "source": d.source,
            "event_type": d.event_type,
            "timestamp": d.discovered_at,
            "metadata": d.initial_metadata,
        }
        for d in disc_res.scalars().all()
    ]

    # 3. Security Findings
    sec_stmt = (
        select(TokenSecurityProfile)
        .where(
            TokenSecurityProfile.mint_address == mint_address,
            TokenSecurityProfile.analyzed_at <= eval_time,
        )
        .order_by(TokenSecurityProfile.analyzed_at.desc())
    )
    sec_res = await session.execute(sec_stmt)
    sec = sec_res.scalars().first()
    sec_dict = None
    if sec:
        sec_dict = {
            "mint_authority": sec.mint_authority,
            "freeze_authority": sec.freeze_authority,
            "has_mint_authority": sec.has_mint_authority,
            "has_freeze_authority": sec.has_freeze_authority,
            "is_mutable": sec.is_mutable,
            "is_token_2022": sec.is_token_2022,
            "transfer_fee_bps": sec.transfer_fee_bps,
            "lp_burned_percentage": sec.lp_burned_percentage,
            "top_10_holder_percent": sec.top_10_holder_percent,
            "is_honeypot": sec.honeypot_risk,
            "honeypot_risk": sec.honeypot_risk,
        }
        input_timestamps["security_findings"] = sec.analyzed_at

    # 4. Holder Distribution
    holder_stmt = (
        select(TokenHolderSnapshot)
        .where(
            TokenHolderSnapshot.mint_address == mint_address,
            TokenHolderSnapshot.snapshot_time <= eval_time,
        )
        .order_by(TokenHolderSnapshot.snapshot_time.desc())
    )
    holder_res = await session.execute(holder_stmt)
    holder = holder_res.scalars().first()
    holder_dict = None
    if holder:
        holder_dict = {
            "top_10_percentage": holder.top_10_percent,
            "unique_holders_count": holder.unique_holders,
            "deployer_holding_pct": holder.deployer_balance_percent,
            "max_single_holder_pct": holder.top_10_percent / 2.5 if holder.top_10_percent else 0.0,
        }
        input_timestamps["holder_distribution"] = holder.snapshot_time

    # 5. Liquidity Pool
    pool_stmt = (
        select(MarketPairObservation)
        .where(
            MarketPairObservation.base_token_address == mint_address,
            MarketPairObservation.observed_at <= eval_time,
        )
        .order_by(MarketPairObservation.observed_at.desc())
    )
    pool_res = await session.execute(pool_stmt)
    pool = pool_res.scalars().first()
    pool_dict = None
    if pool:
        pool_dict = {
            "pair_address": pool.pair_address,
            "dex": pool.dex_id,
            "liquidity_usd": pool.liquidity_usd,
            "volume_5m": pool.volume_5m,
            "volume_1h": pool.volume_1h,
            "volume_24h": pool.volume_24h,
            "buys_5m": pool.buys_5m,
            "sells_5m": pool.sells_5m,
            "price_change_5m": pool.price_change_5m,
            "price_change_1h": pool.price_change_1h,
            "pair_created_at": pool.pair_created_at,
        }
        input_timestamps["liquidity_pool"] = pool.observed_at

    # 6. Market Observations
    obs_stmt = (
        select(MarketObservation)
        .where(
            MarketObservation.mint_address == mint_address,
            MarketObservation.observation_time <= eval_time,
        )
        .order_by(MarketObservation.observation_time.asc())
        .limit(20)
    )
    obs_res = await session.execute(obs_stmt)
    observations = [
        {
            "price_usd": o.price_usd,
            "volume_5m": o.volume_5m,
            "volume_1h": o.volume_1h,
            "buys_5m": o.buys_5m,
            "sells_5m": o.sells_5m,
            "price_change_5m": o.price_change_5m,
            "price_change_1h": o.price_change_1h,
            "timestamp": o.observation_time,
        }
        for o in obs_res.scalars().all()
    ]
    if observations:
        input_timestamps["market_observations"] = observations[-1]["timestamp"]

    # 7. Social Intelligence
    social_stmt = (
        select(SocialMetricsSnapshot)
        .where(
            SocialMetricsSnapshot.token_id == token_id,
            SocialMetricsSnapshot.snapshot_time <= eval_time,
        )
        .order_by(SocialMetricsSnapshot.snapshot_time.desc())
    )
    social_res = await session.execute(social_stmt)
    soc = social_res.scalars().first()
    social_dict = None
    if soc:
        social_dict = {
            "mention_count": soc.mention_count,
            "mention_velocity": soc.mention_velocity,
            "unique_authors_count": soc.unique_authors_count,
            "author_concentration": soc.author_concentration,
            "sentiment_positive": soc.sentiment_positive,
            "sentiment_negative": soc.sentiment_negative,
            "spam_score": soc.spam_score,
        }
        input_timestamps["social_intelligence"] = soc.snapshot_time

    # 8. Reconstruct Agent Outputs from TokenInvestigation
    agent_outputs: dict[str, AgentOutput] = {}
    if investigation_id:
        inv_stmt = select(TokenInvestigation).where(TokenInvestigation.id == investigation_id)
    else:
        inv_stmt = (
            select(TokenInvestigation)
            .where(
                TokenInvestigation.mint_address == mint_address,
                TokenInvestigation.created_at <= eval_time,
            )
            .order_by(TokenInvestigation.created_at.desc())
        )
    inv_res = await session.execute(inv_stmt)
    inv = inv_res.scalar_one_or_none()

    if inv:
        results_stmt = select(AgentInvestigationResult).where(
            AgentInvestigationResult.investigation_id == inv.id
        )
        results_res = await session.execute(results_stmt)
        for r in results_res.scalars().all():
            agent_outputs[r.agent_name] = AgentOutput(
                agent_name=r.agent_name,
                status=AgentStatus(r.status) if r.status in AgentStatus.__members__.values() else AgentStatus.COMPLETED,
                confidence=r.confidence,
                insufficient_evidence=r.insufficient_evidence,
                findings=[AgentFinding(**f) for f in (r.findings or [])],
                evidence_references=[EvidenceItem(**e) for e in (r.evidence_references or [])],
                unanswered_questions=r.unanswered_questions or [],
                hard_risks=[HardRiskCondition(**h) for h in (r.hard_risks or [])],
                soft_warnings=[SoftWarning(**w) for w in (r.soft_warnings or [])],
                metrics=r.metrics or {},
                error_message=r.error_message,
                model_provider=r.model_provider,
                model_name=r.model_name,
            )

    return TokenDecisionInput(
        mint_address=mint_address,
        token_id=token_id,
        as_of=eval_time,
        canonical_token=canonical_token,
        discovery_history=disc_events,
        lifecycle_state=token.lifecycle_state if token else "discovered",
        security_findings=sec_dict,
        holder_distribution=holder_dict,
        deployer_intelligence=None,
        liquidity_pool=pool_dict,
        market_observations=observations,
        social_intelligence=social_dict,
        research_agent_output=agent_outputs.get("research"),
        risk_agent_output=agent_outputs.get("risk"),
        market_agent_output=agent_outputs.get("market_analysis"),
        social_agent_output=agent_outputs.get("social"),
        statistical_model_outputs=None,
        input_timestamps=input_timestamps,
    )
