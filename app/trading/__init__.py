"""
Meco Autonomous Paper Trading Engine package (Phase 6).
Simulates execution and portfolio management without broadcasting real transactions.
"""
from app.trading.accounting import (
    PortfolioAccount,
    quantize_usd,
)
from app.trading.execution import (
    ExecutionSimulatorConfig,
    PaperExecutionSimulator,
)
from app.trading.models import (
    ExitConditions,
    ExitReason,
    OrderSide,
    OrderType,
    PaperOrder,
    PaperPosition,
    PortfolioSnapshot,
    PositionStatus,
    ProposalStatus,
    RiskGatewayDecision,
    SimulatedExecutionResult,
    StopLossConfig,
    TakeProfitConfig,
    TakeProfitStage,
    TradeProposal,
)
from app.trading.sizing import (
    PositionSizer,
    PositionSizingConfig,
    SizingDecision,
    SizingMethod,
)

__all__ = [
    "ExecutionSimulatorConfig",
    "ExitConditions",
    "ExitReason",
    "OrderSide",
    "OrderType",
    "PaperExecutionSimulator",
    "PaperOrder",
    "PaperPosition",
    "PortfolioAccount",
    "PortfolioSnapshot",
    "PositionSizer",
    "PositionSizingConfig",
    "PositionStatus",
    "ProposalStatus",
    "RiskGatewayDecision",
    "SimulatedExecutionResult",
    "SizingDecision",
    "SizingMethod",
    "StopLossConfig",
    "TakeProfitConfig",
    "TakeProfitStage",
    "TradeProposal",
    "quantize_usd",
]
