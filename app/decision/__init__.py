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
from app.decision.engine import (
    DecisionEngine,
)
from app.decision.explain import (
    DecisionAuditTracer,
)
from app.decision.freshness import (
    FreshnessValidationResult,
    evaluate_input_freshness,
)
from app.decision.hard_rules import (
    evaluate_hard_risk_rules,
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
from app.decision.ranking import (
    OpportunityRanker,
    RankedTokenOpportunity,
)

__all__ = [
    "DecisionAuditTracer",
    "DecisionDimension",
    "DecisionEngine",
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
    "RankedTokenOpportunity",
    "ReassessmentConfig",
    "OpportunityRanker",
    "ReassessmentTriggerEvent",
    "ReassessmentTriggerType",
    "TokenDecisionInput",
    "TokenDecisionResult",
    "evaluate_hard_risk_rules",
    "evaluate_input_freshness",
    "get_decision_config",
    "register_decision_config",
]
