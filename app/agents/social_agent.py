from datetime import datetime, timezone
import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.base import (
    AgentConfig,
    AgentFinding,
    AgentOutput,
    AgentStatus,
    BaseAgent,
    EvidenceItem,
    FindingType,
    InvestigationContext,
)
from app.agents.llm.client import LLMClient
from app.agents.llm.prompts import SOCIAL_AGENT_PROMPT_V1, SOCIAL_SYSTEM_PROMPT
from app.agents.llm.sanitizer import wrap_untrusted_data

logger = logging.getLogger("meco.agents.social")


class SocialIntelligenceOutput(AgentOutput):
    model_config = ConfigDict(extra="ignore")

    agent_name: str = "social"
    social_traction: str = "NONE"  # NONE, LOW, MODERATE, HIGH, VIRAL
    narratives: list[str] = Field(default_factory=list)
    mention_velocity: float = 0.0
    unique_authors: int = 0
    author_concentration: float = 0.0
    spam_score: float = 0.0
    sentiment_positive: float = 0.0
    sentiment_negative: float = 0.0
    sentiment_neutral: float = 1.0
    social_market_correlation: dict[str, Any] = Field(default_factory=dict)


class LLMSocialSynthesis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str = ""
    narrative_evaluation: str = ""
    inferences: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    unanswered_questions: list[str] = Field(default_factory=list)


