"""
Data Confidence Dimension Evaluator.
Measures completeness, freshness, and agent consensus across ingested intelligence.
"""
from datetime import datetime, timezone
from typing import Any

from app.agents.base import EvidenceItem
from app.decision.config import DecisionEngineConfig
from app.decision.dimensions.base import BaseDimensionEvaluator
from app.decision.models import DecisionDimension, DimensionScore, TokenDecisionInput


class DataConfidenceEvaluator(BaseDimensionEvaluator):
    """
    Evaluates evidence confidence and completeness (0 = zero confidence, 100 = full confidence):
    - Input completeness across domains (token, security, pool, market, agents, social)
    - Input freshness and lack of stale timestamps
    - Cross-agent consensus vs conflicting signals penalty
    """

    def evaluate(
        self,
        input_data: TokenDecisionInput,
        config: DecisionEngineConfig,
        as_of: datetime,
    ) -> DimensionScore:
        components: dict[str, float] = {}
        evidence: list[EvidenceItem] = []

        # 1. Completeness Score (0-100)
        domain_weights = {
            "canonical_token": 15.0 if input_data.canonical_token else 0.0,
            "security_findings": 25.0 if input_data.security_findings else 0.0,
            "liquidity_pool": 20.0 if input_data.liquidity_pool else 0.0,
            "holder_distribution": 15.0 if input_data.holder_distribution else 0.0,
            "market_observations": 10.0 if input_data.market_observations else 0.0,
            "social_intelligence": 7.5 if input_data.social_intelligence else 0.0,
            "deployer_intelligence": 7.5 if input_data.deployer_intelligence else 0.0,
        }
        completeness_score = min(100.0, sum(domain_weights.values()))
        components["domain_completeness"] = round(completeness_score, 2)

        # 2. Freshness Score (0-100)
        timestamps = input_data.input_timestamps or {}
        freshness_config = config.freshness
        staleness_penalties = 0.0

        for key, ts in timestamps.items():
            if ts:
                ts_aware = ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
                age = max(0.0, (as_of - ts_aware).total_seconds())
                if key in ("price", "market_observations") and age > freshness_config.max_price_staleness_seconds:
                    staleness_penalties += 25.0
                elif key in ("liquidity_pool", "liquidity") and age > freshness_config.max_liquidity_staleness_seconds:
                    staleness_penalties += 25.0
                elif key in ("security_findings", "security") and age > freshness_config.max_security_staleness_seconds:
                    staleness_penalties += 20.0
                elif key in ("social_intelligence", "social") and age > freshness_config.max_social_staleness_seconds:
                    staleness_penalties += 10.0

        freshness_score = max(0.0, 100.0 - staleness_penalties)
        components["input_freshness"] = round(freshness_score, 2)

        # 3. Agent Execution Quality & Consensus (0-100)
        agent_outputs = [
            input_data.research_agent_output,
            input_data.risk_agent_output,
            input_data.market_agent_output,
            input_data.social_agent_output,
        ]
        valid_agents = [a for a in agent_outputs if a is not None]

        if valid_agents:
            completed_agents = [a for a in valid_agents if a.status.value == "completed"]
            agent_ratio = len(completed_agents) / len(valid_agents)
            avg_agent_conf = sum(a.confidence for a in completed_agents) / len(completed_agents) if completed_agents else 0.0
            agent_score = (agent_ratio * 50.0) + (avg_agent_conf * 50.0)

            # Check for conflicting agent findings (e.g. research very bullish vs risk agent finding critical warning)
            has_conflict = False
            if input_data.research_agent_output and input_data.risk_agent_output:
                res_conf = input_data.research_agent_output.confidence
                has_hard_or_soft_risks = bool(
                    input_data.risk_agent_output.hard_risks
                    or len(input_data.risk_agent_output.soft_warnings) >= 2
                )
                if res_conf > 0.75 and has_hard_or_soft_risks:
                    has_conflict = True
                    # Disagreement penalty
                    agent_score = max(20.0, agent_score - 25.0)
                    evidence.append(
                        EvidenceItem(
                            source="agent_consensus_checker",
                            timestamp=as_of,
                            reference=f"mint:{input_data.mint_address}",
                            details={"conflict": "Research conviction high while Risk flagged severe warnings"},
                        )
                    )
            components["conflict_detected"] = 1.0 if has_conflict else 0.0
        else:
            agent_score = 40.0
            components["conflict_detected"] = 0.0

        components["agent_consensus"] = round(agent_score, 2)

        # Total Data Confidence Score
        total_score = round(
            0.40 * components["domain_completeness"]
            + 0.35 * components["input_freshness"]
            + 0.25 * components["agent_consensus"],
            2,
        )

        overall_conf = round(total_score / 100.0, 2)
        rationale = (
            f"Data confidence {total_score:.1f}/100. Domain completeness ({components['domain_completeness']:.1f}), "
            f"freshness ({components['input_freshness']:.1f}), and agent consensus ({components['agent_consensus']:.1f})."
        )

        return DimensionScore(
            dimension=DecisionDimension.DATA_CONFIDENCE,
            score=total_score,
            confidence=overall_conf,
            components=components,
            rationale=rationale,
            evidence_sources=evidence,
        )
