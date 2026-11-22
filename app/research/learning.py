"""
Learning from Paper Trades and Continuous Evaluation for Meco (Phase 7).

Ingests simulated paper-trading outcomes from Phase 6, joins them with
original decision contexts, feature snapshots, and execution friction logs.
Diagnoses error modes:
- False Positives (high model confidence resulting in capital loss).
- Execution Drag (trades profitable on gross returns, but unprofitable after friction).
- Liquidity Traps (positions that suffered severe liquidity drain).
- Calibration Analysis (observed win rate vs predicted probability deciles).
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.research.dataset import PointInTimeFeatures
from app.trading.models import PaperPosition, PositionStatus


@dataclass
class TradeDiagnosis:
    """Diagnostic profile for an individual closed trade."""
    position_id: str
    token_mint: str
    strategy_id: str
    model_version: str | None
    pred_probability: float | None
    realised_pnl_usd: float
    total_fees_paid_usd: float
    net_pnl_usd: float
    return_pct: float
    exit_reason: str
    holding_seconds: float
    error_mode: str  # "success", "false_positive", "execution_drag", "liquidity_trap", "unforced_loss"
    diagnosis_notes: str
    entry_feature_snapshot: dict[str, Any] = field(default_factory=dict)
    agent_findings_summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class LearningInsightsReport:
    """Aggregated insights from post-trade analysis for continuous model improvement."""
    total_analyzed_trades: int
    winning_trades: int
    losing_trades: int
    false_positives_count: int
    execution_drag_count: int
    liquidity_traps_count: int
    unforced_losses_count: int
    total_friction_drag_usd: float
    average_slippage_usd: float
    model_brier_score: float | None
    probability_calibration: dict[str, dict[str, float]] = field(default_factory=dict)
    high_loss_features_correlation: dict[str, float] = field(default_factory=dict)
    recommended_strategy_adjustments: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PaperTradingLearner:
    """
    Analyzes historical paper trading positions to surface statistical weaknesses
    and guide quantitative model retraining.
    """

    @classmethod
    def diagnose_trade(
        cls,
        position: PaperPosition,
        feature_snapshot: PointInTimeFeatures | None = None,
        model_version: str | None = None,
        pred_probability: float | None = None,
        agent_findings: dict[str, Any] | None = None,
    ) -> TradeDiagnosis:
        """Analyze a closed position to isolate the exact cause of failure or success."""
        pnl = float(position.realised_pnl_usd)
        fees = float(position.total_fees_paid_usd)
        net = pnl - fees
        cap = float(position.capital_committed)
        ret_pct = (net / cap * 100.0) if cap > 0 else 0.0

        exit_reas = position.exit_reason.value if position.exit_reason else "unknown"
        dur = position.holding_duration_seconds()

        # Diagnose Error Mode
        if net > 0:
            error_mode = "success"
            notes = f"Profitable trade: net +${net:.2f} ({ret_pct:+.1f}%) via {exit_reas}."
        elif pnl > 0 and net <= 0:
            # Gross was positive, but friction wiped out profit
            error_mode = "execution_drag"
            notes = (
                f"Execution drag trap: gross profit +${pnl:.2f} was completely consumed by "
                f"${fees:.2f} in fees/slippage, resulting in net -${abs(net):.2f}."
            )
        elif exit_reas == "liquidity_deterioration":
            error_mode = "liquidity_trap"
            notes = "Liquidity trap: pool liquidity evaporated during holding period, forcing defensive exit."
        elif pred_probability is not None and pred_probability >= 0.70:
            error_mode = "false_positive"
            notes = f"High-confidence false positive: model predicted {pred_probability*100:.1f}%, but position lost ${abs(net):.2f}."
        else:
            error_mode = "unforced_loss"
            notes = f"Adverse market movement: stop loss or timeout hit ({exit_reas}) with net loss ${abs(net):.2f}."

        return TradeDiagnosis(
            position_id=position.position_id,
            token_mint=position.mint_address,
            strategy_id=position.strategy_id,
            model_version=model_version,
            pred_probability=pred_probability,
            realised_pnl_usd=round(pnl, 2),
            total_fees_paid_usd=round(fees, 2),
            net_pnl_usd=round(net, 2),
            return_pct=round(ret_pct, 2),
            exit_reason=exit_reas,
            holding_seconds=round(dur, 1),
            error_mode=error_mode,
            diagnosis_notes=notes,
            entry_feature_snapshot=feature_snapshot.to_dict() if feature_snapshot else {},
            agent_findings_summary=agent_findings or {},
        )

    @classmethod
    def aggregate_insights(cls, diagnoses: list[TradeDiagnosis]) -> LearningInsightsReport:
        """
        Aggregate individual trade diagnoses into actionable learning metrics.
        """
        n = len(diagnoses)
        if n == 0:
            return LearningInsightsReport(
                total_analyzed_trades=0,
                winning_trades=0,
                losing_trades=0,
                false_positives_count=0,
                execution_drag_count=0,
                liquidity_traps_count=0,
                unforced_losses_count=0,
                total_friction_drag_usd=0.0,
                average_slippage_usd=0.0,
                model_brier_score=None,
            )

        wins = sum(1 for d in diagnoses if d.net_pnl_usd > 0)
        losses = n - wins
        false_pos = sum(1 for d in diagnoses if d.error_mode == "false_positive")
        exec_drag = sum(1 for d in diagnoses if d.error_mode == "execution_drag")
        liq_traps = sum(1 for d in diagnoses if d.error_mode == "liquidity_trap")
        unforced = sum(1 for d in diagnoses if d.error_mode == "unforced_loss")
        total_fees = sum(d.total_fees_paid_usd for d in diagnoses)

        # Probability calibration check
        prob_pairs = [(d.pred_probability, 1 if d.net_pnl_usd > 0 else 0) for d in diagnoses if d.pred_probability is not None]
        brier = None
        calibration_bins: dict[str, dict[str, float]] = {}

        if prob_pairs:
            brier = sum((p - y) ** 2 for p, y in prob_pairs) / len(prob_pairs)

            # Bin into 3 buckets: [0-0.4], [0.4-0.7], [0.7-1.0]
            bins = {"low_prob [0.0-0.4)": [], "mid_prob [0.4-0.7)": [], "high_prob [0.7-1.0]": []}
            for p, y in prob_pairs:
                if p < 0.4:
                    bins["low_prob [0.0-0.4)"].append(y)
                elif p < 0.7:
                    bins["mid_prob [0.4-0.7)"].append(y)
                else:
                    bins["high_prob [0.7-1.0]"].append(y)

            for b_name, ys in bins.items():
                calibration_bins[b_name] = {
                    "count": len(ys),
                    "actual_win_rate_pct": round((sum(ys) / len(ys) * 100.0), 1) if ys else 0.0,
                }

        recommendations: list[str] = []
        if exec_drag > (n * 0.20):
            recommendations.append(
                f"Execution drag affected {exec_drag}/{n} trades ({(exec_drag/n)*100:.1f}%). "
                "Recommend increasing take-profit target or raising minimum pool liquidity floor."
            )
        if liq_traps > 0:
            recommendations.append(
                f"{liq_traps} liquidity trap(s) detected. Recommend tightening deployer holder concentration filters."
            )
        if false_pos > (n * 0.30):
            recommendations.append(
                f"High false-positive rate ({false_pos}/{n}). Model probability threshold should be raised from 0.60 to 0.75."
            )

        return LearningInsightsReport(
            total_analyzed_trades=n,
            winning_trades=wins,
            losing_trades=losses,
            false_positives_count=false_pos,
            execution_drag_count=exec_drag,
            liquidity_traps_count=liq_traps,
            unforced_losses_count=unforced,
            total_friction_drag_usd=round(total_fees, 2),
            average_slippage_usd=round(total_fees / n, 2),
            model_brier_score=round(brier, 4) if brier is not None else None,
            probability_calibration=calibration_bins,
            recommended_strategy_adjustments=recommendations,
        )
