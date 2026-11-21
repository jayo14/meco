from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.agents.base import AgentFinding, AgentOutput, EvidenceItem


class TokenInvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mint_address: str
    trigger: str = "manual"
    requested_agents: list[str] | None = None
    timeout_seconds: float = 60.0
    force_refresh: bool = False


class DecisionEngineHandoffPackage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    investigation_id: str
    mint_address: str
    token_id: int | None = None
    verdict: str  # PASS, FAIL, HOLD, INSUFFICIENT_DATA
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    hard_risks_detected: list[str] = Field(default_factory=list)
    soft_warnings_count: int = 0
    overall_confidence: float = 0.0
    agent_results: dict[str, Any] = Field(default_factory=dict)
    consolidated_facts: list[AgentFinding] = Field(default_factory=list)
    consolidated_evidence: list[EvidenceItem] = Field(default_factory=list)
    unanswered_questions: list[str] = Field(default_factory=list)
    ready_for_trade_decision: bool = False
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
