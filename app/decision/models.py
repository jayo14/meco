"""
Core data models and contracts for Meco Evidence-Based Decision Engine (Phase 5).
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.agents.base import AgentFinding, AgentOutput, EvidenceItem


class DecisionOutcome(str, Enum):
    IGNORE = "ignore"
    MONITOR = "monitor"
    INVESTIGATE_FURTHER = "investigate_further"
    WATCHLIST = "watchlist"
    PAPER_TRADE_CANDIDATE = "paper_trade_candidate"
    REJECTED_DUE_TO_HARD_RISK = "rejected_due_to_hard_risk"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class DecisionDimension(str, Enum):
    OPPORTUNITY_QUALITY = "opportunity_quality"
    MARKET_CONDITIONS = "market_conditions"
    SOCIAL_TRACTION = "social_traction"
    LIQUIDITY_QUALITY = "liquidity_quality"
    SECURITY_RISK = "security_risk"
    WALLET_DEPLOYER_RISK = "wallet_deployer_risk"
    DATA_CONFIDENCE = "data_confidence"
    EXECUTION_FEASIBILITY = "execution_feasibility"


class DimensionScore(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dimension: DecisionDimension
    score: float = Field(ge=0.0, le=100.0, description="Normalized score 0.0 to 100.0")
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    components: dict[str, float] = Field(default_factory=dict, description="Transparent subcomponent score breakdown")
    rationale: str = ""
    evidence_sources: list[EvidenceItem] = Field(default_factory=list)


class DimensionScores(BaseModel):
    model_config = ConfigDict(extra="ignore")

    opportunity_quality: DimensionScore
    market_conditions: DimensionScore
    social_traction: DimensionScore
    liquidity_quality: DimensionScore
    security_risk: DimensionScore
    wallet_deployer_risk: DimensionScore
    data_confidence: DimensionScore
    execution_feasibility: DimensionScore

    def to_dict(self) -> dict[str, float]:
        return {
            self.opportunity_quality.dimension.value: self.opportunity_quality.score,
            self.market_conditions.dimension.value: self.market_conditions.score,
            self.social_traction.dimension.value: self.social_traction.score,
            self.liquidity_quality.dimension.value: self.liquidity_quality.score,
            self.security_risk.dimension.value: self.security_risk.score,
            self.wallet_deployer_risk.dimension.value: self.wallet_deployer_risk.score,
            self.data_confidence.dimension.value: self.data_confidence.score,
            self.execution_feasibility.dimension.value: self.execution_feasibility.score,
        }

    def composite_opportunity_score(self) -> float:
        """Weighted blend of opportunity dimensions only (without collapsing risk)."""
        return round(
            0.35 * self.opportunity_quality.score
            + 0.30 * self.market_conditions.score
            + 0.20 * self.social_traction.score
            + 0.15 * self.liquidity_quality.score,
            2,
        )

    def composite_risk_penalty(self) -> float:
        """Composite risk dimension metric (higher means higher danger)."""
        return round(
            0.60 * self.security_risk.score + 0.40 * self.wallet_deployer_risk.score,
            2,
        )


class HardRiskViolation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    rule_code: str
    description: str
    severity: str = "critical"
    evidence: EvidenceItem | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class DecisionExplanation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    evidence_available: dict[str, Any] = Field(
        default_factory=dict,
        description="Q1: What evidence was available at evaluation time?"
    )
    token_state_at_time: dict[str, Any] = Field(
        default_factory=dict,
        description="Q2: What was the token's state at the time?"
    )
    contributing_agents: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Q3: Which agents contributed and what were their outputs?"
    )
    critical_risk_factors: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Q4: Which risk factors mattered and what thresholds were breached?"
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Q5: What information was missing or stale?"
    )
    scoring_config_used: dict[str, Any] = Field(
        default_factory=dict,
        description="Q6: Which scoring configuration was used?"
    )
    outcome_selection_rationale: str = Field(
        default="",
        description="Q7: Why was this specific outcome selected over alternatives?"
    )


class TokenDecisionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    token_id: int | None = None
    mint_address: str
    outcome: DecisionOutcome
    reasoning_summary: str
    dimension_scores: DimensionScores
    hard_risk_violations: list[HardRiskViolation] = Field(default_factory=list)
    supporting_evidence: list[EvidenceItem] = Field(default_factory=list)
    contradictory_evidence: list[EvidenceItem] = Field(default_factory=list)
    risk_factors: list[dict[str, Any]] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    decision_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expiration_time: datetime
    engine_version: str = "1.0.0"
    scoring_config_version: str = "1.0.0"
    explanation: DecisionExplanation | None = None

    def is_expired(self, at_time: datetime | None = None) -> bool:
        eval_time = at_time or datetime.now(timezone.utc)
        return eval_time >= self.expiration_time

    def explain(self) -> DecisionExplanation:
        """Return the structured 7-question explanation of this decision."""
        if self.explanation is not None:
            return self.explanation
        return DecisionExplanation(
            evidence_available={"supporting_count": len(self.supporting_evidence)},
            token_state_at_time={"mint_address": self.mint_address},
            critical_risk_factors=[h.model_dump() for h in self.hard_risk_violations],
            missing_information=self.missing_information,
            scoring_config_used={"version": self.scoring_config_version},
            outcome_selection_rationale=self.reasoning_summary,
        )


class TokenDecisionInput(BaseModel):
    """
    Timestamped container of all intelligence, specialist findings, and market features
    ingested by the Decision Engine.
    """
    model_config = ConfigDict(extra="ignore")

    mint_address: str
    token_id: int | None = None
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # 1. Canonical token information
    canonical_token: dict[str, Any] = Field(default_factory=dict)
    # 2. Discovery history
    discovery_history: list[dict[str, Any]] = Field(default_factory=list)
    # 3. Lifecycle state
    lifecycle_state: str = "discovered"
    # 4. Security and authority findings
    security_findings: dict[str, Any] | None = None
    # 5. Holder distribution
    holder_distribution: dict[str, Any] | None = None
    # 6. Deployer and wallet intelligence
    deployer_intelligence: dict[str, Any] | None = None
    # 7. Liquidity and pool information
    liquidity_pool: dict[str, Any] | None = None
    # 8. Market observations
    market_observations: list[dict[str, Any]] = Field(default_factory=list)
    # 9. Social intelligence
    social_intelligence: dict[str, Any] | None = None
    # 10. Research agent findings
    research_agent_output: AgentOutput | None = None
    # 11. Risk agent findings
    risk_agent_output: AgentOutput | None = None
    # 12. Market analysis findings
    market_agent_output: AgentOutput | None = None
    # 13. Social agent findings
    social_agent_output: AgentOutput | None = None
    # 14. Validated statistical model outputs
    statistical_model_outputs: dict[str, Any] | None = None

    # Timestamps of individual components for staleness enforcement
    input_timestamps: dict[str, datetime] = Field(default_factory=dict)


class ReassessmentTriggerType(str, Enum):
    LIQUIDITY_CHANGE = "liquidity_change"
    SIGNIFICANT_PRICE_MOVEMENT = "significant_price_movement"
    HOLDER_CHANGE = "holder_change"
    AUTHORITY_CHANGE = "authority_change"
    NEW_SOCIAL_ACTIVITY = "new_social_activity"
    NEW_RISK_FINDINGS = "new_risk_findings"
    MARKET_DETERIORATION = "market_deterioration"
    DECISION_EXPIRED = "decision_expired"
    MANUAL_REQUEST = "manual_request"


class ReassessmentTriggerEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mint_address: str
    token_id: int | None = None
    trigger_type: ReassessmentTriggerType
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    delta_metrics: dict[str, Any] = Field(default_factory=dict)
    is_emergency: bool = False
    details: str = ""
