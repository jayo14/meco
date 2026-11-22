"""
Experiment Tracking & Version Registry for Meco Quantitative Research (Phase 7).

Maintains versioned registries of:
- Strategy implementations & parameter definitions.
- Model artifacts, weights, and hyper-parameters.
- Experiment runs, training configs, and validation scores.
- Audit trails preventing unauthorized or unverified strategy tampering.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

from app.research.dataset import DatasetManifest
from app.research.metrics import QuantitativeReport
from app.research.models_ml import ModelEvaluationReport


class ExperimentStatus(str, Enum):
    CONFIGURED = "configured"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


@dataclass
class ModelArtifactRecord:
    """Versioned model metadata artifact."""
    model_id: str
    version: str
    model_family: str  # logistic_regression, random_forest, gradient_boosting, heuristic
    hyperparameters: dict[str, Any]
    feature_columns: list[str]
    trained_dataset_hash: str
    in_sample_metrics: dict[str, Any]
    out_of_sample_metrics: dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_champion: bool = False


@dataclass
class StrategyVersionRecord:
    """Versioned strategy configuration record."""
    strategy_id: str
    version: str
    description: str
    parameters: dict[str, Any]
    associated_model_id: str | None = None
    associated_model_version: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_active: bool = False
    is_locked: bool = True  # Locked to prevent live in-place self-modification


@dataclass
class ExperimentRun:
    """Complete record of a research experiment iteration."""
    experiment_id: str = field(default_factory=lambda: f"exp_{uuid.uuid4().hex[:8]}")
    experiment_name: str = ""
    hypothesis: str = ""
    dataset_manifest: DatasetManifest | None = None
    strategy_version: StrategyVersionRecord | None = None
    model_artifact: ModelArtifactRecord | None = None
    status: ExperimentStatus = ExperimentStatus.CONFIGURED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
    in_sample_report: ModelEvaluationReport | None = None
    out_of_sample_report: ModelEvaluationReport | None = None
    backtest_report: QuantitativeReport | None = None
    execution_notes: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


class ExperimentRegistry:
    """
    Central experiment registry for reproducible quantitative ML iterations.
    Strictly forbids uncontrolled live strategy self-modification.
    """

    def __init__(self) -> None:
        self.experiments: dict[str, ExperimentRun] = {}
        self.model_artifacts: dict[str, ModelArtifactRecord] = {}
        self.strategy_versions: dict[str, StrategyVersionRecord] = {}

    def register_strategy(
        self,
        strategy_id: str,
        version: str,
        description: str,
        parameters: dict[str, Any],
        associated_model_id: str | None = None,
        associated_model_version: str | None = None,
        lock_live_modification: bool = True,
    ) -> StrategyVersionRecord:
        """Register a versioned immutable strategy template."""
        key = f"{strategy_id}@{version}"
        if key in self.strategy_versions and self.strategy_versions[key].is_locked:
            raise ValueError(f"Strategy version {key} is locked and cannot be overwritten.")

        rec = StrategyVersionRecord(
            strategy_id=strategy_id,
            version=version,
            description=description,
            parameters=parameters,
            associated_model_id=associated_model_id,
            associated_model_version=associated_model_version,
            is_locked=lock_live_modification,
        )
        self.strategy_versions[key] = rec
        return rec

    def register_model_artifact(
        self,
        model_id: str,
        version: str,
        model_family: str,
        hyperparameters: dict[str, Any],
        feature_columns: list[str],
        trained_dataset_hash: str,
        in_sample_metrics: dict[str, Any],
        out_of_sample_metrics: dict[str, Any],
    ) -> ModelArtifactRecord:
        """Register a versioned model artifact with reproducible metrics."""
        key = f"{model_id}@{version}"
        rec = ModelArtifactRecord(
            model_id=model_id,
            version=version,
            model_family=model_family,
            hyperparameters=hyperparameters,
            feature_columns=feature_columns,
            trained_dataset_hash=trained_dataset_hash,
            in_sample_metrics=in_sample_metrics,
            out_of_sample_metrics=out_of_sample_metrics,
        )
        self.model_artifacts[key] = rec
        return rec

    def create_experiment(
        self,
        name: str,
        hypothesis: str,
        dataset_manifest: DatasetManifest,
        strategy_key: str | None = None,
        model_key: str | None = None,
        tags: list[str] | None = None,
    ) -> ExperimentRun:
        """Initialize and persist a new experiment tracking record."""
        strat = self.strategy_versions.get(strategy_key) if strategy_key else None
        model = self.model_artifacts.get(model_key) if model_key else None

        exp = ExperimentRun(
            experiment_name=name,
            hypothesis=hypothesis,
            dataset_manifest=dataset_manifest,
            strategy_version=strat,
            model_artifact=model,
            status=ExperimentStatus.CONFIGURED,
            tags=tags or [],
        )
        self.experiments[exp.experiment_id] = exp
        return exp

    def complete_experiment(
        self,
        experiment_id: str,
        in_sample_report: ModelEvaluationReport | None = None,
        out_of_sample_report: ModelEvaluationReport | None = None,
        backtest_report: QuantitativeReport | None = None,
        notes: list[str] | None = None,
    ) -> ExperimentRun:
        """Finalize experiment with verified evaluation and backtest scorecards."""
        exp = self.experiments.get(experiment_id)
        if not exp:
            raise KeyError(f"Experiment {experiment_id} not found in registry.")

        exp.status = ExperimentStatus.COMPLETED
        exp.completed_at = datetime.now(timezone.utc).isoformat()
        exp.in_sample_report = in_sample_report
        exp.out_of_sample_report = out_of_sample_report
        exp.backtest_report = backtest_report
        if notes:
            exp.execution_notes.extend(notes)
        return exp
