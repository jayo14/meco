"""
Market Conditions Dimension Evaluator.
Evaluates order flow quality, volume-to-liquidity ratio, buy pressure,
and price stability/volatility from live market observations and specialist market agent findings.
"""
from datetime import datetime, timezone
import math
from typing import Any

from app.agents.base import EvidenceItem
from app.decision.config import DecisionEngineConfig
from app.decision.dimensions.base import BaseDimensionEvaluator
from app.decision.models import DecisionDimension, DimensionScore, TokenDecisionInput


class MarketConditionsEvaluator(BaseDimensionEvaluator):
    """
    Evaluates market health:
    - Volume-to-Liquidity ratio (liquidity utilization vs wash trading)
    - Order flow buy/sell balance
    - Volatility & drawdown stability
    - Market analysis agent output & price impact predictions
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
        obs = input_data.market_observations or []
        latest_obs = obs[-1] if obs else {}

        # 1. Volume-to-Liquidity Ratio (0-100)
        # Healthy ratio for active memecoins/dex pairs is between 0.05 and 2.5
        # Dead token (< 0.01) scores low. Extreme wash trading (> 10.0) penalized.
        vol_24h = float(latest_obs.get("volume_24h") or pool.get("volume_24h") or 0.0)
        vol_5m = float(latest_obs.get("volume_5m") or pool.get("volume_5m") or 0.0)
        vol_effective = vol_24h if vol_24h > 0 else (vol_5m * 288.0)
        liq_usd = float(pool.get("liquidity_usd") or 0.0)

        if liq_usd > 0:
            v_to_l = vol_effective / liq_usd
            if v_to_l < 0.01:
                v_to_l_score = 20.0  # dormant
            elif 0.01 <= v_to_l <= 0.1:
                v_to_l_score = 40.0 + (v_to_l - 0.01) * 300.0  # emerging
            elif 0.1 < v_to_l <= 2.5:
                v_to_l_score = 70.0 + min(30.0, (v_to_l - 0.1) * 12.5)  # optimal liquidity utilization
            elif 2.5 < v_to_l <= 10.0:
                v_to_l_score = 75.0 - (v_to_l - 2.5) * 5.0  # slight wash risk
            else:
                v_to_l_score = 30.0  # severe wash trading / spoofing
            confidences.append(0.85)
            evidence.append(
                EvidenceItem(
                    source="market_liquidity_ratio",
                    timestamp=as_of,
                    reference=f"mint:{input_data.mint_address}",
                    details={"volume_to_liquidity": round(v_to_l, 3), "liquidity_usd": liq_usd, "volume": vol_effective},
                )
            )
        else:
            v_to_l_score = 0.0
            confidences.append(0.9)
        components["volume_to_liquidity"] = round(v_to_l_score, 2)

        # 2. Buy/Sell Order Flow Pressure (0-100)
        buys = int(latest_obs.get("buys_5m") or pool.get("buys_5m") or 0)
        sells = int(latest_obs.get("sells_5m") or pool.get("sells_5m") or 0)
        total_tx = buys + sells

        if total_tx > 0:
            buy_fraction = buys / total_tx
            # 50% buy fraction -> 50 pts; 80% buy fraction -> 95 pts; 20% -> 15 pts
            buy_pressure_score = min(100.0, max(0.0, buy_fraction * 100.0))
            confidences.append(0.8)
        else:
            buy_pressure_score = 50.0
            confidences.append(0.4)
        components["buy_pressure"] = round(buy_pressure_score, 2)

        # 3. Volatility & Price Trend Stability (0-100)
        # High chaotic 5m swings (> 30% drop) penalized; smooth upward drift rewarded
        p_chg_5m = float(latest_obs.get("price_change_5m") or 0.0)
        p_chg_1h = float(latest_obs.get("price_change_1h") or 0.0)
        if p_chg_5m < -25.0 or p_chg_1h < -50.0:
            volatility_stability = 20.0  # dumping
        elif -10.0 <= p_chg_5m <= 25.0:
            volatility_stability = 80.0  # healthy consolidation / steady rise
        elif p_chg_5m > 50.0:
            volatility_stability = 60.0  # parabolic blow-off risk
        else:
            volatility_stability = 50.0
        components["price_stability"] = round(volatility_stability, 2)

        # 4. Market Specialist Agent Findings (0-100)
        mkt_agent = input_data.market_agent_output
        if mkt_agent and mkt_agent.status.value == "completed":
            agent_score = mkt_agent.confidence * 85.0
            # If agent flagged soft warnings, reduce score
            warning_penalty = len(mkt_agent.soft_warnings) * 10.0
            market_agent_score = min(100.0, max(10.0, agent_score - warning_penalty))
            confidences.append(mkt_agent.confidence)
            evidence.extend(mkt_agent.evidence_references[:2])
        else:
            market_agent_score = 50.0
            confidences.append(0.4)
        components["market_agent_conviction"] = round(market_agent_score, 2)

        # Equal weighting across market condition subcomponents
        total_score = round(
            0.30 * components["volume_to_liquidity"]
            + 0.30 * components["buy_pressure"]
            + 0.20 * components["price_stability"]
            + 0.20 * components["market_agent_conviction"],
            2,
        )

        overall_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.5
        rationale = (
            f"Market conditions score {total_score:.1f}/100. Liquidity utilization ({components['volume_to_liquidity']:.1f}), "
            f"buy pressure ({components['buy_pressure']:.1f}), price trend stability ({components['price_stability']:.1f}), "
            f"and market agent conviction ({components['market_agent_conviction']:.1f})."
        )

        return DimensionScore(
            dimension=DecisionDimension.MARKET_CONDITIONS,
            score=total_score,
            confidence=overall_conf,
            components=components,
            rationale=rationale,
            evidence_sources=evidence,
        )
