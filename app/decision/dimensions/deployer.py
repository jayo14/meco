"""
Wallet and Deployer Risk Dimension Evaluator.
Measures insider concentration, whale dominance, deployer track record, and cabal risk.
Note: In this dimension, a higher score represents HIGHER RISK (danger).
"""
from datetime import datetime, timezone
from typing import Any

from app.agents.base import EvidenceItem
from app.decision.config import DecisionEngineConfig
from app.decision.dimensions.base import BaseDimensionEvaluator
from app.decision.models import DecisionDimension, DimensionScore, TokenDecisionInput


class WalletDeployerRiskEvaluator(BaseDimensionEvaluator):
    """
    Evaluates wallet distribution and deployer risk (0 = completely safe, 100 = extreme danger):
    - Top 10 non-pool holder concentration
    - Single largest holder dominance
    - Deployer retained holding percentage
    - Deployer history (prior rug pulls, wash trading, blacklists)
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

        holders = input_data.holder_distribution or {}
        deployer = input_data.deployer_intelligence or {}
        sec = input_data.security_findings or {}

        # 1. Top 10 Holder Concentration Risk (0-100)
        top_10_pct = float(holders.get("top_10_percentage") or sec.get("top_10_holder_percent") or 0.0)
        if top_10_pct > 80.0:
            top_10_risk = 90.0 + (top_10_pct - 80.0) * 0.5
        elif top_10_pct > 50.0:
            top_10_risk = 40.0 + ((top_10_pct - 50.0) / 30.0) * 50.0
        elif top_10_pct > 20.0:
            top_10_risk = 15.0 + ((top_10_pct - 20.0) / 30.0) * 25.0
        else:
            top_10_risk = max(5.0, top_10_pct * 0.75)
        components["top_10_concentration_risk"] = round(min(100.0, top_10_risk), 2)
        confidences.append(0.85)

        # 2. Single Largest Holder Dominance Risk (0-100)
        max_single = float(holders.get("max_single_holder_pct") or 0.0)
        if max_single > 40.0:
            whale_risk = 95.0
        elif max_single > 20.0:
            whale_risk = 60.0 + ((max_single - 20.0) / 20.0) * 35.0
        elif max_single > 10.0:
            whale_risk = 30.0 + ((max_single - 10.0) / 10.0) * 30.0
        else:
            whale_risk = max(5.0, max_single * 2.0)
        components["whale_dominance_risk"] = round(min(100.0, whale_risk), 2)
        confidences.append(0.8)

        # 3. Deployer Retained Holding Risk (0-100)
        deployer_holding = float(deployer.get("deployer_holding_pct") or holders.get("deployer_holding_pct") or 0.0)
        if deployer_holding > 30.0:
            dep_holding_risk = 95.0
        elif deployer_holding > 10.0:
            dep_holding_risk = 50.0 + ((deployer_holding - 10.0) / 20.0) * 45.0
        elif deployer_holding > 2.0:
            dep_holding_risk = 20.0 + ((deployer_holding - 2.0) / 8.0) * 30.0
        else:
            dep_holding_risk = 5.0
        components["deployer_holding_risk"] = round(min(100.0, dep_holding_risk), 2)
        confidences.append(0.85)

        # 4. Deployer Track Record & History (0-100)
        prior_rugs = int(deployer.get("known_rug_count") or deployer.get("prior_rugs", 0))
        is_blacklisted = bool(deployer.get("is_blacklisted", False))
        wash_score = float(deployer.get("wash_trading_score") or 0.0)

        if prior_rugs > 0 or is_blacklisted:
            track_risk = 100.0
            evidence.append(
                EvidenceItem(
                    source="deployer_intelligence",
                    timestamp=as_of,
                    reference=f"deployer:{deployer.get('address')}",
                    details={"prior_rugs": prior_rugs, "is_blacklisted": is_blacklisted},
                )
            )
        else:
            total_deployed = int(deployer.get("total_deployed_tokens") or 1)
            # Fresh new deployer has mild uncertainty (30 pts); seasoned clean deployer lower (15 pts)
            track_risk = max(10.0, min(80.0, 30.0 + (wash_score * 50.0)))
        components["deployer_history_risk"] = round(track_risk, 2)
        confidences.append(0.8)

        # Total Wallet & Deployer Risk (Higher = DANGER)
        total_risk = round(
            0.30 * components["top_10_concentration_risk"]
            + 0.25 * components["whale_dominance_risk"]
            + 0.25 * components["deployer_holding_risk"]
            + 0.20 * components["deployer_history_risk"],
            2,
        )

        overall_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.5
        rationale = (
            f"Wallet/deployer risk score {total_risk:.1f}/100. Top 10 concentration ({components['top_10_concentration_risk']:.1f}), "
            f"whale dominance ({components['whale_dominance_risk']:.1f}), deployer holding ({components['deployer_holding_risk']:.1f}), "
            f"and deployer track record ({components['deployer_history_risk']:.1f})."
        )

        return DimensionScore(
            dimension=DecisionDimension.WALLET_DEPLOYER_RISK,
            score=total_risk,
            confidence=overall_conf,
            components=components,
            rationale=rationale,
            evidence_sources=evidence,
        )
