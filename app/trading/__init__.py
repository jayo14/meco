"""
Meco Autonomous Paper Trading Engine package (Phase 6).
Simulates execution and portfolio management without broadcasting real transactions.
"""
from app.trading.accounting import (
    PortfolioAccount,
    quantize_usd,
)
from app.trading.engine import (
    PaperTradingEngine,
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
from app.trading.performance import (
    PerformanceAnalyzer,
    StrategyPerformanceSummary,
    TradingPerformanceReport,
)
from app.trading.persistence import (
    PersistenceManager,
)
from app.trading.position_manager import (
    ExitEvaluator,
    ExitSignal,
    PositionManager,
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
from app.trading.wallet_spec import (
    DEFAULT_ALLOWED_PROGRAMS,
    LiveReadinessStatus,
    LiveTradingReadinessEvaluator,
    MecoWalletPolicy,
    ReadinessEvaluationReport,
    ReadinessGateCriteria,
    TransactionPolicyValidator,
    TransactionValidationResult,
    ValidationCode,
)

__all__ = [
    "DEFAULT_ALLOWED_PROGRAMS",
    "BaseTradingStrategy",
    "ExecutionSimulatorConfig",
    "ExitConditions",
    "ExitEvaluator",
    "ExitReason",
    "ExitSignal",
    "LiquiditySurgeStrategy",
    "LiveReadinessStatus",
    "LiveTradingReadinessEvaluator",
    "MecoWalletPolicy",
    "MomentumBreakoutStrategy",
    "OrderSide",
    "OrderType",
    "PaperExecutionSimulator",
    "PaperOrder",
    "PaperPosition",
    "PaperTradingEngine",
    "PerformanceAnalyzer",
    "PersistenceManager",
    "PortfolioAccount",
    "PortfolioSnapshot",
    "PositionManager",
    "PositionSizer",
    "PositionSizingConfig",
    "PositionStatus",
    "PreTradeRiskGateway",
    "ProposalGenerator",
    "ProposalStatus",
    "ReadinessEvaluationReport",
    "ReadinessGateCriteria",
    "RiskGatewayConfig",
    "RiskGatewayDecision",
    "SimulatedExecutionResult",
    "SizingDecision",
    "SizingMethod",
    "StopLossConfig",
    "StrategyPerformanceSummary",
    "StrategyRegistry",
    "TakeProfitConfig",
    "TakeProfitStage",
    "TradeProposal",
    "TradingPerformanceReport",
    "TransactionPolicyValidator",
    "TransactionValidationResult",
    "ValidationCode",
    "quantize_usd",
]
