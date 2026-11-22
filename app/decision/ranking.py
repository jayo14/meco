"""
Opportunity Ranking and Classification Engine for Meco (Phase 5).
Ranks evaluated tokens deterministically while preserving strict separation
between risk and opportunity.
"""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from app.decision.models import DecisionOutcome, TokenDecisionResult


class RankedTokenOpportunity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    rank: int
    mint_address: str
    token_id: int | None = None
    outcome: DecisionOutcome
    composite_opportunity: float
    composite_risk: float
    confidence: float
    risk_adjusted_rank_score: float
    tier: str
    ranking_rationale: str
    decision: TokenDecisionResult


class OpportunityRanker:
    """
    Ranks token opportunities across watchlists and candidates.
    Never collapses risk into an arbitrary blended score:
    - Hard risk rejections and insufficient data are segregated into unqualified tiers.
    - Qualifying tokens are sorted by opportunity quality, execution feasibility, and data confidence,
      with risk serving as a penalty threshold rather than a hidden offset.
    """

    @classmethod
    def classify_tier(cls, decision: TokenDecisionResult) -> str:
        """Categorize token into an institutional actionable tier."""
        if decision.outcome == DecisionOutcome.REJECTED_DUE_TO_HARD_RISK:
            return "UNQUALIFIED_HARD_RISK"
        if decision.outcome == DecisionOutcome.INSUFFICIENT_EVIDENCE:
            return "UNQUALIFIED_INSUFFICIENT_DATA"
        if decision.outcome == DecisionOutcome.PAPER_TRADE_CANDIDATE:
            return "TIER_1_PAPER_TRADE_CANDIDATE"
        if decision.outcome == DecisionOutcome.WATCHLIST:
            return "TIER_2_HIGH_CONVICTION_WATCHLIST"
        if decision.outcome == DecisionOutcome.INVESTIGATE_FURTHER:
            return "TIER_3_INVESTIGATION_QUEUE"
        if decision.outcome == DecisionOutcome.MONITOR:
            return "TIER_4_LOW_PRIORITY_MONITOR"
        return "TIER_5_IGNORED"

    @classmethod
    def calculate_rank_score(
        cls,
        decision: TokenDecisionResult,
        strategy: Literal["risk_adjusted", "opportunity_first", "confidence_weighted"] = "risk_adjusted",
    ) -> float:
        """
        Calculate deterministic ranking score based on selected strategy.
        Hard rejections always receive score < 0 to ensure they never rank above viable candidates.
        """
        if decision.outcome == DecisionOutcome.REJECTED_DUE_TO_HARD_RISK:
            return -1000.0
        if decision.outcome == DecisionOutcome.INSUFFICIENT_EVIDENCE:
            return -500.0

        scores = decision.dimension_scores
        opp = scores.composite_opportunity_score()
        risk = scores.composite_risk_penalty()
        conf = decision.confidence

        if strategy == "opportunity_first":
            # Pure opportunity among non-rejected tokens
            return round(opp, 2)
        elif strategy == "confidence_weighted":
            # Weight opportunity by confidence
            return round(opp * conf, 2)
        else:  # "risk_adjusted" default
            # Opportunity discounted by risk penalty and modulated by execution feasibility
            feasibility = scores.execution_feasibility.score / 100.0
            # Risk penalty discount (max 40% penalty so risk doesn't invert good tokens into negatives)
            risk_discount = max(0.60, 1.0 - (risk / 150.0))
            score = opp * risk_discount * feasibility * conf
            return round(score, 2)

    @classmethod
    def rank_opportunities(
        cls,
        decisions: list[TokenDecisionResult],
        strategy: Literal["risk_adjusted", "opportunity_first", "confidence_weighted"] = "risk_adjusted",
        filter_outcomes: list[DecisionOutcome] | None = None,
    ) -> list[RankedTokenOpportunity]:
        """
        Rank token decisions in descending order of priority.
        Tiebreaker: higher confidence, then lower composite risk, then mint address lexicographically.
        """
        filtered = decisions
        if filter_outcomes:
            filtered = [d for d in decisions if d.outcome in filter_outcomes]

        # Calculate scores and sort
        scored_items = []
        for d in filtered:
            score = cls.calculate_rank_score(d, strategy=strategy)
            opp = d.dimension_scores.composite_opportunity_score()
            risk = d.dimension_scores.composite_risk_penalty()
            tier = cls.classify_tier(d)
            scored_items.append({
                "decision": d,
                "score": score,
                "opp": opp,
                "risk": risk,
                "conf": d.confidence,
                "tier": tier,
                "mint": d.mint_address,
            })

        # Deterministic sort: score desc, confidence desc, risk asc, mint asc
        sorted_items = sorted(
            scored_items,
            key=lambda x: (x["score"], x["conf"], -x["risk"], x["mint"]),
            reverse=True,
        )

        ranked: list[RankedTokenOpportunity] = []
        for idx, item in enumerate(sorted_items, start=1):
            d = item["decision"]
            rationale = (
                f"Rank {idx} ({item['tier']}): rank score {item['score']:.1f} "
                f"(Opportunity: {item['opp']:.1f}, Risk: {item['risk']:.1f}, Confidence: {item['conf']:.2f})."
            )
            ranked.append(
                RankedTokenOpportunity(
                    rank=idx,
                    mint_address=d.mint_address,
                    token_id=d.token_id,
                    outcome=d.outcome,
                    composite_opportunity=item["opp"],
                    composite_risk=item["risk"],
                    confidence=item["conf"],
                    risk_adjusted_rank_score=item["score"],
                    tier=item["tier"],
                    ranking_rationale=rationale,
                    decision=d,
                )
            )

        return ranked
