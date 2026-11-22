"""Meco quantitative research, backtesting, and machine learning package."""

from app.research.backtest import (
    BacktestEngine,
    BacktestExecutionConfig,
    BacktestResult,
    SimulatedTrade,
)
from app.research.dataset import (
    DatasetManifest,
    PointInTimeDatasetBuilder,
    PointInTimeFeatures,
)
from app.research.experimentation import (
    ExperimentRegistry,
    ExperimentRun,
    ExperimentStatus,
    ModelArtifactRecord,
    StrategyVersionRecord,
)
from app.research.labels import (
    TargetLabelComputer,
    TargetLabels,
)
from app.research.leakage import (
    DataLeakageGuard,
    LeakageAuditReport,
    SplitResult,
)
from app.research.learning import (
    LearningInsightsReport,
    PaperTradingLearner,
    TradeDiagnosis,
)
from app.research.metrics import (
    PerformanceEvaluator,
    PerformanceSliceSummary,
    QuantitativeReport,
)
from app.research.models_ml import (
    BaseMLModel,
    GradientBoostingModel,
    HeuristicRuleBaseline,
    LogisticRegressionModel,
    MajorityClassBaseline,
    ModelEvaluationReport,
    RandomBaseline,
    RandomForestModel,
)
from app.research.promotion import (
    ChampionChallengerGateway,
    PromotionAuditRecord,
    PromotionEvaluationResult,
    PromotionGateCriteria,
    PromotionStatus,
)

__all__ = [
    "PointInTimeFeatures",
    "PointInTimeDatasetBuilder",
    "DatasetManifest",
    "TargetLabels",
    "TargetLabelComputer",
    "DataLeakageGuard",
    "SplitResult",
    "LeakageAuditReport",
    "BaseMLModel",
    "ModelEvaluationReport",
    "MajorityClassBaseline",
    "RandomBaseline",
    "HeuristicRuleBaseline",
    "LogisticRegressionModel",
    "RandomForestModel",
    "GradientBoostingModel",
    "BacktestEngine",
    "BacktestExecutionConfig",
    "BacktestResult",
    "SimulatedTrade",
    "PerformanceEvaluator",
    "PerformanceSliceSummary",
    "QuantitativeReport",
    "ChampionChallengerGateway",
    "PromotionGateCriteria",
    "PromotionEvaluationResult",
    "PromotionAuditRecord",
    "PromotionStatus",
    "PaperTradingLearner",
    "TradeDiagnosis",
    "LearningInsightsReport",
    "ExperimentRegistry",
    "ExperimentRun",
    "ModelArtifactRecord",
    "StrategyVersionRecord",
    "ExperimentStatus",
]
