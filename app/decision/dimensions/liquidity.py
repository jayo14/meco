"""
Liquidity Quality Dimension Evaluator.
Evaluates depth, LP token burn/lock status, pool maturity, and reserve health.
"""
from datetime import datetime, timezone
from typing import Any

from app.agents.base import EvidenceItem
from app.decision.config import DecisionEngineConfig
from app.decision.dimensions.base import BaseDimensionEvaluator
from app.decision.models import DecisionDimension, DimensionScore, TokenDecisionInput


class LiquidityQualityEvaluator(BaseDimensionEvaluator):
    """
    Evaluates liquidity robustness:
    - Pool depth in USD
    - LP burn/lock percentage
    - Pool age and pair maturity
    - Reserve balance and multi-pair distribution
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

        # 1. Pool Depth (0-100)
        # Low liquidity (< $2k) is fragile and hard to exit
        # $10k+ is viable for small paper trades; $50k+ is institutional/safe
        liq_usd = float(pool.get("liquidity_usd") or 0.0)
        if liq_usd < 1000.0:
            depth_score = min(20.0, (liq_usd / 1000.0) * 20.0)
        elif 1000.0 <= liq_usd < 10000.0:
            depth_score = 20.0 + ((liq_usd - 1000.0) / 9000.0) * 35.0  # 20 to 55
        elif 10000.0 <= liq_usd < 50000.0:
            depth_score = 55.0 + ((liq_usd - 10000.0) / 40000.0) * 30.0  # 55 to 85
        else:
            depth_score = min(100.0, 85.0 + min(15.0, (liq_usd - 50000.0) / 100000.0 * 15.0))
        components["pool_depth"] = round(depth_score, 2)
        confidences.append(0.9)

        evidence.append(
            EvidenceItem(
                source="liquidity_pool",
                timestamp=as_of,
                reference=f"mint:{input_data.mint_address}",
                details={"liquidity_usd": liq_usd},
            )
        )

        # 2. LP Token Lock & Burn Status (0-100)
        # If LP is 100% burned or locked -> 100 pts. If 0% burned -> 10 pts (instant rug danger)
        lp_burned_pct = float(
            sec.get("lp_burned_percentage")
            or pool.get("lp_burned_percentage")
            or (100.0 if sec.get("lp_burned") else 0.0)
        )

        if lp_burned_pct >= 99.0:
            lock_score = 100.0
        elif lp_burned_pct >= 80.0:
            lock_score = 80.0 + (lp_burned_pct - 80.0)
        elif lp_burned_pct >= 50.0:
            lock_score = 50.0 + (lp_burned_pct - 50.0)
        else:
            lock_score = max(5.0, lp_burned_pct)
        components["lp_lock_burn"] = round(lock_score, 2)
        confidences.append(0.85)

        # 3. Pair Maturity & Longevity (0-100)
        # Check pair creation timestamp
        created_at_ms = pool.get("pair_created_at")
        if created_at_ms:
            # could be ms timestamp or seconds
            if created_at_ms > 1e11:
                created_at_sec = created_at_ms / 1000.0
            else:
                created_at_sec = float(created_at_ms)
            pair_created_dt = datetime.fromtimestamp(created_at_sec, tz=timezone.utc)
            age_hours = (as_of - pair_created_dt).total_seconds() / 3600.0
            if age_hours < 0.5:
                maturity_score = 30.0  # brand new pool (<30 mins)
            elif age_hours < 6.0:
                maturity_score = 60.0  # early survivor
            elif age_hours < 24.0:
                maturity_score = 80.0  # past initial rug window
            else:
                maturity_score = 95.0  # established
            confidences.append(0.8)
        else:
            maturity_score = 50.0
            confidences.append(0.5)
        components["pair_maturity"] = round(maturity_score, 2)

        # 4. Multi-Pair / Reserve Viability (0-100)
        pairs_count = int(pool.get("pairs_count") or 1)
        dex = pool.get("dex") or pool.get("source") or "unknown"
        # Known DEXes (Raydium, Meteora, Orca, Pump.fun)
        dex_bonus = 20.0 if dex.lower() in ("raydium", "meteora", "orca", "pumpfun") else 5.0
        multi_pair_score = min(100.0, 50.0 + min(30.0, pairs_count * 15.0) + dex_bonus)
        components["dex_and_reserves"] = round(multi_pair_score, 2)
        confidences.append(0.8)

        # Total composite score for Liquidity Quality
        total_score = round(
            0.35 * components["pool_depth"]
            + 0.35 * components["lp_lock_burn"]
            + 0.15 * components["pair_maturity"]
            + 0.15 * components["dex_and_reserves"],
            2,
        )

        overall_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.5
        rationale = (
            f"Liquidity quality score {total_score:.1f}/100. Pool depth (${liq_usd:,.0f} -> {components['pool_depth']:.1f}), "
            f"LP burned/locked ({lp_burned_pct:.1f}% -> {components['lp_lock_burn']:.1f}), "
            f"maturity ({components['pair_maturity']:.1f}), and DEX reserves ({components['dex_and_reserves']:.1f})."
        )

        return DimensionScore(
            dimension=DecisionDimension.LIQUIDITY_QUALITY,
            score=total_score,
            confidence=overall_conf,
            components=components,
            rationale=rationale,
            evidence_sources=evidence,
        )
