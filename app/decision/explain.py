"""
Decision Explainability and Audit Tracing for Meco Decision Engine.
Answers the 7 institutional questions for full regulatory and engineering explainability.
"""
from datetime import datetime
import json
from typing import Any

from app.decision.models import DecisionExplanation, TokenDecisionResult


class DecisionAuditTracer:
    """
    Produces deterministic audit logs and structured human-readable explanations
    for every decision produced by Meco.
    """

    @staticmethod
    def answer_seven_questions(decision: TokenDecisionResult) -> dict[str, Any]:
        """
        Formulate answers to the 7 core questions specified in Phase 5:
        1. What evidence was available?
        2. What was the token's state at the time?
        3. Which agents contributed?
        4. Which risk factors mattered?
        5. What information was missing?
        6. Which scoring configuration was used?
        7. Why was this outcome selected?
        """
        expl = decision.explain()
        return {
            "q1_evidence_available": expl.evidence_available,
            "q2_token_state_at_time": expl.token_state_at_time,
            "q3_contributing_agents": expl.contributing_agents,
            "q4_critical_risk_factors": expl.critical_risk_factors,
            "q5_missing_information": expl.missing_information,
            "q6_scoring_config_used": expl.scoring_config_used,
            "q7_outcome_selection_rationale": expl.outcome_selection_rationale,
        }

    @staticmethod
    def generate_audit_report(decision: TokenDecisionResult) -> str:
        """
        Render a comprehensive Markdown audit report of the decision.
        """
        expl = decision.explain()
        scores = decision.dimension_scores

        lines = [
            f"# Decision Audit Report: {decision.mint_address}",
            f"**Decision ID:** `{decision.decision_id}`  ",
            f"**Decision Outcome:** `{decision.outcome.value.upper()}`  ",
            f"**Decision Timestamp:** `{decision.decision_timestamp.isoformat()}`  ",
            f"**Expiration Time:** `{decision.expiration_time.isoformat()}`  ",
            f"**Overall Confidence:** `{decision.confidence:.2f}`  ",
            f"**Engine Version:** `{decision.engine_version}` | **Config Version:** `{decision.scoring_config_version}`  ",
            "",
            "## Reasoning Summary",
            decision.reasoning_summary,
            "",
            "## Dimension Scores Breakdown",
            "| Dimension | Score (0-100) | Confidence | Rationale |",
            "| :--- | :--- | :--- | :--- |",
            f"| Opportunity Quality | {scores.opportunity_quality.score:.1f} | {scores.opportunity_quality.confidence:.2f} | {scores.opportunity_quality.rationale} |",
            f"| Market Conditions | {scores.market_conditions.score:.1f} | {scores.market_conditions.confidence:.2f} | {scores.market_conditions.rationale} |",
            f"| Social Traction | {scores.social_traction.score:.1f} | {scores.social_traction.confidence:.2f} | {scores.social_traction.rationale} |",
            f"| Liquidity Quality | {scores.liquidity_quality.score:.1f} | {scores.liquidity_quality.confidence:.2f} | {scores.liquidity_quality.rationale} |",
            f"| Security Risk (Danger) | {scores.security_risk.score:.1f} | {scores.security_risk.confidence:.2f} | {scores.security_risk.rationale} |",
            f"| Wallet/Deployer Risk | {scores.wallet_deployer_risk.score:.1f} | {scores.wallet_deployer_risk.confidence:.2f} | {scores.wallet_deployer_risk.rationale} |",
            f"| Data Confidence | {scores.data_confidence.score:.1f} | {scores.data_confidence.confidence:.2f} | {scores.data_confidence.rationale} |",
            f"| Execution Feasibility | {scores.execution_feasibility.score:.1f} | {scores.execution_feasibility.confidence:.2f} | {scores.execution_feasibility.rationale} |",
            "",
            "## 7-Question Explainability Audit",
            "",
            "### 1. What evidence was available?",
            "```json",
            json.dumps(expl.evidence_available, indent=2),
            "```",
            "",
            "### 2. What was the token's state at the time?",
            "```json",
            json.dumps(expl.token_state_at_time, indent=2),
            "```",
            "",
            "### 3. Which agents contributed?",
            "```json",
            json.dumps(expl.contributing_agents, indent=2),
            "```",
            "",
            "### 4. Which risk factors mattered?",
            "```json",
            json.dumps(expl.critical_risk_factors, indent=2),
            "```",
            "",
            "### 5. What information was missing?",
            f"- Missing fields: {expl.missing_information if expl.missing_information else 'None. Complete input dataset.'}",
            "",
            "### 6. Which scoring configuration was used?",
            "```json",
            json.dumps(expl.scoring_config_used, indent=2),
            "```",
            "",
            "### 7. Why was this outcome selected?",
            f"> {expl.outcome_selection_rationale}",
            "",
            "## Evidence Provenance",
            f"- **Supporting Evidence Count:** {len(decision.supporting_evidence)}",
            f"- **Contradictory Evidence Count:** {len(decision.contradictory_evidence)}",
        ]

        if decision.hard_risk_violations:
            lines.extend([
                "",
                "### Hard Risk Violations Triggered",
            ])
            for v in decision.hard_risk_violations:
                lines.append(f"- **[{v.rule_code}]** {v.description} (Severity: {v.severity})")

        return "\n".join(lines)