class SocialIntelligenceAgent(BaseAgent):
    """
    Social Intelligence Specialist Agent.
    Evaluates narrative relevance, mention velocity, unique author diversity,
    sentiment, spam indicators, and social-to-market correlation.
    Reports lack of traction when social presence is minimal or absent.
    """

    def __init__(
        self,
        config: AgentConfig | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        super().__init__(config)
        self.llm = llm_client or LLMClient()

    @property
    def name(self) -> str:
        return "social"

    @property
    def responsibility(self) -> str:
        return (
            "Evaluate social narrative relevance, mention velocity, participant diversity, "
            "attention acceleration, sentiment, spam/bot concentration, and social-to-market correlation."
        )

    @property
    def required_input(self) -> list[str]:
        return ["mint_address"]

    @property
    def available_tools(self) -> list[str]:
        return [
            "social_metrics_snapshot_reader",
            "narrative_relevance_classifier",
            "author_concentration_evaluator",
            "social_market_correlator",
        ]

    @property
    def expected_output_schema(self) -> type[SocialIntelligenceOutput]:
        return SocialIntelligenceOutput

    @property
    def evidence_requirements(self) -> list[str]:
        return [
            "social_metrics_snapshot",
            "narrative_association_evidence",
            "social_post_sample",
        ]

    async def investigate(self, context: InvestigationContext) -> SocialIntelligenceOutput:
        now_utc = datetime.now(timezone.utc)
        mint_address = context.mint_address
        social_data = context.social_data or {}
        profile = context.profile

        findings: list[AgentFinding] = []
        evidence_references: list[EvidenceItem] = []
        unanswered_questions: list[str] = []

        # 1. Check for absence of social data / no traction
        mention_count = int(social_data.get("mention_count", 0))
        recent_posts = social_data.get("recent_posts", [])
        metrics_snapshot = social_data.get("metrics_snapshot", {})

        if mention_count == 0 and not recent_posts and not metrics_snapshot:
            ev_missing = EvidenceItem(
                source="social_ingestion_index",
                timestamp=now_utc,
                reference=f"social_query:{mint_address}",
                details={"mention_count": 0},
            )
            evidence_references.append(ev_missing)

            findings.append(
                AgentFinding(
                    type=FindingType.VERIFIED_FACT,
                    title="No Credible Social Traction",
                    statement=f"Token {mint_address[:8]}... has zero recorded mentions, community posts, or narrative signals across monitored social channels.",
                    confidence=0.95,
                    evidence_sources=[ev_missing],
                )
            )
            findings.append(
                AgentFinding(
                    type=FindingType.INFERENCE,
                    title="Absence of Organic Community",
                    statement="Trading activity is unbacked by public social dialogue, indicating purely algorithmic or bot-driven volume.",
                    confidence=0.85,
                    evidence_sources=[ev_missing],
                )
            )

            return SocialIntelligenceOutput(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                confidence=0.9,
                insufficient_evidence=False,
                social_traction="NONE",
                findings=findings,
                evidence_references=evidence_references,
                unanswered_questions=["Does this token have an active community or marketing push planned?"],
                narratives=[],
                mention_velocity=0.0,
                unique_authors=0,
                author_concentration=0.0,
                spam_score=0.0,
            )

        # 2. Process Available Social Metrics
        ev_soc = EvidenceItem(
            source="social_metrics_evaluator",
            timestamp=now_utc,
            reference=f"metrics_snapshot:{mint_address}",
            details=social_data,
        )
        evidence_references.append(ev_soc)

        mention_velocity = float(social_data.get("mention_velocity") or metrics_snapshot.get("mention_velocity", 0.0))
        unique_authors = int(social_data.get("unique_authors_count") or metrics_snapshot.get("unique_authors_count", len({p.get("author_id") for p in recent_posts if p.get("author_id")})))
        author_concentration = float(social_data.get("author_concentration") or metrics_snapshot.get("author_concentration", 0.0))
        spam_score = float(social_data.get("spam_score") or metrics_snapshot.get("spam_score", 0.0))
        pos_sent = float(social_data.get("sentiment_positive", metrics_snapshot.get("sentiment_positive", 0.0)))
        neg_sent = float(social_data.get("sentiment_negative", metrics_snapshot.get("sentiment_negative", 0.0)))
        neu_sent = float(social_data.get("sentiment_neutral", metrics_snapshot.get("sentiment_neutral", 1.0)))
        narratives = list(social_data.get("narratives", []))

        # Evaluate Traction Level
        if mention_velocity > 50.0 and unique_authors > 40:
            social_traction = "VIRAL"
        elif mention_velocity > 15.0 and unique_authors > 15:
            social_traction = "HIGH"
        elif mention_velocity > 2.0 or unique_authors > 5:
            social_traction = "MODERATE"
        else:
            social_traction = "LOW"

        # 3. Correlation with Market Activity
        market_data = context.market_data or {}
        volume_5m = float(market_data.get("volume_5m", 0.0))
        social_market_corr = {
            "mention_velocity": mention_velocity,
            "market_volume_5m": volume_5m,
            "is_social_preceding_market": mention_velocity > 5.0 and volume_5m < 5000.0,
            "is_market_preceding_social": volume_5m > 20000.0 and mention_velocity < 2.0,
        }

        # 4. Verified Facts and Statistical Observations
        findings.append(
            AgentFinding(
                type=FindingType.VERIFIED_FACT,
                title="Social Mention Volume Recorded",
                statement=f"Detected {mention_count} total mentions with velocity of {mention_velocity:.2f} posts/hour across {unique_authors} unique accounts.",
                confidence=1.0,
                evidence_sources=[ev_soc],
                metadata={"velocity": mention_velocity, "unique_authors": unique_authors},
            )
        )

        if author_concentration > 0.4:
            findings.append(
                AgentFinding(
                    type=FindingType.STATISTICAL_OBSERVATION,
                    title="High Author Concentration (Astroturfing Alert)",
                    statement=f"Author Herfindahl concentration is {author_concentration:.2f}. A small group of accounts accounts for a disproportionate share of mentions.",
                    confidence=0.9,
                    evidence_sources=[ev_soc],
                )
            )

        if spam_score > 0.5:
            findings.append(
                AgentFinding(
                    type=FindingType.STATISTICAL_OBSERVATION,
                    title="Elevated Spam and Bot Indicators",
                    statement=f"Automated spam score reached {spam_score:.2f}, indicating bot activity, repeated copy-paste text, or coordinated raid patterns.",
                    confidence=0.88,
                    evidence_sources=[ev_soc],
                )
            )

        if narratives:
            findings.append(
                AgentFinding(
                    type=FindingType.INFERENCE,
                    title="Active Narrative Association",
                    statement=f"Token aligns with identified meta-narratives: {', '.join(narratives)}.",
                    confidence=0.85,
                    evidence_sources=[ev_soc],
                    metadata={"narratives": narratives},
                )
            )

        # 5. LLM Qualitative Synthesis (using sanitized external text)
        model_name = None
        provider = None
        tokens_used = None

        if self.config.allow_llm:
            sanitized_posts_block = wrap_untrusted_data(
                [p.get("content", "") for p in recent_posts[:5]],
                source_label="recent_social_posts",
            )
            prompt_input = (
                f"Mint: {mint_address}\n"
                f"Traction Level: {social_traction}\n"
                f"Mention Velocity: {mention_velocity}/hr\n"
                f"Unique Authors: {unique_authors}\n"
                f"Spam Score: {spam_score}\n"
                f"Identified Narratives: {narratives}\n"
                f"Untrusted Social Posts Sample:\n{sanitized_posts_block}\n"
            )

            llm_resp = await self.llm.generate_structured(
                system_prompt=SOCIAL_SYSTEM_PROMPT,
                user_prompt=prompt_input,
                response_schema=LLMSocialSynthesis,
                prompt_version=SOCIAL_AGENT_PROMPT_V1,
                model_override=self.config.model_name,
            )

            if llm_resp.parsed:
                model_name = llm_resp.model
                provider = llm_resp.provider
                tokens_used = llm_resp.usage.total_tokens

                for inf in llm_resp.parsed.inferences:
                    findings.append(
                        AgentFinding(
                            type=FindingType.INFERENCE,
                            title="Social Narrative Inference",
                            statement=inf,
                            confidence=0.8,
                            evidence_sources=[ev_soc],
                        )
                    )
                for hyp in llm_resp.parsed.hypotheses:
                    findings.append(
                        AgentFinding(
                            type=FindingType.HYPOTHESIS,
                            title="Audience Engagement Hypothesis",
                            statement=hyp,
                            confidence=0.6,
                            evidence_sources=[ev_soc],
                        )
                    )
                unanswered_questions.extend(llm_resp.parsed.unanswered_questions)

        confidence = 0.9 if unique_authors > 3 else 0.75

        return SocialIntelligenceOutput(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            confidence=confidence,
            insufficient_evidence=False,
            social_traction=social_traction,
            findings=findings,
            evidence_references=evidence_references,
            unanswered_questions=list(dict.fromkeys(unanswered_questions)),
            narratives=narratives,
            mention_velocity=mention_velocity,
            unique_authors=unique_authors,
            author_concentration=author_concentration,
            spam_score=spam_score,
            sentiment_positive=pos_sent,
            sentiment_negative=neg_sent,
            sentiment_neutral=neu_sent,
            social_market_correlation=social_market_corr,
            model_provider=provider,
            model_name=model_name,
            prompt_version=SOCIAL_AGENT_PROMPT_V1,
            tokens_used=tokens_used,
        )
