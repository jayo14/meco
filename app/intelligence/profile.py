import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import (
    Token,
)

logger = logging.getLogger("meco.intelligence.profile")


@dataclass
class FindingProvenance:
    source: str
    timestamp: str
    evidence: str
    confidence: float = 1.0


@dataclass
class TokenIntelligenceProfile:
    mint_address: str
    name: str | None
    symbol: str | None
    decimals: int | None
    total_supply: int | None
    lifecycle_state: str
    risk_score: float | None
    first_discovered_at: str
    first_discovery_source: str
    last_enriched_at: str | None

    # Provenance & Discovery
    discovery_history: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    # Security & Authority
    security: dict[str, Any] = field(default_factory=dict)

    # Liquidity & Pool Intelligence
    liquidity: dict[str, Any] = field(default_factory=dict)

    # Holder Concentration
    holders: dict[str, Any] = field(default_factory=dict)

    # Historical Snapshots
    market_history_count: int = 0
    recent_market_snapshots: list[dict[str, Any]] = field(default_factory=list)

    # Lifecycle Events
    lifecycle_events: list[dict[str, Any]] = field(default_factory=list)

    # Active Investigation Queue
    outstanding_tasks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


async def build_token_intelligence_profile(
    session: AsyncSession,
    mint_address: str,
) -> TokenIntelligenceProfile | None:
    """
    Assemble the comprehensive consolidated intelligence profile for a token,
    linking identity, discovery provenance, security findings, holder analysis,
    multi-pool market data, and lifecycle history with strict provenance.
    """
    stmt = (
        select(Token)
        .where(Token.mint_address == mint_address)
        .options(
            selectinload(Token.discovery_events),
            selectinload(Token.sources),
            selectinload(Token.security_profile),
            selectinload(Token.metadata_record),
            selectinload(Token.holder_snapshots),
            selectinload(Token.market_snapshots),
            selectinload(Token.lifecycle_events),
            selectinload(Token.enrichment_tasks),
        )
    )
    result = await session.execute(stmt)
    token = result.scalar_one_or_none()

    if token is None:
        return None

    # 1. Discovery History
    disc_history = [
        {
            "id": ev.id,
            "source": ev.source,
            "event_type": ev.event_type,
            "signature": ev.signature,
            "slot": ev.slot,
            "commitment": ev.commitment,
            "source_timestamp": ev.source_timestamp.isoformat() if ev.source_timestamp else None,
            "received_at": ev.received_at.isoformat() if ev.received_at else None,
            "is_duplicate": ev.is_duplicate,
            "provenance": {
                "source": ev.source,
                "timestamp": ev.received_at.isoformat() if ev.received_at else None,
                "evidence": f"Recorded event #{ev.id} via adapter {ev.source}",
            },
        }
        for ev in token.discovery_events
    ]

    # 2. Sources Summary
    src_summary = [
        {
            "source": ts.source,
            "first_seen_at": ts.first_seen_at.isoformat() if ts.first_seen_at else None,
            "last_seen_at": ts.last_seen_at.isoformat() if ts.last_seen_at else None,
            "event_count": ts.event_count,
            "metadata": ts.source_metadata,
        }
        for ts in token.sources
    ]

    # 3. Metadata
    meta_dict = {}
    if token.metadata_record:
        mr = token.metadata_record
        meta_dict = {
            "name": mr.name,
            "symbol": mr.symbol,
            "description": mr.description,
            "image_uri": mr.image_uri,
            "metadata_uri": mr.metadata_uri,
            "website": mr.website,
            "twitter": mr.twitter,
            "telegram": mr.telegram,
            "discord": mr.discord,
            "launchpad": mr.launchpad,
            "is_uri_fetched": mr.is_uri_fetched,
            "uri_fetch_error": mr.uri_fetch_error,
            "provenance": {
                "source": "metadata_resolver",
                "timestamp": mr.updated_at.isoformat(),
                "evidence": f"URI: {mr.metadata_uri or 'on-chain hints'}",
            },
        }

    # 4. Security Profile
    sec_dict = {}
    if token.security_profile:
        sp = token.security_profile
        sec_dict = {
            "token_program": sp.token_program,
            "mint_authority": sp.mint_authority,
            "is_mintable": sp.is_mintable,
            "freeze_authority": sp.freeze_authority,
            "is_freezable": sp.is_freezable,
            "permanent_delegate": sp.permanent_delegate,
            "has_transfer_fee": sp.has_transfer_fee,
            "transfer_fee_basis_points": sp.transfer_fee_basis_points,
            "risk_score": sp.risk_score,
            "risk_factors": sp.risk_factors or [],
            "verified_facts": sp.verified_facts or [],
            "provenance": {
                "source": "solana_rpc_mint_decode",
                "timestamp": sp.updated_at.isoformat(),
                "evidence": f"Direct binary decode of mint {token.mint_address}",
            },
        }

    # 5. Liquidity & Recent Market
    mkt_snaps = sorted(token.market_snapshots, key=lambda s: s.observed_at)
    latest_mkt = mkt_snaps[-1] if mkt_snaps else None
    liq_dict = {}
    if latest_mkt:
        liq_dict = {
            "primary_pair_address": latest_mkt.primary_pair_address,
            "primary_dex_id": latest_mkt.primary_dex_id,
            "price_usd": latest_mkt.price_usd,
            "liquidity_usd": latest_mkt.liquidity_usd,
            "market_cap": latest_mkt.market_cap,
            "fdv": latest_mkt.fdv,
            "volume_5m": latest_mkt.volume_5m,
            "buys_5m": latest_mkt.buys_5m,
            "sells_5m": latest_mkt.sells_5m,
            "pairs_count": latest_mkt.pairs_count,
            "pool_age_seconds": latest_mkt.pool_age_seconds,
            "all_pairs": latest_mkt.pairs_data or [],
            "provenance": {
                "source": "dexscreener_snapshot",
                "timestamp": latest_mkt.observed_at.isoformat(),
                "evidence": f"Checked {latest_mkt.pairs_count} pairs via DexScreener",
            },
        }

    # 6. Holder Concentration
    holder_snaps = sorted(token.holder_snapshots, key=lambda s: s.observed_at)
    latest_holders = holder_snaps[-1] if holder_snaps else None
    holder_dict = {}
    if latest_holders:
        holder_dict = {
            "total_holders_count": latest_holders.total_holders_count,
            "top10_concentration_pct": latest_holders.top10_concentration_pct,
            "top20_concentration_pct": latest_holders.top20_concentration_pct,
            "deployer_address": latest_holders.deployer_address,
            "deployer_holding_pct": latest_holders.deployer_holding_pct,
            "top_holders": latest_holders.top_holders or [],
            "provenance": {
                "source": "solana_rpc_token_largest_accounts",
                "timestamp": latest_holders.observed_at.isoformat(),
                "evidence": "getTokenLargestAccounts RPC response",
            },
        }

    # 7. Recent Market Snapshots
    recent_mkt_list = [
        {
            "id": s.id,
            "observed_at": s.observed_at.isoformat(),
            "price_usd": s.price_usd,
            "liquidity_usd": s.liquidity_usd,
            "volume_5m": s.volume_5m,
            "primary_dex_id": s.primary_dex_id,
        }
        for s in mkt_snaps[-10:]
    ]

    # 8. Lifecycle Events
    lifecycle_list = [
        {
            "from_state": ev.from_state,
            "to_state": ev.to_state,
            "reason": ev.reason,
            "occurred_at": ev.occurred_at.isoformat(),
        }
        for ev in sorted(token.lifecycle_events, key=lambda e: e.occurred_at)
    ]

    # 9. Outstanding Tasks
    active_tasks = [
        {
            "id": t.id,
            "task_type": t.task_type,
            "status": t.status,
            "priority": t.priority,
            "scheduled_at": t.scheduled_at.isoformat(),
            "retry_count": t.retry_count,
        }
        for t in token.enrichment_tasks
        if t.status in ("pending", "running")
    ]

    return TokenIntelligenceProfile(
        mint_address=token.mint_address,
        name=token.name,
        symbol=token.symbol,
        decimals=token.decimals,
        total_supply=token.total_supply,
        lifecycle_state=token.lifecycle_state,
        risk_score=token.risk_score,
        first_discovered_at=token.first_discovered_at.isoformat(),
        first_discovery_source=token.first_discovery_source,
        last_enriched_at=token.last_enriched_at.isoformat() if token.last_enriched_at else None,
        discovery_history=disc_history,
        sources=src_summary,
        metadata=meta_dict,
        security=sec_dict,
        liquidity=liq_dict,
        holders=holder_dict,
        market_history_count=len(mkt_snaps),
        recent_market_snapshots=recent_mkt_list,
        lifecycle_events=lifecycle_list,
        outstanding_tasks=active_tasks,
    )
