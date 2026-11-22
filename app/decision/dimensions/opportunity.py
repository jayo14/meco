"""
Opportunity Quality Dimension Evaluator.
Synthesizes trading momentum, volume acceleration, research agent findings,
and validated statistical model expectations into an opportunity score.
"""
from datetime import datetime, timezone
import math
from typing import Any

from app.agents.base import EvidenceItem, FindingType
from app.decision.config import DecisionEngineConfig
from app.decision.dimensions.base import BaseDimensionEvaluator
from app.decision.models import DecisionDimension, DimensionScore, TokenDecisionInput


class OpportunityQualityEvaluator(BaseDimensionEvaluator):
    """
    Evaluates upside opportunity without conflating risk:
    - 5m/1h volume acceleration
    - Price momentum and buy dominance
    - Research specialist conviction
    - Validated statistical model outputs (cohort win rates & positive expectancy)
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

        # 1. Volume Acceleration Component (0-100)
        # Ratio of short-term (5m) volume to 1h volume annualized to 5m slots (1h / 12)
        vol_5m = float(latest_obs.get("volume_5m") or pool.get("volume_5m") or 0.0)
        vol_1h = float(latest_obs.get("volume_1h") or pool.get("volume_1h") or 0.0)
        expected_5m = (vol_1h / 12.0) if vol_1h > 0 else 0.0

        if expected_5m > 0 and vol_5m > 0:
            vol_ratio = vol_5m / expected_5m
            # 1.0 is normal baseline (50 pts), 3.0+ is breakout surge (100 pts)
            vol_score = min(100.0, max(0.0, 50.0 + (vol_ratio - 1.0) * 25.0))
            confidences.append(0.85)
            evidence.append(
                EvidenceItem(
                    source="market_volume",
                    timestamp=as_of,
                    reference=f"mint:{input_data.mint_address}",
                    details={"volume_5m": vol_5m, "volume_1h": vol_1h, "acceleration_ratio": round(vol_ratio, 2)},
                )
            )
        elif vol_5m > 0:
            vol_score = 50.0
            confidences.append(0.5)
        else:
            vol_score = 10.0
            confidences.append(0.6)
        components["volume_acceleration"] = round(vol_score, 2)

        # 2. Price Momentum & Buy Dominance Component (0-100)
        price_chg_5m = float(latest_obs.get("price_change_5m") or pool.get("price_change_5m") or 0.0)
        price_chg_1h = float(latest_obs.get("price_change_1h") or pool.get("price_change_1h") or 0.0)
        buys_5m = int(latest_obs.get("buys_5m") or pool.get("buys_5m") or 0)
        sells_5m = int(latest_obs.get("sells_5m") or pool.get("sells_5m") or 0)
        total_txns = buys_5m + sells_5m

        buy_ratio = (buys_5m / total_txns) if total_txns > 0 else 0.5

        # Momentum score from price changes: 0% chg = 50 pts, +10% 5m = 75 pts, +25% = 100 pts
        # Penalize severe sudden pump dumps (-20% drops)
        momentum_base = 50.0 + (price_chg_5m * 2.5) + (price_chg_1h * 0.5)
        buy_modifier = (buy_ratio - 0.5) * 40.0
        price_momentum_score = min(100.0, max(0.0, momentum_base + buy_modifier))
        components["price_momentum"] = round(price_momentum_score, 2)
        if total_txns > 0:
            confidences.append(0.8)
            evidence.append(
                EvidenceItem(
                    source="market_momentum",
                    timestamp=as_of,
                    reference=f"mint:{input_data.mint_address}",
                    details={
                        "price_change_5m": price_chg_5m,
                        "price_change_1h": price_chg_1h,
                        "buy_ratio": round(buy_ratio, 2),
                    },
                )
            )

        # 3. Research Agent Conviction Component (0-100)
        res_out = input_data.research_agent_output
        if res_out and res_out.status.value == "completed":
            facts_count = len(res_out.facts())
            hypotheses = res_out.hypotheses()
            # Score based on confidence and verified findings
            research_base = res_out.confidence * 80.0 + min(20.0, facts_count * 4.0)
            research_score = min(100.0, max(0.0, research_base))
            confidences.append(res_out.confidence)
            evidence.extend(res_out.evidence_references[:3])
        else:
            research_score = 45.0
            confidences.append(0.4)
        components["research_conviction"] = round(research_score, 2)

        # 4. Statistical Model Edge Component (0-100)
        stats = input_data.statistical_model_outputs or {}
        if stats:
            expected_win_rate = float(stats.get("expected_win_rate") or stats.get("win_rate") or 0.5)
            expected_payoff = float(stats.get("expected_payoff") or stats.get("profit_factor") or 1.0)
            anomaly_score = float(stats.get("anomaly_score") or 0.0)

            # Win rate 50% & payoff 1.0 -> 50 pts; Win rate 65% & payoff 2.0 -> 85 pts
            stats_base = (expected_win_rate * 60.0) + min(30.0, (expected_payoff - 1.0) * 20.0)
            # Positive anomalies can signal breakout
            stats_score = min(100.0, max(0.0, stats_base + (anomaly_score * 10.0)))
            confidences.append(0.85)
            evidence.append(
                EvidenceItem(
                    source="statistical_models",
                    timestamp=as_of,
                    reference=f"mint:{input_data.mint_address}",
                    details={"expected_win_rate": expected_win_rate, "expected_payoff": expected_payoff},
                )
            )
        else:
            # Baseline neutral score if statistical model not available
            stats_score = 50.0
            confidences.append(0.5)
        components["statistical_edge"] = round(stats_score, 2)

        # Apply weights from config
        w = config.weights
        total_score = round(
            w.volume_growth_weight * components["volume_acceleration"]
            + w.price_momentum_weight * components["price_momentum"]
            + w.social_traction_weight * components["research_conviction"]
            + w.statistical_edge_weight * components["statistical_edge"],
            2,
        )

        overall_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.5
        rationale = (
            f"Opportunity score {total_score:.1f}/100 driven by volume acceleration ({components['volume_acceleration']:.1f}), "
            f"price momentum ({components['price_momentum']:.1f}), research conviction ({components['research_conviction']:.1f}), "
            f"and statistical expectation ({components['statistical_edge']:.1f})."
        )

        return DimensionScore(
            dimension=DecisionDimension.OPPORTUNITY_QUALITY,
            score=total_score,
            confidence=overall_conf,
            components=components,
            rationale=rationale,
            evidence_sources=evidence,
        )
