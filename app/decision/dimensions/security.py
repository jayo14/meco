"""
Security Risk Dimension Evaluator.
Measures contract, authority, and protocol safety.
Note: In this dimension, a higher score represents HIGHER RISK (danger).
"""
from datetime import datetime, timezone
from typing import Any

from app.agents.base import EvidenceItem
from app.decision.config import DecisionEngineConfig
from app.decision.dimensions.base import BaseDimensionEvaluator
from app.decision.models import DecisionDimension, DimensionScore, TokenDecisionInput


class SecurityRiskEvaluator(BaseDimensionEvaluator):
    """
    Evaluates security risk dimension (0 = completely safe, 100 = extreme danger):
    - Mint authority status
    - Freeze authority status
    - Honeypot and transfer tax indicators
    - Metadata mutability
    - Risk specialist agent findings & soft warnings
    """

    def evaluate(
        self,
        input_data: TokenDecisionInput,
        config: DecisionEngineConfig,
        as_of: datetime,
    ) -> DimensionScore:
        components: dict[str, float] = {}
        evidence: list[EvidenceItem] = []
        confidences: list[float] = []

        sec = input_data.security_findings or {}
        risk_agent = input_data.risk_agent_output

        # 1. Authority Risk (0-100)
        mint_auth = sec.get("mint_authority")
        freeze_auth = sec.get("freeze_authority")
        has_mint = sec.get("has_mint_authority", False) or (mint_auth is not None and str(mint_auth).strip() != "")
        has_freeze = sec.get("has_freeze_authority", False) or (freeze_auth is not None and str(freeze_auth).strip() != "")

        auth_score = 0.0
        if has_mint:
            auth_score += 60.0
        if has_freeze:
            auth_score += 40.0
        auth_score = min(100.0, auth_score)
        components["authority_risk"] = round(auth_score, 2)
        confidences.append(0.95)

        if has_mint or has_freeze:
            evidence.append(
                EvidenceItem(
                    source="security_profile",
                    timestamp=as_of,
                    reference=f"mint:{input_data.mint_address}",
                    details={"has_mint": has_mint, "has_freeze": has_freeze},
                )
            )

        # 2. Honeypot & Tax Risk (0-100)
        is_honeypot = bool(sec.get("is_honeypot") or sec.get("honeypot_risk"))
        transfer_fee = float(sec.get("transfer_fee_bps") or 0.0)
        if is_honeypot:
            honeypot_score = 100.0
        elif transfer_fee > 500:  # > 5% tax
            honeypot_score = 75.0
        elif transfer_fee > 0:
            honeypot_score = 30.0
        else:
            honeypot_score = 0.0
        components["honeypot_tax_risk"] = round(honeypot_score, 2)
        confidences.append(0.9)

        # 3. Metadata & Extension Risk (0-100)
        is_mutable = bool(sec.get("is_mutable", True))
        is_token_2022 = bool(sec.get("is_token_2022", False))
        meta_score = 0.0
        if is_mutable:
            meta_score += 25.0
        if is_token_2022:
            # Token2022 without fees is modest risk, with non-standard extensions is higher
            meta_score += 15.0
        components["metadata_risk"] = round(meta_score, 2)
        confidences.append(0.8)

        # 4. Specialist Risk Agent Findings (0-100)
        if risk_agent and risk_agent.status.value == "completed":
            hard_count = len(risk_agent.hard_risks)
            soft_count = len(risk_agent.soft_warnings)
            agent_risk = min(100.0, (hard_count * 50.0) + (soft_count * 15.0))
            confidences.append(risk_agent.confidence)
            evidence.extend(risk_agent.evidence_references[:2])
        else:
            agent_risk = 25.0
            confidences.append(0.4)
        components["risk_agent_findings"] = round(agent_risk, 2)

        # Total Security Risk Score (Higher = DANGER)
        total_risk = round(
            0.40 * components["authority_risk"]
            + 0.30 * components["honeypot_tax_risk"]
            + 0.10 * components["metadata_risk"]
            + 0.20 * components["risk_agent_findings"],
            2,
        )

        overall_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.5
        rationale = (
            f"Security risk score {total_risk:.1f}/100. Authority risk ({components['authority_risk']:.1f}), "
            f"honeypot/tax ({components['honeypot_tax_risk']:.1f}), metadata mutability ({components['metadata_risk']:.1f}), "
            f"and specialist risk agent findings ({components['risk_agent_findings']:.1f})."
        )

        return DimensionScore(
            dimension=DecisionDimension.SECURITY_RISK,
            score=total_risk,
            confidence=overall_conf,
            components=components,
            rationale=rationale,
            evidence_sources=evidence,
        )
