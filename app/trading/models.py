"""
Data models and status enums for Meco Autonomous Paper Trading Engine (Phase 6).
All financial and monetary quantities use Decimal to guarantee accurate precision.
"""
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field


class PositionStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    OPEN = "open"
    PARTIALLY_EXITED = "partially_exited"
    CLOSED = "closed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"
    FAILED = "failed"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class ExitReason(str, Enum):
    TAKE_PROFIT_FULL = "take_profit_full"
    TAKE_PROFIT_PARTIAL = "take_profit_partial"
    STOP_LOSS = "stop_loss"
    TRAILING_STOP = "trailing_stop"
    MAX_HOLDING_TIME = "max_holding_time"
    LIQUIDITY_DETERIORATION = "liquidity_deterioration"
    RISK_TRIGGERED = "risk_triggered"
    STRATEGY_INVALIDATION = "strategy_invalidation"
    EMERGENCY_STOP = "emergency_stop"
    MANUAL_EXIT = "manual_exit"


class StopLossConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    stop_loss_pct: Decimal = Field(default=Decimal("15.0"), description="Stop loss percentage below entry")
    is_trailing: bool = Field(default=False, description="Whether stop trails peak price")
    trailing_activation_pct: Decimal = Field(default=Decimal("10.0"), description="Profit pct before trail activates")
    trailing_delta_pct: Decimal = Field(default=Decimal("10.0"), description="Trailing distance pct from peak")


class TakeProfitStage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    target_gain_pct: Decimal = Field(description="Percentage gain target (e.g. 25.0)")
    close_fraction: Decimal = Field(description="Fraction of remaining quantity to exit (e.g. 0.50)")


class TakeProfitConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    stages: list[TakeProfitStage] = Field(
        default_factory=lambda: [
            TakeProfitStage(target_gain_pct=Decimal("30.0"), close_fraction=Decimal("0.50")),
            TakeProfitStage(target_gain_pct=Decimal("75.0"), close_fraction=Decimal("1.00")),
        ]
    )


class ExitConditions(BaseModel):
    model_config = ConfigDict(extra="ignore")

    stop_loss: StopLossConfig = Field(default_factory=StopLossConfig)
    take_profit: TakeProfitConfig = Field(default_factory=TakeProfitConfig)
    max_holding_seconds: int = Field(default=7200, description="Max holding duration (2 hours)")
    max_liquidity_drop_pct: Decimal = Field(default=Decimal("30.0"), description="Exit if liquidity falls by > 30%")
    exit_on_critical_risk: bool = Field(default=True, description="Exit immediately if token raises hard risk")


class TradeProposal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    proposal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mint_address: str
    token_id: int | None = None
    strategy_id: str
    strategy_version: str = "1.0.0"
    decision_id: str
    proposed_entry_price: Decimal
    proposed_position_size_usd: Decimal
    expected_slippage_pct: Decimal = Field(default=Decimal("1.5"))
    max_acceptable_price_impact_pct: Decimal = Field(default=Decimal("3.0"))
    exit_conditions: ExitConditions = Field(default_factory=ExitConditions)
    risk_assessment: dict[str, Any] = Field(default_factory=dict)
    proposal_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    proposal_expiration: datetime
    status: ProposalStatus = ProposalStatus.PENDING
    rejection_reason: str | None = None

    def is_expired(self, at_time: datetime | None = None) -> bool:
        eval_time = at_time or datetime.now(timezone.utc)
        if eval_time.tzinfo is None:
            eval_time = eval_time.replace(tzinfo=timezone.utc)
        return eval_time >= self.proposal_expiration


class RiskGatewayDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    approved: bool
    rejection_reasons: list[str] = Field(default_factory=list)
    adjusted_size_usd: Decimal | None = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rule_evaluations: dict[str, Any] = Field(default_factory=dict)


class SimulatedExecutionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    success: bool
    side: OrderSide
    requested_size_usd: Decimal
    executed_size_usd: Decimal = Decimal("0")
    executed_quantity: Decimal = Decimal("0")
    requested_price: Decimal
    executed_price: Decimal = Decimal("0")
    base_slippage_usd: Decimal = Decimal("0")
    price_impact_usd: Decimal = Decimal("0")
    dex_fee_usd: Decimal = Decimal("0")
    network_fee_usd: Decimal = Decimal("0")
    total_fee_usd: Decimal = Decimal("0")
    is_partial_fill: bool = False
    fill_fraction: Decimal = Decimal("1.0")
    failure_reason: str | None = None
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assumptions_logged: dict[str, Any] = Field(default_factory=dict)
    is_simulated: bool = True


class PaperOrder(BaseModel):
    model_config = ConfigDict(extra="ignore")

    order_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    position_id: str
    mint_address: str
    side: OrderSide
    order_type: OrderType
    requested_size_usd: Decimal
    executed_size_usd: Decimal = Decimal("0")
    executed_price: Decimal = Decimal("0")
    executed_quantity: Decimal = Decimal("0")
    total_fees_usd: Decimal = Decimal("0")
    status: str = "completed"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    executed_at: datetime | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class PaperPosition(BaseModel):
    model_config = ConfigDict(extra="ignore")

    position_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    proposal_id: str
    mint_address: str
    token_id: int | None = None
    strategy_id: str
    status: PositionStatus = PositionStatus.OPEN
    entry_time: datetime
    entry_price: Decimal
    quantity: Decimal
    capital_committed: Decimal
    current_mark_price: Decimal
    unrealised_pnl_usd: Decimal = Decimal("0")
    realised_pnl_usd: Decimal = Decimal("0")
    total_fees_paid_usd: Decimal = Decimal("0")
    exit_history: list[PaperOrder] = Field(default_factory=list)
    exit_conditions: ExitConditions
    peak_price: Decimal
    initial_pool_liquidity_usd: Decimal | None = None
    max_favourable_excursion_usd: Decimal = Decimal("0")
    max_adverse_excursion_usd: Decimal = Decimal("0")
    exit_reason: ExitReason | None = None
    closed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def holding_duration_seconds(self, at_time: datetime | None = None) -> float:
        end_t = self.closed_at or at_time or datetime.now(timezone.utc)
        if end_t.tzinfo is None:
            end_t = end_t.replace(tzinfo=timezone.utc)
        start_t = self.entry_time
        if start_t.tzinfo is None:
            start_t = start_t.replace(tzinfo=timezone.utc)
        return max(0.0, (end_t - start_t).total_seconds())


class PortfolioSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")

    snapshot_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    starting_capital: Decimal
    available_capital: Decimal
    reserved_capital: Decimal
    open_positions_value: Decimal
    realised_pnl: Decimal
    unrealised_pnl: Decimal
    total_fees: Decimal
    net_equity: Decimal
    peak_equity: Decimal
    current_drawdown_pct: Decimal
    open_positions_count: int
    exposure_by_token: dict[str, Decimal] = Field(default_factory=dict)
    exposure_by_strategy: dict[str, Decimal] = Field(default_factory=dict)
