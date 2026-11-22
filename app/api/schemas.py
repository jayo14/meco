"""
Pydantic Schemas for Meco Intelligence Dashboard & Control Centre API (Phase 8).
"""
from datetime import datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, Field


class SystemOverviewResponse(BaseModel):
    system_status: str
    total_tokens_discovered: int
    new_tokens_last_24h: int
    tokens_enriching_count: int
    tokens_under_investigation_count: int
    watchlisted_opportunities_count: int
    rejected_opportunities_count: int
    open_paper_positions_count: int
    closed_paper_positions_count: int
    portfolio_starting_capital: float
    portfolio_available_capital: float
    portfolio_reserved_capital: float
    portfolio_net_equity: float
    realised_pnl_usd: float
    unrealised_pnl_usd: float
    total_fees_paid_usd: float
    current_drawdown_pct: float
    active_strategies_count: int
    active_strategies: list[str]
    emergency_stop_active: bool
    as_of: datetime


class TokenSummaryItem(BaseModel):
    token_mint: str
    token_id: int | None = None
    name: str | None = None
    symbol: str | None = None
    discovery_source: str
    discovered_at: datetime
    first_seen_price_usd: float | None = None
    current_price_usd: float | None = None
    pool_liquidity_usd: float | None = None
    volume_5m_usd: float | None = None
    lifecycle_state: str
    enrichment_status: str
    top10_holder_share_pct: float | None = None
    mint_authority_revoked: bool | None = None
    freeze_authority_revoked: bool | None = None
    risk_level: str = "unknown"
    opportunity_score: float | None = None
    latest_decision_outcome: str | None = None


class TokenDetailResponse(BaseModel):
    token_mint: str
    token_id: int | None = None
    name: str | None = None
    symbol: str | None = None
    decimals: int | None = 9
    total_supply: float | None = None
    discovery_source: str
    discovered_at: datetime
    lifecycle_state: str
    enrichment_status: str

    # Liquidity & Pool Information
    dex_id: str | None = None
    pair_address: str | None = None
    pool_liquidity_usd: float | None = None
    initial_liquidity_usd: float | None = None
    current_price_usd: float | None = None
    volume_5m_usd: float | None = None
    volume_1h_usd: float | None = None
    buys_5m: int | None = None
    sells_5m: int | None = None
    price_change_5m: float | None = None

    # Security & Authorities
    mint_authority: str | None = None
    freeze_authority: str | None = None
    mint_authority_revoked: bool | None = None
    freeze_authority_revoked: bool | None = None
    is_honeypot: bool | None = None
    transfer_fee_bps: int | None = 0

    # Holders & Deployer
    holder_count: int | None = None
    top10_holder_share_pct: float | None = None
    deployer_address: str | None = None
    deployer_prior_token_count: int | None = None
    deployer_risk_score: float | None = None
    suspicious_sniper_count: int | None = None

    # Social & Narratives
    social_post_count_1h: int | None = None
    social_reach_estimate: int | None = None
    social_sentiment_score: float | None = None
    narrative_tier: str | None = None
    narrative_keywords: list[str] = Field(default_factory=list)

    # Agent Findings
    investigations: list[dict[str, Any]] = Field(default_factory=list)

    # Decision History
    decisions: list[dict[str, Any]] = Field(default_factory=list)

    # Paper Trading Activity
    positions: list[dict[str, Any]] = Field(default_factory=list)


class AgentInvestigationItem(BaseModel):
    investigation_id: str
    token_mint: str
    token_name: str | None = None
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    agent_findings_count: int = 0
    findings: list[dict[str, Any]] = Field(default_factory=list)
    models_used: list[str] = Field(default_factory=list)
    summary_verdict: str | None = None


class DecisionRecordItem(BaseModel):
    decision_id: str
    token_mint: str
    token_symbol: str | None = None
    outcome: str
    opportunity_rank: int | None = None
    opportunity_score: float | None = None
    confidence_score: float
    risk_level: str
    reasoning_summary: str
    supporting_evidence: list[str] = Field(default_factory=list)
    contradictory_evidence: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    decision_timestamp: datetime
    expiration_timestamp: datetime
    is_expired: bool = False


class PaperPositionItem(BaseModel):
    position_id: str
    proposal_id: str
    token_mint: str
    token_symbol: str | None = None
    strategy_id: str
    status: str
    entry_time: datetime
    entry_price: float
    current_mark_price: float
    quantity: float
    capital_committed: float
    unrealised_pnl_usd: float
    realised_pnl_usd: float
    total_fees_paid_usd: float
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    peak_price: float
    max_favourable_excursion_usd: float
    max_adverse_excursion_usd: float
    holding_duration_seconds: float
    exit_reason: str | None = None
    closed_at: datetime | None = None
    is_simulated: bool = True


class SystemHealthResponse(BaseModel):
    overall_status: str  # healthy, degraded, critical
    database_connected: bool
    rpc_connected: bool
    rpc_latency_ms: float
    discovery_sources: list[dict[str, Any]]
    background_backlog_count: int
    agent_engine_status: str
    paper_engine_status: str
    emergency_stop_engaged: bool
    recent_errors: list[dict[str, Any] | str] = Field(default_factory=list)
    as_of: datetime


class OperatorControlCommand(BaseModel):
    action: str  # pause_discovery, resume_discovery, pause_enrichment, resume_enrichment, emergency_stop, reset_emergency_stop, toggle_strategy, close_position, trigger_investigation, trigger_backtest
    confirmation: bool = False
    target_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    operator_notes: str | None = None
