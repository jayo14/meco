"""
Meco Evidence-Based Decision Engine package (Phase 5).
"""
from app.decision.config import (
    DecisionEngineConfig,
    FreshnessConfig,
    HardRiskRuleConfig,
    OpportunityWeightsConfig,
    OutcomeThresholdsConfig,
    ReassessmentConfig,
    get_decision_config,
    register_decision_config,
)
from app.decision.freshness import (
    FreshnessValidationResult,
    evaluate_input_freshness,
)
from app.decision.models import (
    DecisionDimension,
    DecisionExplanation,
    DecisionOutcome,
    DimensionScore,
    DimensionScores,
    HardRiskViolation,
    ReassessmentTriggerEvent,
    ReassessmentTriggerType,
    TokenDecisionInput,
    TokenDecisionResult,
)

__all__ = [
    "DecisionDimension",
    "DecisionEngineConfig",
    "DecisionExplanation",
    "DecisionOutcome",
    "DimensionScore",
    "DimensionScores",
    "FreshnessConfig",
    "FreshnessValidationResult",
    "HardRiskRuleConfig",
    "HardRiskViolation",
    "OpportunityWeightsConfig",
    "OutcomeThresholdsConfig",
    "ReassessmentConfig",
    "ReassessmentTriggerEvent",
    "ReassessmentTriggerType",
    "TokenDecisionInput",
    "TokenDecisionResult",
    "evaluate_input_freshness",
    "get_decision_config",
    "register_decision_config",
]
