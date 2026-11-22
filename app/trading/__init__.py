"""
Meco Autonomous Paper Trading Engine package (Phase 6).
Simulates execution and portfolio management without broadcasting real transactions.
"""
from app.trading.accounting import (
    PortfolioAccount,
    quantize_usd,
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

__all__ = [
    "ExitConditions",
    "ExitReason",
    "OrderSide",
    "OrderType",
    "PaperOrder",
    "PaperPosition",
    "PortfolioAccount",
    "PortfolioSnapshot",
    "PositionStatus",
    "ProposalStatus",
    "RiskGatewayDecision",
    "SimulatedExecutionResult",
    "StopLossConfig",
    "TakeProfitConfig",
    "TakeProfitStage",
    "TradeProposal",
    "quantize_usd",
]
