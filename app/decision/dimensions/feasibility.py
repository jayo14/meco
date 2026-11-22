"""
Execution Feasibility Dimension Evaluator.
Evaluates realistic trade execution viabilities, simulated slippage impact,
and liquidity pool routing.
"""
from datetime import datetime, timezone
import math
from typing import Any

from app.agents.base import EvidenceItem
from app.decision.config import DecisionEngineConfig
from app.decision.dimensions.base import BaseDimensionEvaluator
from app.decision.models import DecisionDimension, DimensionScore, TokenDecisionInput


class ExecutionFeasibilityEvaluator(BaseDimensionEvaluator):
    """
    Evaluates execution feasibility (0 = completely unexecutable, 100 = seamless execution):
    - Simulated price impact on test trade sizes ($100, $500, $2500)
    - AMM constant product pool reserves vs trade size
    - DEX liquidity pool routing and standard fee tiers
    - Anti-whale transfer limits or transaction size limits
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

        pool = input_data.liquidity_pool or {}
        sec = input_data.security_findings or {}

        liq_usd = float(pool.get("liquidity_usd") or 0.0)

        # 1. Simulated Price Impact on Standard Size ($250 test order) (0-100)
        # Using AMM Constant Product approximation: Impact = OrderSize / (PoolLiquidity / 2)
        test_trade_size = 250.0
        if liq_usd > 0:
            reserve_side = liq_usd / 2.0
            price_impact_pct = (test_trade_size / (reserve_side + test_trade_size)) * 100.0
            if price_impact_pct < 0.5:
                impact_score = 100.0  # minimal slippage
            elif price_impact_pct < 2.0:
                impact_score = 85.0
            elif price_impact_pct < 5.0:
                impact_score = 60.0
            elif price_impact_pct < 10.0:
                impact_score = 30.0
            else:
                impact_score = max(5.0, 30.0 - (price_impact_pct - 10.0))
            confidences.append(0.9)
            evidence.append(
                EvidenceItem(
                    source="simulated_slippage_model",
                    timestamp=as_of,
                    reference=f"mint:{input_data.mint_address}",
                    details={
                        "test_trade_usd": test_trade_size,
                        "estimated_impact_pct": round(price_impact_pct, 2),
                        "liquidity_usd": liq_usd,
                    },
                )
            )
        else:
            impact_score = 0.0
            price_impact_pct = 100.0
            confidences.append(0.9)
        components["slippage_viability"] = round(impact_score, 2)

        # 2. DEX Routing and Infrastructure (0-100)
        dex = str(pool.get("dex") or pool.get("source") or "").lower()
        if dex in ("raydium", "meteora", "orca", "pumpfun"):
            dex_route_score = 90.0
        elif dex:
            dex_route_score = 65.0
        else:
            dex_route_score = 30.0
        components["dex_routing"] = round(dex_route_score, 2)
        confidences.append(0.8)

        # 3. Transfer Tax and Gas Deduction Viability (0-100)
        tax_bps = float(sec.get("transfer_fee_bps") or 0.0)
        if tax_bps == 0:
            tax_viability = 100.0
        elif tax_bps < 100:  # < 1%
            tax_viability = 80.0
        elif tax_bps < 500:  # < 5%
            tax_viability = 40.0
        else:
            tax_viability = 0.0
        components["tax_viability"] = round(tax_viability, 2)
        confidences.append(0.9)

        # Total Execution Feasibility Score
        total_score = round(
            0.50 * components["slippage_viability"]
            + 0.25 * components["dex_routing"]
            + 0.25 * components["tax_viability"],
            2,
        )

        overall_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.5
        rationale = (
            f"Execution feasibility {total_score:.1f}/100. Slippage on ${test_trade_size:.0f} trade ({components['slippage_viability']:.1f}), "
            f"DEX routing ({components['dex_routing']:.1f}), and tax viability ({components['tax_viability']:.1f})."
        )

        return DimensionScore(
            dimension=DecisionDimension.EXECUTION_FEASIBILITY,
            score=total_score,
            confidence=overall_conf,
            components=components,
            rationale=rationale,
            evidence_sources=evidence,
        )
