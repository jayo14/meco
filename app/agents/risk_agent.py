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
    HardRiskCondition,
    InvestigationContext,
    SoftWarning,
)
from app.agents.llm.client import LLMClient
from app.agents.llm.prompts import RISK_AGENT_PROMPT_V1, RISK_SYSTEM_PROMPT
from app.agents.llm.sanitizer import wrap_untrusted_data

logger = logging.getLogger("meco.agents.risk")


class RiskAgentOutput(AgentOutput):
    model_config = ConfigDict(extra="ignore")

    agent_name: str = "risk"
    deterministic_risk_score: float = 0.0
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    can_exit_safely: bool = True
    hard_risks: list[HardRiskCondition] = Field(default_factory=list)
    soft_warnings: list[SoftWarning] = Field(default_factory=list)
    insider_indicators: dict[str, Any] = Field(default_factory=dict)


class LLMRiskNotes(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str = ""
    qualitative_observations: list[str] = Field(default_factory=list)
    unanswered_questions: list[str] = Field(default_factory=list)


class RiskAgent(BaseAgent):
    """
    Independent Risk Assessment Specialist Agent.
    Strictly enforces deterministic security and liquidity guardrails.
    LLM reasoning cannot override deterministic risk classifications.
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
        return "risk"

    @property
    def responsibility(self) -> str:
        return (
            "Evaluate token security authorities, token extensions, liquidity depth and drain risks, "
            "holder concentration, deployer holdings, insider wallet clustering, and exit market viability."
        )

    @property
    def required_input(self) -> list[str]:
        return ["mint_address"]

    @property
    def available_tools(self) -> list[str]:
        return [
            "solana_rpc_authority_checker",
            "token_extension_analyzer",
            "holder_concentration_analyzer",
            "liquidity_depth_calculator",
            "insider_wallet_clustering_tool",
        ]

    @property
    def expected_output_schema(self) -> type[RiskAgentOutput]:
        return RiskAgentOutput

    @property
    def evidence_requirements(self) -> list[str]:
        return [
            "solana_rpc_mint_decode",
            "largest_accounts_snapshot",
            "market_liquidity_snapshot",
        ]

    async def investigate(self, context: InvestigationContext) -> RiskAgentOutput:
        now_utc = datetime.now(timezone.utc)
        mint_address = context.mint_address
        profile = context.profile

        if profile is None:
            return RiskAgentOutput(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                confidence=0.0,
                insufficient_evidence=True,
                insufficient_evidence_reason="Token profile is missing. Cannot perform deterministic risk evaluation.",
                unanswered_questions=["Token security and liquidity data unavailable."],
            )

        profile_dict = profile.to_dict() if hasattr(profile, "to_dict") else dict(profile)
        security = profile_dict.get("security") or {}
        holders = profile_dict.get("holders") or {}
        liquidity = profile_dict.get("liquidity") or {}

        findings: list[AgentFinding] = []
        evidence_references: list[EvidenceItem] = []
        hard_risks: list[HardRiskCondition] = []
        soft_warnings: list[SoftWarning] = []
        unanswered_questions: list[str] = []

        # =========================================================================
        # 1. Deterministic Security & Authority Evaluation (Hard Stops)
        # =========================================================================
        sec_ev = EvidenceItem(
            source="solana_rpc_mint_decode",
            timestamp=now_utc,
            reference=f"mint_authority:{mint_address}",
            details=security,
        )
        evidence_references.append(sec_ev)

        # Check Mint Authority
        mint_auth = security.get("mint_authority")
        is_mintable = security.get("is_mintable", bool(mint_auth))
        if is_mintable and mint_auth:
            hard = HardRiskCondition(
                code="MINT_AUTHORITY_ACTIVE",
                description=f"Active mint authority retained by {mint_auth}. Supply can be inflated arbitrarily.",
                severity="critical",
                evidence=sec_ev,
            )
            hard_risks.append(hard)
            findings.append(
                AgentFinding(
                    type=FindingType.VERIFIED_FACT,
                    title="Active Mint Authority (Hard Risk)",
                    statement=f"Mint authority is active ({mint_auth}). Creator can mint infinite tokens.",
                    confidence=1.0,
                    evidence_sources=[sec_ev],
                    metadata={"mint_authority": mint_auth},
                )
            )
        else:
            findings.append(
                AgentFinding(
                    type=FindingType.VERIFIED_FACT,
                    title="Mint Authority Renounced",
                    statement="Mint authority is null/revoked. Additional token supply cannot be minted.",
                    confidence=1.0,
                    evidence_sources=[sec_ev],
                )
            )

        # Check Freeze Authority
        freeze_auth = security.get("freeze_authority")
        is_freezable = security.get("is_freezable", bool(freeze_auth))
        if is_freezable and freeze_auth:
            hard = HardRiskCondition(
                code="FREEZE_AUTHORITY_ACTIVE",
                description=f"Active freeze authority retained by {freeze_auth}. Token transfers can be blocked.",
                severity="critical",
                evidence=sec_ev,
            )
            hard_risks.append(hard)
            findings.append(
                AgentFinding(
                    type=FindingType.VERIFIED_FACT,
                    title="Active Freeze Authority (Hard Risk)",
                    statement=f"Freeze authority is active ({freeze_auth}). Token accounts can be blacklisted.",
                    confidence=1.0,
                    evidence_sources=[sec_ev],
                    metadata={"freeze_authority": freeze_auth},
                )
            )
        else:
            findings.append(
                AgentFinding(
                    type=FindingType.VERIFIED_FACT,
                    title="Freeze Authority Renounced",
                    statement="Freeze authority is null/revoked. Token accounts cannot be frozen by authority.",
                    confidence=1.0,
                    evidence_sources=[sec_ev],
                )
            )

        # Check Token-2022 Extensions & Fees
        perm_delegate = security.get("permanent_delegate")
        if perm_delegate:
            hard = HardRiskCondition(
                code="PERMANENT_DELEGATE_ACTIVE",
                description=f"Token has permanent delegate {perm_delegate} enabled. Assets can be confiscated.",
                severity="critical",
                evidence=sec_ev,
            )
            hard_risks.append(hard)
            findings.append(
                AgentFinding(
                    type=FindingType.VERIFIED_FACT,
                    title="Permanent Delegate Enabled (Hard Risk)",
                    statement=f"Permanent delegate {perm_delegate} can transfer or burn tokens from any account.",
                    confidence=1.0,
                    evidence_sources=[sec_ev],
                )
            )

        has_transfer_fee = security.get("has_transfer_fee", False)
        fee_bps = security.get("transfer_fee_basis_points", 0)
        if has_transfer_fee and fee_bps > 1000:  # > 10%
            hard = HardRiskCondition(
                code="EXCESSIVE_TRANSFER_FEE",
                description=f"High transfer fee of {fee_bps / 100}% configured on token transfers.",
                severity="critical",
                evidence=sec_ev,
            )
            hard_risks.append(hard)
        elif has_transfer_fee and fee_bps > 0:
            soft = SoftWarning(
                code="TRANSFER_FEE_ENABLED",
                description=f"Token applies a {fee_bps / 100}% fee on each transaction.",
                severity="warning",
                evidence=sec_ev,
            )
            soft_warnings.append(soft)

        # =========================================================================
        # 2. Holder Concentration & Deployer Holdings
        # =========================================================================
        holder_ev = EvidenceItem(
            source="solana_rpc_largest_accounts",
            timestamp=now_utc,
            reference=f"holders:{mint_address}",
            details=holders,
        )
        evidence_references.append(holder_ev)

        deployer_holding_pct = float(holders.get("deployer_holding_pct") or 0.0)
        top10_concentration = float(holders.get("top10_concentration_pct") or 0.0)
        top20_concentration = float(holders.get("top20_concentration_pct") or 0.0)
        top_holders = holders.get("top_holders") or []

        if deployer_holding_pct > 35.0:
            hard = HardRiskCondition(
                code="DEPLOYER_MAJORITY_HOLDINGS",
                description=f"Deployer wallet retains {deployer_holding_pct:.1f}% of circulating supply.",
                severity="critical",
                evidence=holder_ev,
            )
            hard_risks.append(hard)
            findings.append(
                AgentFinding(
                    type=FindingType.VERIFIED_FACT,
                    title="Excessive Deployer Holdings (Hard Risk)",
                    statement=f"Deployer directly controls {deployer_holding_pct:.1f}% of total supply.",
                    confidence=1.0,
                    evidence_sources=[holder_ev],
                )
            )
        elif deployer_holding_pct > 15.0:
            soft = SoftWarning(
                code="HIGH_DEPLOYER_HOLDING",
                description=f"Deployer wallet holds {deployer_holding_pct:.1f}% of supply.",
                severity="warning",
                evidence=holder_ev,
            )
            soft_warnings.append(soft)

        # Check single non-DEX whale concentration
        largest_holder_pct = 0.0
        if top_holders:
            largest_holder_pct = float(top_holders[0].get("percentage") or 0.0)
            if largest_holder_pct > 60.0:
                hard = HardRiskCondition(
                    code="EXTREME_SINGLE_HOLDER_CONCENTRATION",
                    description=f"Single wallet owns {largest_holder_pct:.1f}% of supply.",
                    severity="critical",
                    evidence=holder_ev,
                )
                hard_risks.append(hard)

        if top10_concentration > 60.0 and not any(h.code == "EXTREME_SINGLE_HOLDER_CONCENTRATION" for h in hard_risks):
            soft_warnings.append(
                SoftWarning(
                    code="ELEVATED_TOP10_CONCENTRATION",
                    description=f"Top 10 holders control {top10_concentration:.1f}% of circulating supply.",
                    severity="warning",
                    evidence=holder_ev,
                )
            )
            findings.append(
                AgentFinding(
                    type=FindingType.STATISTICAL_OBSERVATION,
                    title="Top 10 Holder Concentration High",
                    statement=f"Top 10 wallets account for {top10_concentration:.1f}% of tokens.",
                    confidence=0.95,
                    evidence_sources=[holder_ev],
                )
            )

        # =========================================================================
        # 3. Liquidity Depth, Liquidity Drain, and Exit Feasibility
        # =========================================================================
        liq_ev = EvidenceItem(
            source="dexscreener_snapshot",
            timestamp=now_utc,
            reference=f"pair:{liquidity.get('primary_pair_address', 'none')}",
            details=liquidity,
        )
        evidence_references.append(liq_ev)

        liquidity_usd = float(liquidity.get("liquidity_usd") or 0.0)
        pool_age_seconds = liquidity.get("pool_age_seconds")

        # Inability to exit / minimal liquidity check
        can_exit_safely = True
        if liquidity_usd < 1000.0:
            can_exit_safely = False
            hard = HardRiskCondition(
                code="INSUFFICIENT_LIQUIDITY_DEPTH",
                description=f"Total pool liquidity is ${liquidity_usd:,.2f} USD. Exiting position is virtually impossible without severe price collapse.",
                severity="critical",
                evidence=liq_ev,
            )
            hard_risks.append(hard)
            findings.append(
                AgentFinding(
                    type=FindingType.STATISTICAL_OBSERVATION,
                    title="Illiquid Pool (Hard Risk)",
                    statement=f"Liquidity pool depth of ${liquidity_usd:,.2f} is insufficient to support exits.",
                    confidence=1.0,
                    evidence_sources=[liq_ev],
                )
            )
        elif liquidity_usd < 10000.0:
            soft_warnings.append(
                SoftWarning(
                    code="THIN_LIQUIDITY_BUFFER",
                    description=f"Modest liquidity depth of ${liquidity_usd:,.2f} USD.",
                    severity="warning",
                    evidence=liq_ev,
                )
            )

        if pool_age_seconds is not None and pool_age_seconds < 300:  # < 5 minutes
            soft_warnings.append(
                SoftWarning(
                    code="ULTRA_NEW_POOL",
                    description=f"Trading pool created only {int(pool_age_seconds)}s ago. Vulnerable to early sniper rug or dev dump.",
                    severity="warning",
                    evidence=liq_ev,
                )
            )

        # =========================================================================
        # 4. Insider Wallet Clustering Indicators
        # =========================================================================
        insider_data = {
            "deployer_holding_pct": deployer_holding_pct,
            "top10_concentration_pct": top10_concentration,
            "top20_concentration_pct": top20_concentration,
            "cluster_suspicion_score": round(
                (deployer_holding_pct * 0.4) + (top10_concentration * 0.6) / 100.0, 3
            ),
        }

        # =========================================================================
        # 5. Deterministic Risk Score and Risk Level Calculation
        # =========================================================================
        if hard_risks:
            deterministic_risk_score = 1.0
            risk_level = "CRITICAL"
        else:
            score = 0.1
            score += len(soft_warnings) * 0.15
            if top10_concentration > 40.0:
                score += 0.15
            deterministic_risk_score = min(round(score, 2), 0.85)
            if deterministic_risk_score >= 0.7:
                risk_level = "HIGH"
            elif deterministic_risk_score >= 0.4:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"

        # =========================================================================
        # 6. LLM Qualitative Synthesis (Guaranteed NOT to override deterministic rules)
        # =========================================================================
        model_name = None
        provider = None
        tokens_used = None

        if self.config.allow_llm:
            sanitized_meta = wrap_untrusted_data(profile_dict.get("metadata", {}), "token_metadata")
            prompt_input = (
                f"Token: {profile_dict.get('name')} ({profile_dict.get('symbol')})\n"
                f"Mint: {mint_address}\n"
                f"Deterministic Hard Risks ({len(hard_risks)}): {[h.code for h in hard_risks]}\n"
                f"Soft Warnings ({len(soft_warnings)}): {[w.code for w in soft_warnings]}\n"
                f"Liquidity USD: ${liquidity_usd}\n"
                f"Deployer Holdings: {deployer_holding_pct}%\n"
                f"Top 10 Concentration: {top10_concentration}%\n"
                f"Untrusted Metadata:\n{sanitized_meta}\n"
            )

            llm_resp = await self.llm.generate_structured(
                system_prompt=RISK_SYSTEM_PROMPT,
                user_prompt=prompt_input,
                response_schema=LLMRiskNotes,
                prompt_version=RISK_AGENT_PROMPT_V1,
                model_override=self.config.model_name,
            )

            if llm_resp.parsed:
                model_name = llm_resp.model
                provider = llm_resp.provider
                tokens_used = llm_resp.usage.total_tokens

                for obs in llm_resp.parsed.qualitative_observations:
                    findings.append(
                        AgentFinding(
                            type=FindingType.INFERENCE,
                            title="Risk Specialist Synthesis",
                            statement=obs,
                            confidence=0.75,
                            evidence_sources=[sec_ev],
                        )
                    )
                unanswered_questions.extend(llm_resp.parsed.unanswered_questions)

        # Confidence is high because deterministic checks are on-chain authoritative
        confidence = 0.95

        return RiskAgentOutput(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            confidence=confidence,
            insufficient_evidence=False,
            findings=findings,
            evidence_references=evidence_references,
            unanswered_questions=list(dict.fromkeys(unanswered_questions)),
            hard_risks=hard_risks,
            soft_warnings=soft_warnings,
            deterministic_risk_score=deterministic_risk_score,
            risk_level=risk_level,
            can_exit_safely=can_exit_safely,
            insider_indicators=insider_data,
            model_provider=provider,
            model_name=model_name,
            prompt_version=RISK_AGENT_PROMPT_V1,
            tokens_used=tokens_used,
        )
