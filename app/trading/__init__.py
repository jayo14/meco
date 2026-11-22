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
from app.trading.proposal import (
    ProposalGenerator,
)
from app.trading.risk_gateway import (
    PreTradeRiskGateway,
    RiskGatewayConfig,
)
from app.trading.sizing import (
    PositionSizer,
    PositionSizingConfig,
    SizingDecision,
    SizingMethod,
)
from app.trading.strategy import (
    BaseTradingStrategy,
    LiquiditySurgeStrategy,
    MomentumBreakoutStrategy,
    StrategyRegistry,
)

__all__ = [
    "BaseTradingStrategy",
    "ExecutionSimulatorConfig",
    "ExitConditions",
    "ExitReason",
    "LiquiditySurgeStrategy",
    "MomentumBreakoutStrategy",
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
    "PreTradeRiskGateway",
    "ProposalGenerator",
    "ProposalStatus",
    "RiskGatewayConfig",
    "RiskGatewayDecision",
    "SimulatedExecutionResult",
    "SizingDecision",
    "SizingMethod",
    "StopLossConfig",
    "StrategyRegistry",
    "TakeProfitConfig",
    "TakeProfitStage",
    "TradeProposal",
    "quantize_usd",
]
