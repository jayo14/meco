"""
Deterministic Evidence-Based Decision Engine for Meco (Phase 5).
Synthesizes token intelligence, specialist agent findings, and quantitative market features.
Ranks opportunities, separates risk from opportunity, and explains why a token is or is not
worth further consideration.
"""
from datetime import datetime, timedelta, timezone
import logging
from typing import Any
import uuid

from app.agents.base import EvidenceItem, FindingType
from app.decision.config import DecisionEngineConfig, get_decision_config
from app.decision.dimensions import (
    DataConfidenceEvaluator,
    ExecutionFeasibilityEvaluator,
    LiquidityQualityEvaluator,
    MarketConditionsEvaluator,
    OpportunityQualityEvaluator,
    SecurityRiskEvaluator,
    SocialTractionEvaluator,
    WalletDeployerRiskEvaluator,
)
from app.decision.freshness import evaluate_input_freshness
from app.decision.hard_rules import evaluate_hard_risk_rules
from app.decision.models import (
    DecisionDimension,
    DecisionExplanation,
    DecisionOutcome,
    DimensionScore,
    DimensionScores,
    HardRiskViolation,
    TokenDecisionInput,
    TokenDecisionResult,
)

logger = logging.getLogger("meco.decision.engine")


class DecisionEngine:
    """
    Core Deterministic Decision Engine.
    Executes staged multi-dimensional evaluation:
    1. Input Freshness and Completeness Validation.
    2. Deterministic Hard Risk Constraints Evaluation.
    3. Independent 8-Dimension Evaluation.
    4. Deterministic Outcome Classification.
    5. Evidence Provenance & Contradiction Mapping.
    6. Explainability Trace Generation.
    """

    def __init__(self, config: DecisionEngineConfig | None = None) -> None:
        self.config = config or get_decision_config()
        self.version = self.config.version

        # Initialize dimension evaluators
        self.evaluators = {
            DecisionDimension.OPPORTUNITY_QUALITY: OpportunityQualityEvaluator(),
            DecisionDimension.MARKET_CONDITIONS: MarketConditionsEvaluator(),
            DecisionDimension.SOCIAL_TRACTION: SocialTractionEvaluator(),
            DecisionDimension.LIQUIDITY_QUALITY: LiquidityQualityEvaluator(),
            DecisionDimension.SECURITY_RISK: SecurityRiskEvaluator(),
            DecisionDimension.WALLET_DEPLOYER_RISK: WalletDeployerRiskEvaluator(),
            DecisionDimension.DATA_CONFIDENCE: DataConfidenceEvaluator(),
            DecisionDimension.EXECUTION_FEASIBILITY: ExecutionFeasibilityEvaluator(),
        }

    def evaluate(
        self,
        input_data: TokenDecisionInput,
        as_of: datetime | None = None,
    ) -> TokenDecisionResult:
        """
        Evaluate token decision deterministically.
        All calculations use `eval_time` to prevent any temporal look-ahead bias.
        """
        eval_time = as_of or input_data.as_of or datetime.now(timezone.utc)
        if eval_time.tzinfo is None:
            eval_time = eval_time.replace(tzinfo=timezone.utc)

        decision_id = str(uuid.uuid4())
        expiration_time = eval_time + timedelta(seconds=self.config.reassessment.decision_validity_seconds)

        supporting_evidence: list[EvidenceItem] = []
        contradictory_evidence: list[EvidenceItem] = []
        risk_factors: list[dict[str, Any]] = []
        missing_info: list[str] = []

        # ----------------------------------------------------------------------
        # STAGE 1: Data Freshness and Completeness Gate
        # ----------------------------------------------------------------------
        freshness_res = evaluate_input_freshness(input_data, self.config.freshness, as_of=eval_time)
        missing_info.extend(freshness_res.missing_critical_fields)
        if freshness_res.stale_fields:
            missing_info.extend([f"stale_{f}" for f in freshness_res.stale_fields])

        # If critical information is missing or stale critical data rejected
        if not freshness_res.is_valid:
            # Evaluate baseline dimensions for transparency even in rejection
            dim_scores = self._evaluate_all_dimensions(input_data, eval_time)
            contradictory_evidence.extend(freshness_res.evidence)

            reason = "; ".join(freshness_res.rejection_reasons)
            outcome = DecisionOutcome.INSUFFICIENT_EVIDENCE
            summary = f"Evaluation halted: insufficient or stale evidence. {reason}"

            explanation = self._build_explanation(
                input_data=input_data,
                eval_time=eval_time,
                outcome=outcome,
                summary=summary,
                dim_scores=dim_scores,
                hard_risks=[],
                missing_info=missing_info,
                supporting=supporting_evidence,
                contradictory=contradictory_evidence,
            )

            return TokenDecisionResult(
                decision_id=decision_id,
                token_id=input_data.token_id,
                mint_address=input_data.mint_address,
                outcome=outcome,
                reasoning_summary=summary,
                dimension_scores=dim_scores,
                hard_risk_violations=[],
                supporting_evidence=supporting_evidence,
                contradictory_evidence=contradictory_evidence,
                risk_factors=[{"type": "data_quality", "reasons": freshness_res.rejection_reasons}],
                missing_information=missing_info,
                confidence=min(0.3, dim_scores.data_confidence.confidence),
                decision_timestamp=eval_time,
                expiration_time=expiration_time,
                engine_version=self.version,
                scoring_config_version=self.config.version,
                explanation=explanation,
            )

        # ----------------------------------------------------------------------
        # STAGE 2: Deterministic Hard Risk Constraints Gate
        # ----------------------------------------------------------------------
        hard_violations = evaluate_hard_risk_rules(input_data, self.config.hard_rules, as_of=eval_time)
        if hard_violations:
            dim_scores = self._evaluate_all_dimensions(input_data, eval_time)
            for v in hard_violations:
                if v.evidence:
                    contradictory_evidence.append(v.evidence)
                risk_factors.append({
                    "code": v.rule_code,
                    "description": v.description,
                    "severity": v.severity,
                    "details": v.details,
                })

            outcome = DecisionOutcome.REJECTED_DUE_TO_HARD_RISK
            summary = (
                f"Rejected due to {len(hard_violations)} hard risk violation(s): "
                + ", ".join(f"[{v.rule_code}] {v.description}" for v in hard_violations)
            )

            explanation = self._build_explanation(
                input_data=input_data,
                eval_time=eval_time,
                outcome=outcome,
                summary=summary,
                dim_scores=dim_scores,
                hard_risks=hard_violations,
                missing_info=missing_info,
                supporting=supporting_evidence,
                contradictory=contradictory_evidence,
            )

            return TokenDecisionResult(
                decision_id=decision_id,
                token_id=input_data.token_id,
                mint_address=input_data.mint_address,
                outcome=outcome,
                reasoning_summary=summary,
                dimension_scores=dim_scores,
                hard_risk_violations=hard_violations,
                supporting_evidence=supporting_evidence,
                contradictory_evidence=contradictory_evidence,
                risk_factors=risk_factors,
                missing_information=missing_info,
                confidence=dim_scores.data_confidence.confidence,
                decision_timestamp=eval_time,
                expiration_time=expiration_time,
                engine_version=self.version,
                scoring_config_version=self.config.version,
                explanation=explanation,
            )

        # ----------------------------------------------------------------------
        # STAGE 3: Multi-Dimensional Evaluation (8 Independent Dimensions)
        # ----------------------------------------------------------------------
        dim_scores = self._evaluate_all_dimensions(input_data, eval_time)

        # Collate supporting and contradictory evidence across dimensions
        for d in [
            dim_scores.opportunity_quality,
            dim_scores.market_conditions,
            dim_scores.social_traction,
            dim_scores.liquidity_quality,
            dim_scores.execution_feasibility,
        ]:
            if d.score >= 50.0:
                supporting_evidence.extend(d.evidence_sources)
            else:
                contradictory_evidence.extend(d.evidence_sources)

        for d in [dim_scores.security_risk, dim_scores.wallet_deployer_risk]:
            if d.score > 30.0:
                contradictory_evidence.extend(d.evidence_sources)
                risk_factors.append({
                    "dimension": d.dimension.value,
                    "score": d.score,
                    "rationale": d.rationale,
                })
            else:
                supporting_evidence.extend(d.evidence_sources)

        # Also ingest risk agent soft warnings
        if input_data.risk_agent_output:
            for sw in input_data.risk_agent_output.soft_warnings:
                risk_factors.append({
                    "code": sw.code,
                    "description": sw.description,
                    "severity": sw.severity,
                })
                if sw.evidence:
                    contradictory_evidence.append(sw.evidence)

        # ----------------------------------------------------------------------
        # STAGE 4: Deterministic Outcome Classification
        # ----------------------------------------------------------------------
        t = self.config.thresholds
        opp = dim_scores.opportunity_quality.score
        sec_risk = dim_scores.security_risk.score
        wallet_risk = dim_scores.wallet_deployer_risk.score
        liq_qual = dim_scores.liquidity_quality.score
        feasibility = dim_scores.execution_feasibility.score
        confidence = dim_scores.data_confidence.confidence

        # Paper-trade candidate: high opportunity, safe security, low wallet risk, adequate liquidity & confidence
        if (
            opp >= t.paper_trade_min_opportunity
            and sec_risk <= t.paper_trade_max_security_risk
            and wallet_risk <= t.paper_trade_max_wallet_risk
            and liq_qual >= t.paper_trade_min_liquidity_quality
            and feasibility >= t.paper_trade_min_feasibility
            and confidence >= t.paper_trade_min_confidence
        ):
            outcome = DecisionOutcome.PAPER_TRADE_CANDIDATE
            summary = (
                f"Qualified as Paper-Trade Candidate. High opportunity ({opp:.1f}/100), "
                f"clean security risk ({sec_risk:.1f}/100), low wallet risk ({wallet_risk:.1f}/100), "
                f"and robust liquidity ({liq_qual:.1f}/100) with confidence {confidence:.2f}."
            )

        # Watchlist: solid opportunity and acceptable risk
        elif (
            opp >= t.watchlist_min_opportunity
            and sec_risk <= t.watchlist_max_security_risk
            and wallet_risk <= t.watchlist_max_wallet_risk
            and confidence >= t.watchlist_min_confidence
        ):
            outcome = DecisionOutcome.WATCHLIST
            summary = (
                f"Placed on Watchlist. Favorable opportunity ({opp:.1f}/100) and acceptable risk profile "
                f"(sec: {sec_risk:.1f}, wallet: {wallet_risk:.1f})."
            )

        # Investigate further: high potential but incomplete confidence or unverified signals
        elif (
            opp >= t.investigate_min_opportunity
            and sec_risk <= 50.0
            and confidence < t.investigate_max_confidence
        ):
            outcome = DecisionOutcome.INVESTIGATE_FURTHER
            summary = (
                f"Requires further investigation. Promising opportunity ({opp:.1f}/100) but moderate confidence "
                f"({confidence:.2f} < threshold {t.investigate_max_confidence:.2f})."
            )

        # Monitor: modest opportunity or low liquidity, but clean enough to keep under observation
        elif opp >= t.monitor_min_opportunity and sec_risk <= t.monitor_max_security_risk:
            outcome = DecisionOutcome.MONITOR
            summary = (
                f"Monitored. Modest activity ({opp:.1f}/100) and manageable risk ({sec_risk:.1f}/100). "
                f"Waiting for liquidity or momentum confirmation."
            )

        # Otherwise: ignore
        else:
            outcome = DecisionOutcome.IGNORE
            summary = (
                f"Ignored. Sub-threshold opportunity ({opp:.1f}/100) or excessive risk "
                f"(sec: {sec_risk:.1f}, wallet: {wallet_risk:.1f})."
            )

        explanation = self._build_explanation(
            input_data=input_data,
            eval_time=eval_time,
            outcome=outcome,
            summary=summary,
            dim_scores=dim_scores,
            hard_risks=[],
            missing_info=missing_info,
            supporting=supporting_evidence,
            contradictory=contradictory_evidence,
        )

        return TokenDecisionResult(
            decision_id=decision_id,
            token_id=input_data.token_id,
            mint_address=input_data.mint_address,
            outcome=outcome,
            reasoning_summary=summary,
            dimension_scores=dim_scores,
            hard_risk_violations=[],
            supporting_evidence=supporting_evidence,
            contradictory_evidence=contradictory_evidence,
            risk_factors=risk_factors,
            missing_information=missing_info,
            confidence=confidence,
            decision_timestamp=eval_time,
            expiration_time=expiration_time,
            engine_version=self.version,
            scoring_config_version=self.config.version,
            explanation=explanation,
        )

    def _evaluate_all_dimensions(
        self,
        input_data: TokenDecisionInput,
        as_of: datetime,
    ) -> DimensionScores:
        """Run all 8 dimension evaluators deterministically."""
        scores = {}
        for dim, evaluator in self.evaluators.items():
            scores[dim.value] = evaluator.evaluate(input_data, self.config, as_of)

        return DimensionScores(
            opportunity_quality=scores[DecisionDimension.OPPORTUNITY_QUALITY.value],
            market_conditions=scores[DecisionDimension.MARKET_CONDITIONS.value],
            social_traction=scores[DecisionDimension.SOCIAL_TRACTION.value],
            liquidity_quality=scores[DecisionDimension.LIQUIDITY_QUALITY.value],
            security_risk=scores[DecisionDimension.SECURITY_RISK.value],
            wallet_deployer_risk=scores[DecisionDimension.WALLET_DEPLOYER_RISK.value],
            data_confidence=scores[DecisionDimension.DATA_CONFIDENCE.value],
            execution_feasibility=scores[DecisionDimension.EXECUTION_FEASIBILITY.value],
        )

    def _build_explanation(
        self,
        input_data: TokenDecisionInput,
        eval_time: datetime,
        outcome: DecisionOutcome,
        summary: str,
        dim_scores: DimensionScores,
        hard_risks: list[HardRiskViolation],
        missing_info: list[str],
        supporting: list[EvidenceItem],
        contradictory: list[EvidenceItem],
    ) -> DecisionExplanation:
        """Build the structured 7-question explainability record."""
        # Q1: Evidence available
        evidence_available = {
            "canonical_token": bool(input_data.canonical_token),
            "security_profile": bool(input_data.security_findings),
            "liquidity_pool": bool(input_data.liquidity_pool),
            "holder_distribution": bool(input_data.holder_distribution),
            "market_observations_count": len(input_data.market_observations),
            "social_intelligence": bool(input_data.social_intelligence),
            "statistical_models": bool(input_data.statistical_model_outputs),
            "total_supporting_evidence_items": len(supporting),
            "total_contradictory_evidence_items": len(contradictory),
        }

        # Q2: Token's state at time
        token_state = {
            "mint_address": input_data.mint_address,
            "lifecycle_state": input_data.lifecycle_state,
            "liquidity_usd": (input_data.liquidity_pool or {}).get("liquidity_usd"),
            "as_of": eval_time.isoformat(),
        }

        # Q3: Which agents contributed
        contributing_agents = []
        for name, out in [
            ("research", input_data.research_agent_output),
            ("risk", input_data.risk_agent_output),
            ("market_analysis", input_data.market_agent_output),
            ("social", input_data.social_agent_output),
        ]:
            if out:
                contributing_agents.append({
                    "agent": name,
                    "status": out.status.value,
                    "confidence": out.confidence,
                    "findings_count": len(out.findings),
                    "hard_risks_count": len(out.hard_risks),
                    "soft_warnings_count": len(out.soft_warnings),
                })

        # Q4: Which risk factors mattered
        critical_risk_factors = [h.model_dump(mode="json") for h in hard_risks]
        if dim_scores.security_risk.score > 25.0:
            critical_risk_factors.append({
                "factor": "security_risk",
                "score": dim_scores.security_risk.score,
                "rationale": dim_scores.security_risk.rationale,
            })
        if dim_scores.wallet_deployer_risk.score > 25.0:
            critical_risk_factors.append({
                "factor": "wallet_deployer_risk",
                "score": dim_scores.wallet_deployer_risk.score,
                "rationale": dim_scores.wallet_deployer_risk.rationale,
            })

        # Q6: Which scoring configuration was used
        scoring_config = {
            "version": self.config.version,
            "name": self.config.name,
            "hash": self.config.hash_signature(),
            "weights": self.config.weights.model_dump(mode="json"),
            "thresholds": self.config.thresholds.model_dump(mode="json"),
        }

        return DecisionExplanation(
            evidence_available=evidence_available,
            token_state_at_time=token_state,
            contributing_agents=contributing_agents,
            critical_risk_factors=critical_risk_factors,
            missing_information=missing_info,
            scoring_config_used=scoring_config,
            outcome_selection_rationale=summary,
        )
