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
from app.agents.llm.prompts import RESEARCH_AGENT_PROMPT_V1, RESEARCH_SYSTEM_PROMPT
from app.agents.llm.sanitizer import wrap_untrusted_data

logger = logging.getLogger("meco.agents.research")


class ResearchAgentOutput(AgentOutput):
    model_config = ConfigDict(extra="ignore")

    agent_name: str = "research"
    deployer_summary: dict[str, Any] = Field(default_factory=dict)
    project_presence: dict[str, Any] = Field(default_factory=dict)
    ecosystem_context: dict[str, Any] = Field(default_factory=dict)
    related_wallets: list[str] = Field(default_factory=list)


class LLMResearchSynthesis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str = ""
    confidence: float = 0.8
    inferences: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    unanswered_questions: list[str] = Field(default_factory=list)


class ResearchAgent(BaseAgent):
    """
    Specialist agent investigating token metadata, deployer track record,
    related wallets, web presence, ecosystem context, and historical performance.
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
        return "research"

    @property
    def responsibility(self) -> str:
        return (
            "Investigate token identity, metadata authenticity, deployer launch history, "
            "related wallet clusters, public project presence, and ecosystem context."
        )

    @property
    def required_input(self) -> list[str]:
        return ["mint_address"]

    @property
    def available_tools(self) -> list[str]:
        return [
            "token_metadata_resolver",
            "deployer_history_analyzer",
            "wallet_cluster_tracker",
            "ecosystem_context_resolver",
        ]

    @property
    def expected_output_schema(self) -> type[ResearchAgentOutput]:
        return ResearchAgentOutput

    @property
    def evidence_requirements(self) -> list[str]:
        return [
            "metadata_provenance",
            "deployer_wallet_record",
            "ecosystem_launchpad_context",
        ]

    async def investigate(self, context: InvestigationContext) -> ResearchAgentOutput:
        now_utc = datetime.now(timezone.utc)
        mint_address = context.mint_address
        profile = context.profile

        # Check for insufficient evidence condition
        if profile is None:
            return ResearchAgentOutput(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                confidence=0.0,
                insufficient_evidence=True,
                insufficient_evidence_reason="No canonical profile or discovery history exists for mint.",
                unanswered_questions=["Token not found in canonical registry or external explorers."],
            )

        # Profile can be a TokenIntelligenceProfile dataclass or a dict
        profile_dict = profile.to_dict() if hasattr(profile, "to_dict") else dict(profile)

        metadata = profile_dict.get("metadata") or {}
        security = profile_dict.get("security") or {}
        holders = profile_dict.get("holders") or {}
        liquidity = profile_dict.get("liquidity") or {}
        sources = profile_dict.get("sources") or []

        findings: list[AgentFinding] = []
        evidence_references: list[EvidenceItem] = []
        unanswered_questions: list[str] = []

        # 1. Token Metadata Facts
        token_name = metadata.get("name") or profile_dict.get("name")
        symbol = metadata.get("symbol") or profile_dict.get("symbol")
        decimals = profile_dict.get("decimals")
        total_supply = profile_dict.get("total_supply")

        meta_ref = metadata.get("metadata_uri") or f"mint:{mint_address}"
        meta_ev = EvidenceItem(
            source="metadata_resolver",
            timestamp=now_utc,
            reference=meta_ref,
            details={"name": token_name, "symbol": symbol, "decimals": decimals},
        )
        evidence_references.append(meta_ev)

        findings.append(
            AgentFinding(
                type=FindingType.VERIFIED_FACT,
                title="Token Identity Registered",
                statement=f"Token identified as {token_name or 'Unknown'} (${symbol or 'N/A'}) with {decimals} decimals and total supply {total_supply}.",
                confidence=1.0,
                evidence_sources=[meta_ev],
                metadata={"mint": mint_address, "name": token_name, "symbol": symbol},
            )
        )

        # 2. Deployer History & Track Record
        deployer_address = holders.get("deployer_address") or security.get("mint_authority")
        deployer_summary = {
            "deployer_address": deployer_address,
            "deployer_holding_pct": holders.get("deployer_holding_pct", 0.0),
            "previous_launches_count": 0,
            "known_rugs_count": 0,
            "status": "unverified",
        }

        # Check history_data passed in context
        history_data = context.history_data or {}
        deployer_past_mints = history_data.get("deployer_past_mints", [])

        if deployer_address:
            deployer_ev = EvidenceItem(
                source="solana_rpc_deployer_lookup",
                timestamp=now_utc,
                reference=f"deployer:{deployer_address}",
                details={"deployer": deployer_address, "past_mints_count": len(deployer_past_mints)},
            )
            evidence_references.append(deployer_ev)

            if deployer_past_mints:
                deployer_summary["previous_launches_count"] = len(deployer_past_mints)
                past_rugs = [m for m in deployer_past_mints if m.get("rugged") or m.get("is_honeypot")]
                deployer_summary["known_rugs_count"] = len(past_rugs)
                deployer_summary["status"] = "repeat_creator"

                findings.append(
                    AgentFinding(
                        type=FindingType.STATISTICAL_OBSERVATION,
                        title="Deployer Previous Launches Observed",
                        statement=f"Deployer {deployer_address[:6]}... has deployed {len(deployer_past_mints)} tokens in history ({len(past_rugs)} flagged as failed/rugged).",
                        confidence=0.95,
                        evidence_sources=[deployer_ev],
                        metadata={"previous_mints": len(deployer_past_mints), "rugs": len(past_rugs)},
                    )
                )
            else:
                findings.append(
                    AgentFinding(
                        type=FindingType.STATISTICAL_OBSERVATION,
                        title="Fresh Deployer Wallet",
                        statement=f"Deployer {deployer_address[:6]}... has no documented previous token deployments.",
                        confidence=0.8,
                        evidence_sources=[deployer_ev],
                    )
                )
        else:
            findings.append(
                AgentFinding(
                    type=FindingType.MISSING_INFORMATION,
                    title="Deployer Address Unknown",
                    statement="Deployer address could not be authoritatively resolved from mint genesis or largest accounts.",
                    confidence=1.0,
                    evidence_sources=[meta_ev],
                )
            )
            unanswered_questions.append("Who is the original deployer wallet of this mint?")

        # 3. Project Public Presence
        website = metadata.get("website")
        twitter = metadata.get("twitter")
        telegram = metadata.get("telegram")
        discord = metadata.get("discord")
        launchpad = metadata.get("launchpad") or "unknown"

        presence_info = {
            "website": website,
            "twitter": twitter,
            "telegram": telegram,
            "discord": discord,
            "launchpad": launchpad,
            "has_socials": bool(website or twitter or telegram or discord),
        }

        if presence_info["has_socials"]:
            findings.append(
                AgentFinding(
                    type=FindingType.VERIFIED_FACT,
                    title="Public Project Presence Identified",
                    statement=f"Token maintains external links: website={bool(website)}, twitter={bool(twitter)}, telegram={bool(telegram)}.",
                    confidence=1.0,
                    evidence_sources=[meta_ev],
                    metadata=presence_info,
                )
            )
        else:
            findings.append(
                AgentFinding(
                    type=FindingType.MISSING_INFORMATION,
                    title="No Verifiable Project Presence",
                    statement="Token metadata specifies no website, Twitter/X handle, or official Telegram channel.",
                    confidence=0.95,
                    evidence_sources=[meta_ev],
                )
            )
            unanswered_questions.append("Does the project have an official public development team or communication channel?")

        # 4. Ecosystem & Launch Context
        primary_dex = liquidity.get("primary_dex_id") or "unknown"
        pair_addr = liquidity.get("primary_pair_address")
        ecosystem_info = {
            "primary_dex": primary_dex,
            "primary_pair": pair_addr,
            "launchpad": launchpad,
            "discovery_sources": [s.get("source") for s in sources],
        }

        eco_ev = EvidenceItem(
            source="ecosystem_context_resolver",
            timestamp=now_utc,
            reference=f"pair:{pair_addr or 'none'}",
            details=ecosystem_info,
        )
        evidence_references.append(eco_ev)

        findings.append(
            AgentFinding(
                type=FindingType.STATISTICAL_OBSERVATION,
                title="Ecosystem Trading Architecture",
                statement=f"Trading primary pool routed on {primary_dex} (launchpad: {launchpad}). Initial discovery sources: {', '.join(ecosystem_info['discovery_sources']) or 'unknown'}.",
                confidence=0.95,
                evidence_sources=[eco_ev],
                metadata=ecosystem_info,
            )
        )

        # 5. Related Wallets & Insider Footprint
        top_holders = holders.get("top_holders") or []
        related_wallets = []
        for h in top_holders[:5]:
            addr = h.get("address")
            if addr and addr != deployer_address:
                related_wallets.append(addr)

        if related_wallets:
            findings.append(
                AgentFinding(
                    type=FindingType.INFERENCE,
                    title="Top Wallet Cluster Isolated",
                    statement=f"Identified {len(related_wallets)} primary non-deployer wallets holding substantial supply for cluster correlation.",
                    confidence=0.75,
                    evidence_sources=[eco_ev],
                    metadata={"wallets": related_wallets},
                )
            )

        # 6. LLM Synthesis (Protected with Untrusted Data Wrappers)
        llm_inferences: list[str] = []
        llm_hypotheses: list[str] = []
        model_name = None
        provider = None
        tokens_used = None

        if self.config.allow_llm:
            # Package verified findings and untrusted metadata safely
            clean_meta_block = wrap_untrusted_data(metadata, source_label="token_metadata")
            prompt_input = (
                f"Token: {token_name} ({symbol})\n"
                f"Mint: {mint_address}\n"
                f"Deployer: {deployer_address or 'Unknown'}\n"
                f"Launchpad: {launchpad}\n"
                f"External Presence: {presence_info}\n"
                f"Untrusted Metadata:\n{clean_meta_block}\n"
            )

            llm_resp = await self.llm.generate_structured(
                system_prompt=RESEARCH_SYSTEM_PROMPT,
                user_prompt=prompt_input,
                response_schema=LLMResearchSynthesis,
                prompt_version=RESEARCH_AGENT_PROMPT_V1,
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
                            title="Research Synthesis Inference",
                            statement=inf,
                            confidence=0.7,
                            evidence_sources=[meta_ev],
                        )
                    )
                for hyp in llm_resp.parsed.hypotheses:
                    findings.append(
                        AgentFinding(
                            type=FindingType.HYPOTHESIS,
                            title="Ecosystem Hypothesis",
                            statement=hyp,
                            confidence=0.5,
                            evidence_sources=[meta_ev],
                        )
                    )
                unanswered_questions.extend(llm_resp.parsed.unanswered_questions)

        # Calculate overall confidence
        confidence = 0.85 if deployer_address and presence_info["has_socials"] else 0.65

        return ResearchAgentOutput(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            confidence=confidence,
            insufficient_evidence=False,
            findings=findings,
            evidence_references=evidence_references,
            unanswered_questions=list(dict.fromkeys(unanswered_questions)),
            deployer_summary=deployer_summary,
            project_presence=presence_info,
            ecosystem_context=ecosystem_info,
            related_wallets=related_wallets,
            model_provider=provider,
            model_name=model_name,
            prompt_version=RESEARCH_AGENT_PROMPT_V1,
            tokens_used=tokens_used,
        )
