from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TargetCoverage:
    target_seconds: int
    eligible_count: int
    captured_count: int
    coverage_pct: float
    success_count: int
    failure_count: int
    failure_reasons: dict[str, int] = field(default_factory=dict)
    median_delay_seconds: float | None = None
    max_delay_seconds: float | None = None
    min_delay_seconds: float | None = None


@dataclass
class AuditReport:
    total_signals: int
    unique_signals: int
    unique_tokens: int
    duplicate_rate: float
    source_distribution: dict[str, int]
    date_distribution: dict[str, int]
    validation_distribution: dict[str, int]
    market_status_distribution: dict[str, int]
    dex_distribution: dict[str, int]
    target_coverage: list[TargetCoverage]
    pair_stats: dict[str, Any]
    pair_dex_distribution: dict[str, int]
    generated_at: str


@dataclass
class AnomalyRecord:
    signal_id: int
    token_address: str
    anomaly_type: str
    description: str
    severity: str  # "critical", "high", "medium", "info"
    recommended_action: str  # "exclude_from_returns", "exclude_all", "inspect", "keep_raw"
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExclusionCriteria:
    exclude_test_signals: bool = True
    exclude_signal_103: bool = True
    exclude_invalid_mint: bool = True
    exclude_failed_market: bool = True
    max_observation_delay_seconds: float = 60.0
    min_initial_liquidity_usd: float = 100.0


@dataclass
class OutcomeRecord:
    signal_id: int
    token_address: str
    initial_price: float
    initial_liquidity: float | None
    dex_id: str | None
    message_created_at: datetime
    returns_by_target: dict[int, float] = field(default_factory=dict)
    max_favorable_excursion: float = 0.0
    max_adverse_excursion: float = 0.0
    time_to_mfe: int = 0
    time_to_mae: int = 0
    hit_plus_20: bool = False
    hit_plus_50: bool = False
    hit_plus_100: bool = False
    hit_minus_20: bool = False
    hit_minus_50: bool = False
    hit_minus_80: bool = False
    hit_minus_90: bool = False
    drawdown_after_peak: float | None = None
    recovery_after_trough: float | None = None
    is_excluded: bool = False
    exclusion_reasons: list[str] = field(default_factory=list)


@dataclass
class FeatureRecord:
    signal_id: int
    token_address: str
    timestamp: datetime
    price_usd: float | None
    liquidity_usd: float | None
    volume_5m: float | None
    buys_5m: int | None
    sells_5m: int | None
    total_txns_5m: int | None
    buy_sell_ratio: float | None
    buy_fraction: float | None
    volume_to_liquidity: float | None
    market_cap: float | None
    fdv: float | None
    fdv_to_market_cap: float | None
    dex_id: str | None
    telegram_latency: float | None
    hour_of_day_utc: int = 0
    reported_slippage: float | None = None
    pair_count_initial: int = 1


@dataclass
class PaperTradeResult:
    signal_id: int
    token_address: str
    entry_timestamp: str
    entry_price: float
    entry_liquidity: float
    position_size_usd: float
    exit_timestamp: str
    exit_price: float
    exit_reason: str
    holding_seconds: int
    gross_return_pct: float
    estimated_fees_usd: float
    estimated_slippage_pct: float
    net_return_pct: float
    net_pnl_usd: float
    mfe_pct: float
    mae_pct: float


@dataclass
class HypothesisResult:
    name: str
    rationale: str
    feature_condition: str
    entry_condition: str
    exit_condition: str
    stop_loss_pct: float
    take_profit_pct: float
    max_holding_seconds: int
    train_signals: int
    train_win_rate_pct: float
    train_mean_net_return_pct: float
    train_total_pnl_usd: float
    test_signals: int
    test_win_rate_pct: float
    test_mean_net_return_pct: float
    test_total_pnl_usd: float
    survives_validation: bool
    evidence: str
    counter_evidence: str
    known_limitations: str
    potential_leakage: str
    validation_verdict: str
