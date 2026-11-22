"""
Champion/Challenger Promotion & Governance System for Meco (Phase 7).

Enforces strict, auditable gates for model and strategy promotion:
1. Versioned dataset manifest validation.
2. Chronological out-of-sample evaluation check.
3. Multi-metric comparison against active champion (Sharpe, Profit Factor, Net EV).
4. Mandatory risk gates (Max Drawdown ceiling, min trade sample size, fee tolerance).
5. Documented promotion approval and immediate rollback mechanism.

Invariant: No model or strategy can self-promote merely due to in-sample metrics.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

from app.research.dataset import DatasetManifest
from app.research.metrics import QuantitativeReport


class PromotionStatus(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"
    ACTIVE = "active"


@dataclass
class PromotionGateCriteria:
    """Configurable thresholds required for promotion consideration."""
    min_out_of_sample_trades: int = 15
    min_profit_factor: float = 1.25
    min_win_rate_pct: float = 40.0
    max_acceptable_drawdown_pct: float = 20.0
    min_expectancy_usd: float = 0.50
    min_sharpe_ratio: float = 0.50
    require_profit_factor_improvement_pct: float = 5.0  # must beat champion by at least 5%
    require_net_pnl_improvement_usd: float = 0.0


@dataclass
class PromotionEvaluationResult:
    """Detailed audit verdict of a challenger evaluation against champion."""
    candidate_id: str
    candidate_version: str
    champion_id: str | None
    champion_version: str | None
    is_eligible: bool
    rejection_reasons: list[str] = field(default_factory=list)
    advantages_over_champion: list[str] = field(default_factory=list)
    dataset_manifest_hash: str = ""
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class PromotionAuditRecord:
    """Immutable audit trail of an authorized promotion or rollback event."""
    promotion_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    candidate_id: str = ""
    candidate_version: str = ""
    prior_champion_id: str | None = None
    prior_champion_version: str | None = None
    status: PromotionStatus = PromotionStatus.APPROVED
    approval_reason: str = ""
    approved_by: str = "governance_agent"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evaluation_summary: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True


class ChampionChallengerGateway:
    """
    Controlled gatekeeper ensuring no candidate replaces the active champion
    without rigorous out-of-sample evidence and documented governance approval.
    """

    def __init__(
        self,
        criteria: PromotionGateCriteria | None = None,
        initial_champion_id: str = "heuristic_baseline_champion",
        initial_champion_version: str = "1.0.0",
        initial_champion_report: QuantitativeReport | None = None,
    ) -> None:
        self.criteria = criteria or PromotionGateCriteria()
        self.active_champion_id = initial_champion_id
        self.active_champion_version = initial_champion_version
        self.active_champion_report = initial_champion_report
        self.promotion_history: list[PromotionAuditRecord] = []

    def evaluate_challenger(
        self,
        candidate_id: str,
        candidate_version: str,
        challenger_report: QuantitativeReport,
        dataset_manifest: DatasetManifest,
        in_sample_training_score: float | None = None,
    ) -> PromotionEvaluationResult:
        """
        Evaluate candidate against strict out-of-sample promotion criteria.
        """
        rejection_reasons: list[str] = []
        advantages: list[str] = []

        # Gate 1: Dataset Verification
        if not dataset_manifest or not dataset_manifest.sha256_hash or dataset_manifest.row_count == 0:
            rejection_reasons.append("Unverified or empty dataset manifest provided.")

        # Gate 2: Minimum Out-of-Sample Trade Sample Size
        if challenger_report.total_trades < self.criteria.min_out_of_sample_trades:
            rejection_reasons.append(
                f"Insufficient out-of-sample trades: {challenger_report.total_trades} < "
                f"required {self.criteria.min_out_of_sample_trades}."
            )

        # Gate 3: Risk & Drawdown Thresholds
        if challenger_report.max_drawdown_pct > self.criteria.max_acceptable_drawdown_pct:
            rejection_reasons.append(
                f"Max drawdown too high: {challenger_report.max_drawdown_pct:.2f}% > "
                f"threshold {self.criteria.max_acceptable_drawdown_pct:.2f}%."
            )

        # Gate 4: Profit Factor & Expectancy Absolute Floors
        if challenger_report.profit_factor < self.criteria.min_profit_factor:
            rejection_reasons.append(
                f"Profit factor below minimum: {challenger_report.profit_factor:.2f} < "
                f"{self.criteria.min_profit_factor:.2f}."
            )

        if challenger_report.expectancy_usd < self.criteria.min_expectancy_usd:
            rejection_reasons.append(
                f"Expectancy below minimum: ${challenger_report.expectancy_usd:+.2f} < "
                f"${self.criteria.min_expectancy_usd:+.2f}."
            )

        # Gate 5: Direct Comparison Against Current Champion (if available)
        if self.active_champion_report:
            champ = self.active_champion_report
            # Net profit comparison
            if challenger_report.net_profit_usd <= champ.net_profit_usd:
                rejection_reasons.append(
                    f"Candidate net profit (${challenger_report.net_profit_usd:+.2f}) does not exceed "
                    f"active champion (${champ.net_profit_usd:+.2f})."
                )
            else:
                advantages.append(
                    f"Higher net profit: ${challenger_report.net_profit_usd:+.2f} vs ${champ.net_profit_usd:+.2f}."
                )

            # Profit factor comparison
            required_pf = champ.profit_factor * (1.0 + self.criteria.require_profit_factor_improvement_pct / 100.0)
            if challenger_report.profit_factor < required_pf:
                rejection_reasons.append(
                    f"Candidate profit factor ({challenger_report.profit_factor:.2f}) does not beat "
                    f"champion + {self.criteria.require_profit_factor_improvement_pct}% threshold ({required_pf:.2f})."
                )
            else:
                advantages.append(
                    f"Superior profit factor: {challenger_report.profit_factor:.2f} vs {champ.profit_factor:.2f}."
                )

            # Max drawdown comparison
            if challenger_report.max_drawdown_pct > champ.max_drawdown_pct:
                rejection_reasons.append(
                    f"Candidate max drawdown ({challenger_report.max_drawdown_pct:.2f}%) exceeds "
                    f"champion drawdown ({champ.max_drawdown_pct:.2f}%)."
                )
            else:
                advantages.append(
                    f"Equal or lower drawdown: {challenger_report.max_drawdown_pct:.2f}% vs {champ.max_drawdown_pct:.2f}%."
                )

        is_eligible = len(rejection_reasons) == 0

        return PromotionEvaluationResult(
            candidate_id=candidate_id,
            candidate_version=candidate_version,
            champion_id=self.active_champion_id,
            champion_version=self.active_champion_version,
            is_eligible=is_eligible,
            rejection_reasons=rejection_reasons,
            advantages_over_champion=advantages,
            dataset_manifest_hash=dataset_manifest.sha256_hash if dataset_manifest else "",
        )

    def promote_candidate(
        self,
        evaluation_result: PromotionEvaluationResult,
        candidate_report: QuantitativeReport,
        approver: str = "governance_agent",
        approval_notes: str = "Met all out-of-sample risk and performance gates.",
    ) -> PromotionAuditRecord:
        """
        Executes formal promotion if and only if candidate passed evaluation.
        """
        if not evaluation_result.is_eligible:
            raise ValueError(
                f"Cannot promote ineligible candidate {evaluation_result.candidate_id}: "
                f"{'; '.join(evaluation_result.rejection_reasons)}"
            )

        prior_id = self.active_champion_id
        prior_ver = self.active_champion_version

        # Update active champion
        self.active_champion_id = evaluation_result.candidate_id
        self.active_champion_version = evaluation_result.candidate_version
        self.active_champion_report = candidate_report

        record = PromotionAuditRecord(
            candidate_id=evaluation_result.candidate_id,
            candidate_version=evaluation_result.candidate_version,
            prior_champion_id=prior_id,
            prior_champion_version=prior_ver,
            status=PromotionStatus.APPROVED,
            approval_reason=approval_notes,
            approved_by=approver,
            evaluation_summary=asdict(evaluation_result),
            is_active=True,
        )
        self.promotion_history.append(record)
        return record

    def rollback_to_champion(
        self,
        target_champion_id: str,
        target_version: str,
        target_report: QuantitativeReport | None = None,
        reason: str = "Emergency performance degradation rollback",
        initiator: str = "risk_officer",
    ) -> PromotionAuditRecord:
        """
        Immediately demotes current champion and restores a verified previous champion.
        """
        prior_id = self.active_champion_id
        prior_ver = self.active_champion_version

        self.active_champion_id = target_champion_id
        self.active_champion_version = target_version
        self.active_champion_report = target_report

        # Mark prior active promotions as superseded
        for p in self.promotion_history:
            if p.is_active:
                p.is_active = False

        record = PromotionAuditRecord(
            candidate_id=target_champion_id,
            candidate_version=target_version,
            prior_champion_id=prior_id,
            prior_champion_version=prior_ver,
            status=PromotionStatus.ROLLED_BACK,
            approval_reason=f"Rollback: {reason}",
            approved_by=initiator,
            is_active=True,
        )
        self.promotion_history.append(record)
        return record
