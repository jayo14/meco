"""
Machine Learning Baseline and Predictive Models for Meco (Phase 7).

Implements:
1. Non-predictive & Heuristic Baselines:
   - MajorityClassBaseline (constant prior)
   - RandomBaseline (uniform random)
   - HeuristicRuleBaseline (transparent heuristic: buy pressure + volume acceleration)
2. Interpretable Statistical & Tree Models:
   - LogisticRegressionModel (linear with sigmoid probability calibration)
   - RandomForestModel (scikit-learn ensemble with feature importances)
   - GradientBoostingModel (HistGradientBoosting / LightGBM)
3. Standardized Evaluation Metrics:
   - ROC-AUC, Brier score, Log Loss, Precision, Recall, F1, Accuracy.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import math
import random
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)


@dataclass
class ModelEvaluationReport:
    """Standardized performance metrics for binary classification models."""
    model_name: str
    model_version: str
    sample_size: int
    positive_rate: float
    accuracy: float
    roc_auc: float | None
    brier_score: float
    log_loss: float | None
    precision: float
    recall: float
    f1: float
    feature_importances: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseMLModel(ABC):
    """Abstract interface for all Meco research prediction models."""

    def __init__(self, model_name: str, version: str = "1.0.0") -> None:
        self.model_name = model_name
        self.version = version
        self.is_fitted = False
        self.feature_names: list[str] = []

    @abstractmethod
    def fit(self, X: list[list[float]], y: list[int], feature_names: list[str] | None = None) -> "BaseMLModel":
        pass

    @abstractmethod
    def predict_proba(self, X: list[list[float]]) -> list[float]:
        """Return probability of positive class (target = 1) for each sample."""
        pass

    def predict(self, X: list[list[float]], threshold: float = 0.5) -> list[int]:
        """Return binary prediction based on decision threshold."""
        probas = self.predict_proba(X)
        return [1 if p >= threshold else 0 for p in probas]

    def evaluate(self, X: list[list[float]], y: list[int], threshold: float = 0.5) -> ModelEvaluationReport:
        """Compute full statistical evaluation metrics across out-of-sample data."""
        if not X or not y:
            return ModelEvaluationReport(
                model_name=self.model_name,
                model_version=self.version,
                sample_size=0,
                positive_rate=0.0,
                accuracy=0.0,
                roc_auc=None,
                brier_score=0.0,
                log_loss=None,
                precision=0.0,
                recall=0.0,
                f1=0.0,
            )

        probas = self.predict_proba(X)
        preds = [1 if p >= threshold else 0 for p in probas]

        y_arr = np.array(y, dtype=int)
        p_arr = np.array(probas, dtype=float)
        pred_arr = np.array(preds, dtype=int)

        n = len(y_arr)
        pos_rate = float(np.mean(y_arr))

        acc = float(accuracy_score(y_arr, pred_arr))
        prec = float(precision_score(y_arr, pred_arr, zero_division=0))
        rec = float(recall_score(y_arr, pred_arr, zero_division=0))
        f1 = float(f1_score(y_arr, pred_arr, zero_division=0))

        # Handle ROC-AUC when only one class is present in y
        roc = None
        if len(np.unique(y_arr)) > 1:
            try:
                roc = float(roc_auc_score(y_arr, p_arr))
            except Exception:
                roc = 0.5

        # Brier score: MSE between probability and binary target
        brier = float(brier_score_loss(y_arr, p_arr))

        # Log loss
        ll = None
        try:
            # Clip probabilities to prevent log(0)
            p_clipped = np.clip(p_arr, 1e-15, 1 - 1e-15)
            ll = float(log_loss(y_arr, p_clipped))
        except Exception:
            ll = None

        feat_imp = self.get_feature_importances()

        return ModelEvaluationReport(
            model_name=self.model_name,
            model_version=self.version,
            sample_size=n,
            positive_rate=round(pos_rate, 4),
            accuracy=round(acc, 4),
            roc_auc=round(roc, 4) if roc is not None else None,
            brier_score=round(brier, 4),
            log_loss=round(ll, 4) if ll is not None else None,
            precision=round(prec, 4),
            recall=round(rec, 4),
            f1=round(f1, 4),
            feature_importances=feat_imp,
        )

    def get_feature_importances(self) -> dict[str, float]:
        return {}


# ==============================================================================
# Non-Predictive and Heuristic Baseline Models
# ==============================================================================

class MajorityClassBaseline(BaseMLModel):
    """Predicts historical class frequency for all instances."""

    def __init__(self, version: str = "1.0.0") -> None:
        super().__init__(model_name="majority_class_baseline", version=version)
        self.prior_prob: float = 0.5

    def fit(self, X: list[list[float]], y: list[int], feature_names: list[str] | None = None) -> "MajorityClassBaseline":
        self.prior_prob = float(np.mean(y)) if y else 0.5
        self.feature_names = feature_names or []
        self.is_fitted = True
        return self

    def predict_proba(self, X: list[list[float]]) -> list[float]:
        return [self.prior_prob] * len(X)


class RandomBaseline(BaseMLModel):
    """Predicts a random uniform probability in [0, 1]."""

    def __init__(self, seed: int = 42, version: str = "1.0.0") -> None:
        super().__init__(model_name="random_baseline", version=version)
        self.seed = seed
        self.rng = random.Random(seed)

    def fit(self, X: list[list[float]], y: list[int], feature_names: list[str] | None = None) -> "RandomBaseline":
        self.feature_names = feature_names or []
        self.is_fitted = True
        return self

    def predict_proba(self, X: list[list[float]]) -> list[float]:
        return [round(self.rng.random(), 4) for _ in range(len(X))]


class HeuristicRuleBaseline(BaseMLModel):
    """
    Transparent rule-based baseline:
    Signals with high buy fraction (e.g. > 0.65) and healthy volume-to-liquidity ratio
    are assigned high probability, otherwise low probability.
    """

    def __init__(
        self,
        min_buy_fraction: float = 0.65,
        min_volume_to_liquidity: float = 0.15,
        version: str = "1.0.0",
    ) -> None:
        super().__init__(model_name="heuristic_rule_baseline", version=version)
        self.min_buy_fraction = min_buy_fraction
        self.min_volume_to_liquidity = min_volume_to_liquidity

    def fit(self, X: list[list[float]], y: list[int], feature_names: list[str] | None = None) -> "HeuristicRuleBaseline":
        self.feature_names = feature_names or []
        self.is_fitted = True
        return self

    def predict_proba(self, X: list[list[float]]) -> list[float]:
        # Expect buy_fraction_5m and volume_to_liquidity_ratio
        buy_frac_idx = self.feature_names.index("buy_fraction_5m") if "buy_fraction_5m" in self.feature_names else None
        vol_liq_idx = self.feature_names.index("volume_to_liquidity_ratio") if "volume_to_liquidity_ratio" in self.feature_names else None

        probas: list[float] = []
        for row in X:
            buy_frac = row[buy_frac_idx] if buy_frac_idx is not None and buy_frac_idx < len(row) else 0.5
            vol_liq = row[vol_liq_idx] if vol_liq_idx is not None and vol_liq_idx < len(row) else 0.0

            if buy_frac >= self.min_buy_fraction and vol_liq >= self.min_volume_to_liquidity:
                probas.append(0.80)
            elif buy_frac >= self.min_buy_fraction:
                probas.append(0.55)
            else:
                probas.append(0.20)
        return probas


# ==============================================================================
# Statistical & Tree-Based Machine Learning Models
# ==============================================================================

class LogisticRegressionModel(BaseMLModel):
    """Regularized linear model with sigmoid probability calibration."""

    def __init__(self, C: float = 1.0, max_iter: int = 500, version: str = "1.0.0") -> None:
        super().__init__(model_name="logistic_regression", version=version)
        self.clf = LogisticRegression(C=C, max_iter=max_iter, solver="lbfgs")

    def fit(self, X: list[list[float]], y: list[int], feature_names: list[str] | None = None) -> "LogisticRegressionModel":
        self.feature_names = feature_names or []
        X_arr = np.nan_to_num(np.array(X, dtype=float), nan=0.0, posinf=1e6, neginf=-1e6)
        y_arr = np.array(y, dtype=int)

        if len(np.unique(y_arr)) <= 1:
            # Fallback if only one class exists
            self.is_fitted = False
            return self

        self.clf.fit(X_arr, y_arr)
        self.is_fitted = True
        return self

    def predict_proba(self, X: list[list[float]]) -> list[float]:
        if not self.is_fitted:
            return [0.5] * len(X)
        X_arr = np.nan_to_num(np.array(X, dtype=float), nan=0.0, posinf=1e6, neginf=-1e6)
        probas = self.clf.predict_proba(X_arr)
        return [float(p[1]) for p in probas]

    def get_feature_importances(self) -> dict[str, float]:
        if not self.is_fitted or not hasattr(self.clf, "coef_"):
            return {}
        coefs = self.clf.coef_[0]
        imp: dict[str, float] = {}
        for idx, c in enumerate(coefs):
            col_name = self.feature_names[idx] if idx < len(self.feature_names) else f"feature_{idx}"
            imp[col_name] = round(float(abs(c)), 4)
        return dict(sorted(imp.items(), key=lambda x: x[1], reverse=True))


class RandomForestModel(BaseMLModel):
    """Ensemble of decision trees capturing non-linear interactions."""

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 5,
        random_state: int = 42,
        version: str = "1.0.0",
    ) -> None:
        super().__init__(model_name="random_forest", version=version)
        self.clf = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=random_state,
            class_weight="balanced",
        )

    def fit(self, X: list[list[float]], y: list[int], feature_names: list[str] | None = None) -> "RandomForestModel":
        self.feature_names = feature_names or []
        X_arr = np.nan_to_num(np.array(X, dtype=float), nan=0.0, posinf=1e6, neginf=-1e6)
        y_arr = np.array(y, dtype=int)

        if len(np.unique(y_arr)) <= 1:
            self.is_fitted = False
            return self

        self.clf.fit(X_arr, y_arr)
        self.is_fitted = True
        return self

    def predict_proba(self, X: list[list[float]]) -> list[float]:
        if not self.is_fitted:
            return [0.5] * len(X)
        X_arr = np.nan_to_num(np.array(X, dtype=float), nan=0.0, posinf=1e6, neginf=-1e6)
        probas = self.clf.predict_proba(X_arr)
        return [float(p[1]) for p in probas]

    def get_feature_importances(self) -> dict[str, float]:
        if not self.is_fitted or not hasattr(self.clf, "feature_importances_"):
            return {}
        importances = self.clf.feature_importances_
        imp: dict[str, float] = {}
        for idx, imp_val in enumerate(importances):
            col_name = self.feature_names[idx] if idx < len(self.feature_names) else f"feature_{idx}"
            imp[col_name] = round(float(imp_val), 4)
        return dict(sorted(imp.items(), key=lambda x: x[1], reverse=True))


class GradientBoostingModel(BaseMLModel):
    """Fast histogram-based gradient boosting classifier."""

    def __init__(
        self,
        learning_rate: float = 0.05,
        max_iter: int = 100,
        max_depth: int = 4,
        random_state: int = 42,
        version: str = "1.0.0",
    ) -> None:
        super().__init__(model_name="gradient_boosting", version=version)
        self.clf = HistGradientBoostingClassifier(
            learning_rate=learning_rate,
            max_iter=max_iter,
            max_depth=max_depth,
            random_state=random_state,
        )

    def fit(self, X: list[list[float]], y: list[int], feature_names: list[str] | None = None) -> "GradientBoostingModel":
        self.feature_names = feature_names or []
        X_arr = np.nan_to_num(np.array(X, dtype=float), nan=0.0, posinf=1e6, neginf=-1e6)
        y_arr = np.array(y, dtype=int)

        if len(np.unique(y_arr)) <= 1:
            self.is_fitted = False
            return self

        self.clf.fit(X_arr, y_arr)
        self.is_fitted = True
        return self

    def predict_proba(self, X: list[list[float]]) -> list[float]:
        if not self.is_fitted:
            return [0.5] * len(X)
        X_arr = np.nan_to_num(np.array(X, dtype=float), nan=0.0, posinf=1e6, neginf=-1e6)
        probas = self.clf.predict_proba(X_arr)
        return [float(p[1]) for p in probas]
