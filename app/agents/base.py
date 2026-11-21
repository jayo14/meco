from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timezone
from enum import Enum
import logging
import time
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("meco.agents.base")


class FindingType(str, Enum):
    VERIFIED_FACT = "verified_fact"
    STATISTICAL_OBSERVATION = "statistical_observation"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"
    MISSING_INFORMATION = "missing_information"


class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reference: str
    details: dict[str, Any] = Field(default_factory=dict)


class AgentFinding(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: FindingType
    title: str
    statement: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    evidence_sources: list[EvidenceItem] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HardRiskCondition(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    description: str
    severity: str = "critical"
    evidence: EvidenceItem | None = None


class SoftWarning(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    description: str
    severity: str = "warning"
    evidence: EvidenceItem | None = None


class RetryPolicy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    max_retries: int = 2
    backoff_factor: float = 1.5
    initial_delay_seconds: float = 0.5
    retryable_exceptions: list[str] = Field(
        default_factory=lambda: ["TimeoutError", "ConnectionError", "RateLimitError", "AsyncTimeoutError"]
    )


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    timeout_seconds: float = 30.0
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    allow_llm: bool = True
    model_name: str | None = None


class InvestigationContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    investigation_id: str
    token_id: int | None = None
    mint_address: str
    profile: Any = None
    market_data: dict[str, Any] = Field(default_factory=dict)
    social_data: dict[str, Any] = Field(default_factory=dict)
    history_data: dict[str, Any] = Field(default_factory=dict)
    custom_parameters: dict[str, Any] = Field(default_factory=dict)


class AgentOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    agent_name: str
    status: AgentStatus = AgentStatus.COMPLETED
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    insufficient_evidence: bool = False
    insufficient_evidence_reason: str | None = None
    findings: list[AgentFinding] = Field(default_factory=list)
    evidence_references: list[EvidenceItem] = Field(default_factory=list)
    unanswered_questions: list[str] = Field(default_factory=list)
    hard_risks: list[HardRiskCondition] = Field(default_factory=list)
    soft_warnings: list[SoftWarning] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    execution_duration_ms: int = 0
    model_provider: str | None = None
    model_name: str | None = None
    prompt_version: str | None = None
    tokens_used: int | None = None
    raw_synthesis: dict[str, Any] | None = None

    def facts(self) -> list[AgentFinding]:
        return [f for f in self.findings if f.type == FindingType.VERIFIED_FACT]

    def observations(self) -> list[AgentFinding]:
        return [f for f in self.findings if f.type == FindingType.STATISTICAL_OBSERVATION]

    def inferences(self) -> list[AgentFinding]:
        return [f for f in self.findings if f.type == FindingType.INFERENCE]

    def hypotheses(self) -> list[AgentFinding]:
        return [f for f in self.findings if f.type == FindingType.HYPOTHESIS]

    def missing_info(self) -> list[AgentFinding]:
        return [f for f in self.findings if f.type == FindingType.MISSING_INFORMATION]


TOutput = TypeVar("TOutput", bound=AgentOutput)


class BaseAgent(ABC):
    """
    Standard base contract for specialist intelligence agents in Meco.
    Enforces execution timeouts, retries, structured output schema,
    error isolation, and evidence provenance.
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or AgentConfig()

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique agent identifier."""
        pass

    @property
    @abstractmethod
    def responsibility(self) -> str:
        """Clear statement of agent's domain responsibility."""
        pass

    @property
    @abstractmethod
    def required_input(self) -> list[str]:
        """List of required fields/entities in context."""
        pass

    @property
    @abstractmethod
    def available_tools(self) -> list[str]:
        """List of tools or data sources available to this agent."""
        pass

    @property
    def expected_output_schema(self) -> type[AgentOutput]:
        """Expected Pydantic schema for output validation."""
        return AgentOutput

    @property
    @abstractmethod
    def evidence_requirements(self) -> list[str]:
        """Specific evidence types required for findings."""
        pass

    @abstractmethod
    async def investigate(self, context: InvestigationContext) -> AgentOutput:
        """Core specialized investigation logic to implement."""
        pass

    async def run(self, context: InvestigationContext) -> AgentOutput:
        """
        Execute investigation with timeout, retry policy, error handling,
        and output validation. Never raises uncaught exceptions.
        """
        start_time = time.perf_counter()
        retries = 0
        max_retries = self.config.retry_policy.max_retries
        backoff = self.config.retry_policy.initial_delay_seconds
        last_exception: Exception | None = None

        while retries <= max_retries:
            try:
                # Enforce execution timeout
                output = await asyncio.wait_for(
                    self.investigate(context),
                    timeout=self.config.timeout_seconds,
                )

                # Validate output schema
                if not isinstance(output, self.expected_output_schema):
                    output = self.expected_output_schema.model_validate(output.model_dump())

                output.execution_duration_ms = int((time.perf_counter() - start_time) * 1000)
                return output

            except asyncio.TimeoutError as exc:
                last_exception = exc
                logger.warning(
                    f"Agent {self.name} timed out after {self.config.timeout_seconds}s "
                    f"(attempt {retries + 1}/{max_retries + 1})"
                )
                if retries < max_retries:
                    retries += 1
                    await asyncio.sleep(backoff)
                    backoff *= self.config.retry_policy.backoff_factor
                    continue

                duration_ms = int((time.perf_counter() - start_time) * 1000)
                return self.expected_output_schema(
                    agent_name=self.name,
                    status=AgentStatus.TIMED_OUT,
                    confidence=0.0,
                    error_message=f"Agent timed out after {self.config.timeout_seconds}s",
                    execution_duration_ms=duration_ms,
                    insufficient_evidence=True,
                    insufficient_evidence_reason=f"Timeout after {self.config.timeout_seconds}s",
                )

            except Exception as exc:
                last_exception = exc
                exc_type_name = type(exc).__name__
                is_retryable = any(
                    r_type in exc_type_name or r_type in str(exc)
                    for r_type in self.config.retry_policy.retryable_exceptions
                )

                logger.error(
                    f"Agent {self.name} encountered error: {exc_type_name}: {exc} "
                    f"(retryable={is_retryable}, attempt {retries + 1}/{max_retries + 1})"
                )

                if is_retryable and retries < max_retries:
                    retries += 1
                    await asyncio.sleep(backoff)
                    backoff *= self.config.retry_policy.backoff_factor
                    continue

                duration_ms = int((time.perf_counter() - start_time) * 1000)
                return self.expected_output_schema(
                    agent_name=self.name,
                    status=AgentStatus.FAILED,
                    confidence=0.0,
                    error_message=f"{exc_type_name}: {str(exc)}",
                    execution_duration_ms=duration_ms,
                    insufficient_evidence=True,
                    insufficient_evidence_reason=f"Execution failed: {exc_type_name}",
                )

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return self.expected_output_schema(
            agent_name=self.name,
            status=AgentStatus.FAILED,
            confidence=0.0,
            error_message=f"Exhausted retries: {str(last_exception)}",
            execution_duration_ms=duration_ms,
            insufficient_evidence=True,
            insufficient_evidence_reason="Retries exhausted",
        )
