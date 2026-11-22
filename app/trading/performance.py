"""
Trading History and Performance Analytics for Meco Paper Trading Engine (Phase 6).
Evaluates paper trade records to compute win rates, profit factors, Sharpe ratios,
fee drags, MFE/MAE distributions, and strategy attribution.
"""
from datetime import datetime
from decimal import Decimal
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.trading.accounting import quantize_usd
from app.trading.models import PaperPosition, PortfolioSnapshot, PositionStatus


class StrategyPerformanceSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    strategy_id: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    profit_factor: float
    gross_realised_pnl_usd: Decimal
    total_fees_usd: Decimal
    net_realised_pnl_usd: Decimal
    average_trade_pnl_usd: Decimal
    average_holding_duration_seconds: float
    average_mfe_usd: Decimal
    average_mae_usd: Decimal


class TradingPerformanceReport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    generated_at: datetime
    total_trades_count: int
    winning_trades_count: int
    losing_trades_count: int
    win_rate_pct: float
    profit_factor: float
    gross_realised_pnl_usd: Decimal
    total_fees_usd: Decimal
    net_realised_pnl_usd: Decimal
    average_trade_pnl_usd: Decimal
    max_portfolio_drawdown_pct: Decimal
    sharpe_ratio: float | None = None
    by_strategy: dict[str, StrategyPerformanceSummary] = Field(default_factory=dict)
    by_exit_reason: dict[str, int] = Field(default_factory=dict)

    def render_markdown_report(self) -> str:
        """Render a formatted performance analytics report."""
        lines = [
            "# Paper Trading Performance Report",
            f"**Generated At:** `{self.generated_at.isoformat()}`  ",
            f"**Total Closed Positions:** `{self.total_trades_count}`  ",
            f"**Win Rate:** `{self.win_rate_pct:.1f}%` ({self.winning_trades_count}W / {self.losing_trades_count}L)  ",
            f"**Profit Factor:** `{self.profit_factor:.2f}`  ",
            f"**Gross Realised PnL:** `${self.gross_realised_pnl_usd}`  ",
            f"**Total Friction & Fees:** `${self.total_fees_usd}`  ",
            f"**Net Realised PnL:** `${self.net_realised_pnl_usd}`  ",
            f"**Max Portfolio Drawdown:** `{self.max_portfolio_drawdown_pct:.2f}%`  ",
            f"**Sharpe Ratio:** `{f'{self.sharpe_ratio:.2f}' if self.sharpe_ratio is not None else 'N/A'}`  ",
            "",
            "## Strategy Performance Attribution",
            "| Strategy | Trades | Win Rate | Profit Factor | Gross PnL | Fees | Net PnL | Avg Holding |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for s_id, s_perf in self.by_strategy.items():
            lines.append(
                f"| `{s_id}` | {s_perf.total_trades} | {s_perf.win_rate_pct:.1f}% | "
                f"{s_perf.profit_factor:.2f} | ${s_perf.gross_realised_pnl_usd} | ${s_perf.total_fees_usd} | "
                f"${s_perf.net_realised_pnl_usd} | {s_perf.average_holding_duration_seconds:.0f}s |"
            )

        lines.extend([
            "",
            "## Exits by Trigger Reason",
        ])
        for r_name, r_count in self.by_exit_reason.items():
            lines.append(f"- **{r_name}:** {r_count} position(s)")

        return "\n".join(lines)


class PerformanceAnalyzer:
    """
    Computes performance metrics across trade history.
    """

    @classmethod
    def evaluate(
        cls,
        closed_positions: list[PaperPosition],
        portfolio: PortfolioSnapshot | None = None,
        as_of: datetime | None = None,
    ) -> TradingPerformanceReport:
        now = as_of or (datetime.now() if not portfolio else portfolio.timestamp)

        total_trades = len(closed_positions)
        if total_trades == 0:
            return TradingPerformanceReport(
                generated_at=now,
                total_trades_count=0,
                winning_trades_count=0,
                losing_trades_count=0,
                win_rate_pct=0.0,
                profit_factor=0.0,
                gross_realised_pnl_usd=Decimal("0.00"),
                total_fees_usd=Decimal("0.00"),
                net_realised_pnl_usd=Decimal("0.00"),
                average_trade_pnl_usd=Decimal("0.00"),
                max_portfolio_drawdown_pct=portfolio.current_drawdown_pct if portfolio else Decimal("0.00"),
            )

        winning_trades = 0
        losing_trades = 0
        total_gross_pnl = Decimal("0.00")
        total_fees = Decimal("0.00")
        total_profits = Decimal("0.00")
        total_losses = Decimal("0.00")
        trade_returns: list[float] = []

        by_strategy_groups: dict[str, list[PaperPosition]] = {}
        by_exit_reason: dict[str, int] = {}

        for p in closed_positions:
            net_pnl = p.realised_pnl_usd - p.total_fees_paid_usd
            total_gross_pnl += p.realised_pnl_usd
            total_fees += p.total_fees_paid_usd

            if net_pnl > Decimal("0.00"):
                winning_trades += 1
                total_profits += net_pnl
            else:
                losing_trades += 1
                total_losses += abs(net_pnl)

            # Return pct on committed capital
            if p.capital_committed > Decimal("0.00"):
                ret = float(net_pnl / p.capital_committed)
                trade_returns.append(ret)

            # Strategy group
            by_strategy_groups.setdefault(p.strategy_id, []).append(p)

            # Exit reason
            reason_str = p.exit_reason.value if p.exit_reason else "unknown"
            by_exit_reason[reason_str] = by_exit_reason.get(reason_str, 0) + 1

        win_rate = (winning_trades / total_trades) * 100.0
        profit_factor = float(total_profits / total_losses) if total_losses > Decimal("0.00") else (99.0 if total_profits > Decimal("0.00") else 1.0)
        net_realised = quantize_usd(total_gross_pnl - total_fees)
        avg_trade_pnl = quantize_usd(net_realised / Decimal(str(total_trades)))

        # Annualized Sharpe ratio approximation if >= 5 trades
        sharpe = None
        if len(trade_returns) >= 5:
            mean_ret = sum(trade_returns) / len(trade_returns)
            variance = sum((r - mean_ret) ** 2 for r in trade_returns) / (len(trade_returns) - 1)
            std_dev = math.sqrt(variance)
            if std_dev > 0.0001:
                # Per-trade Sharpe
                sharpe = round(mean_ret / std_dev, 2)

        # Build Strategy summaries
        strategy_summaries: dict[str, StrategyPerformanceSummary] = {}
        for s_id, s_positions in by_strategy_groups.items():
            s_total = len(s_positions)
            s_wins = sum(1 for p in s_positions if (p.realised_pnl_usd - p.total_fees_paid_usd) > Decimal("0.00"))
            s_losses = s_total - s_wins
            s_gross = quantize_usd(sum(p.realised_pnl_usd for p in s_positions))
            s_fees = quantize_usd(sum(p.total_fees_paid_usd for p in s_positions))
            s_net = quantize_usd(s_gross - s_fees)
            s_profits = sum(p.realised_pnl_usd - p.total_fees_paid_usd for p in s_positions if (p.realised_pnl_usd - p.total_fees_paid_usd) > Decimal("0.00"))
            s_loss_sum = sum(abs(p.realised_pnl_usd - p.total_fees_paid_usd) for p in s_positions if (p.realised_pnl_usd - p.total_fees_paid_usd) <= Decimal("0.00"))
            s_pf = float(s_profits / s_loss_sum) if s_loss_sum > Decimal("0.00") else (99.0 if s_profits > Decimal("0.00") else 1.0)
            s_avg_dur = sum(p.holding_duration_seconds() for p in s_positions) / s_total
            s_avg_mfe = quantize_usd(sum(p.max_favourable_excursion_usd for p in s_positions) / Decimal(str(s_total)))
            s_avg_mae = quantize_usd(sum(p.max_adverse_excursion_usd for p in s_positions) / Decimal(str(s_total)))

            strategy_summaries[s_id] = StrategyPerformanceSummary(
                strategy_id=s_id,
                total_trades=s_total,
                winning_trades=s_wins,
                losing_trades=s_losses,
                win_rate_pct=round((s_wins / s_total) * 100.0, 1),
                profit_factor=round(s_pf, 2),
                gross_realised_pnl_usd=s_gross,
                total_fees_usd=s_fees,
                net_realised_pnl_usd=s_net,
                average_trade_pnl_usd=quantize_usd(s_net / Decimal(str(s_total))),
                average_holding_duration_seconds=round(s_avg_dur, 1),
                average_mfe_usd=s_avg_mfe,
                average_mae_usd=s_avg_mae,
            )

        return TradingPerformanceReport(
            generated_at=now,
            total_trades_count=total_trades,
            winning_trades_count=winning_trades,
            losing_trades_count=losing_trades,
            win_rate_pct=round(win_rate, 1),
            profit_factor=round(profit_factor, 2),
            gross_realised_pnl_usd=quantize_usd(total_gross_pnl),
            total_fees_usd=quantize_usd(total_fees),
            net_realised_pnl_usd=net_realised,
            average_trade_pnl_usd=avg_trade_pnl,
            max_portfolio_drawdown_pct=portfolio.current_drawdown_pct if portfolio else Decimal("0.00"),
            sharpe_ratio=sharpe,
            by_strategy=strategy_summaries,
            by_exit_reason=by_exit_reason,
        )
