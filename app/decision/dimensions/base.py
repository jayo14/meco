"""
Dimension evaluators for Meco Evidence-Based Decision Engine.
"""
from abc import ABC, abstractmethod
from datetime import datetime

from app.decision.config import DecisionEngineConfig
from app.decision.models import DimensionScore, TokenDecisionInput


class BaseDimensionEvaluator(ABC):
    """Abstract interface for evaluating a specific decision dimension."""

    @abstractmethod
    def evaluate(
        self,
        input_data: TokenDecisionInput,
        config: DecisionEngineConfig,
        as_of: datetime,
    ) -> DimensionScore:
        """Evaluate dimension score, confidence, components, and evidence."""
        pass
