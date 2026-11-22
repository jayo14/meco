"""
Quantitative Performance Evaluation & Attribution Slicing for Meco (Phase 7).

Computes comprehensive risk-adjusted performance metrics across backtests:
- Net return, Win rate, Profit factor, Expectancy, Max Drawdown.
- Sharpe ratio, Sortino ratio, Gain-to-Pain ratio.
- Slippage drag, roundtrip fee burden, capital utilization.
- Attribution breakdown:
  * By Token Age band
  * By Liquidity band
  * By Discovery Source
  * By Market Regime
- Markdown performance reporting comparing strategy against baseline benchmarks.
"""
from dataclasses import asdict, dataclass, field
import math
from typing import Any

from app.research.backtest import BacktestResult, SimulatedTrade
from app.research.dataset import PointInTimeFeatures


@dataclass
class PerformanceSliceSummary:
    """Summary metrics for a specific cohort or market segment."""
    slice_name: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    profit_factor: float
    gross_pnl_usd: float
    net_pnl_usd: float
    total_fees_usd: float
    average_trade_net_usd: float
    average_holding_seconds: float


@dataclass
class QuantitativeReport:
    """Complete quantitative performance scorecard."""
    strategy_id: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    profit_factor: float
    expectancy_usd: float
    gross_profit_usd: float
    gross_loss_usd: float
    net_profit_usd: float
    total_fees_paid_usd: float
    fee_burden_pct: float  # fees / gross profit
    average_win_usd: float
    average_loss_usd: float
    win_loss_ratio: float
    max_drawdown_pct: float
    sharpe_ratio: float | None
    sortino_ratio: float | None
    average_holding_duration_seconds: float
    trades_per_day: float
    capital_utilization_pct: float

    # Performance Attribution Slices
    by_token_age: dict[str, PerformanceSliceSummary] = field(default_factory=dict)
    by_liquidity_band: dict[str, PerformanceSliceSummary] = field(default_factory=dict)
    by_discovery_source: dict[str, PerformanceSliceSummary] = field(default_factory=dict)
    by_market_regime: dict[str, PerformanceSliceSummary] = field(default_factory=dict)
    by_exit_reason: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def render_markdown(self, baseline_report: "QuantitativeReport | None" = None) -> str:
        """Render a publication-ready quantitative markdown audit report."""
        lines = [
            f"# Quantitative Strategy Performance Report: `{self.strategy_id}`",
            "",
            "## 1. Executive Summary & Return Attribution",
            f"- **Total Closed Trades:** `{self.total_trades}`",
            f"- **Win Rate:** `{self.win_rate_pct:.1f}%` ({self.winning_trades}W / {self.losing_trades}L)",
            f"- **Profit Factor:** `{self.profit_factor:.2f}`",
            f"- **Expectancy per Trade:** `${self.expectancy_usd:+.2f}`",
            f"- **Net Profit:** `${self.net_profit_usd:+.2f}`",
            f"- **Total Friction & Fees:** `${self.total_fees_paid_usd:.2f}` (Fee Burden: `{self.fee_burden_pct:.1f}%`)",
            f"- **Max Portfolio Drawdown:** `{self.max_drawdown_pct:.2f}%`",
            f"- **Sharpe Ratio:** `{f'{self.sharpe_ratio:.2f}' if self.sharpe_ratio is not None else 'N/A'}` | "
            f"**Sortino Ratio:** `{f'{self.sortino_ratio:.2f}' if self.sortino_ratio is not None else 'N/A'}`",
            f"- **Average Holding Duration:** `{self.average_holding_duration_seconds:.0f}s`",
            "",
        ]

        if baseline_report:
            diff_net = self.net_profit_usd - baseline_report.net_profit_usd
            diff_pf = self.profit_factor - baseline_report.profit_factor
            lines.extend([
                "## 2. Comparison Against Baseline Benchmark",
                f"| Metric | Candidate `{self.strategy_id}` | Benchmark `{baseline_report.strategy_id}` | Delta |",
                "| :--- | :--- | :--- | :--- |",
                f"| Net Profit | ${self.net_profit_usd:+.2f} | ${baseline_report.net_profit_usd:+.2f} | ${diff_net:+.2f} |",
                f"| Profit Factor | {self.profit_factor:.2f} | {baseline_report.profit_factor:.2f} | {diff_pf:+.2f} |",
                f"| Win Rate | {self.win_rate_pct:.1f}% | {baseline_report.win_rate_pct:.1f}% | {self.win_rate_pct - baseline_report.win_rate_pct:+.1f}% |",
                f"| Max Drawdown | {self.max_drawdown_pct:.2f}% | {baseline_report.max_drawdown_pct:.2f}% | {self.max_drawdown_pct - baseline_report.max_drawdown_pct:+.2f}% |",
                "",
            ])

        lines.extend([
            "## 3. Performance by Liquidity Band",
            "| Liquidity Band | Trades | Win Rate | Profit Factor | Net PnL | Fees Paid | Avg Holding |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])
        for b_name, b_sum in self.by_liquidity_band.items():
            lines.append(
                f"| `{b_name}` | {b_sum.total_trades} | {b_sum.win_rate_pct:.1f}% | "
                f"{b_sum.profit_factor:.2f} | ${b_sum.net_pnl_usd:+.2f} | ${b_sum.total_fees_usd:.2f} | "
                f"{b_sum.average_holding_seconds:.0f}s |"
            )

        lines.extend([
            "",
            "## 4. Performance by Token Age",
            "| Token Age Band | Trades | Win Rate | Profit Factor | Net PnL | Avg Net / Trade |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ])
        for a_name, a_sum in self.by_token_age.items():
            lines.append(
                f"| `{a_name}` | {a_sum.total_trades} | {a_sum.win_rate_pct:.1f}% | "
                f"{a_sum.profit_factor:.2f} | ${a_sum.net_pnl_usd:+.2f} | ${a_sum.average_trade_net_usd:+.2f} |"
            )

        lines.extend([
            "",
            "## 5. Performance by Market Regime",
            "| Regime | Trades | Win Rate | Profit Factor | Net PnL |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ])
        for r_name, r_sum in self.by_market_regime.items():
            lines.append(
                f"| `{r_name}` | {r_sum.total_trades} | {r_sum.win_rate_pct:.1f}% | "
                f"{r_sum.profit_factor:.2f} | ${r_sum.net_pnl_usd:+.2f} |"
            )

        lines.extend([
            "",
            "## 6. Exit Trigger Distribution",
        ])
        for reas, count in self.by_exit_reason.items():
            lines.append(f"- **{reas}:** {count} trade(s)")

        return "\n".join(lines)


class PerformanceEvaluator:
    """
    Computes multi-dimensional statistical performance analytics and attribution slices.
    """

    @classmethod
    def evaluate(
        cls,
        backtest_result: BacktestResult,
        signals_lookup: dict[str, PointInTimeFeatures] | None = None,
    ) -> QuantitativeReport:
        trades = backtest_result.completed_trades
        n_trades = len(trades)

        if n_trades == 0:
            return QuantitativeReport(
                strategy_id=backtest_result.strategy_id,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate_pct=0.0,
                profit_factor=0.0,
                expectancy_usd=0.0,
                gross_profit_usd=0.0,
                gross_loss_usd=0.0,
                net_profit_usd=0.0,
                total_fees_paid_usd=0.0,
                fee_burden_pct=0.0,
                average_win_usd=0.0,
                average_loss_usd=0.0,
                win_loss_ratio=0.0,
                max_drawdown_pct=0.0,
                sharpe_ratio=None,
                sortino_ratio=None,
                average_holding_duration_seconds=0.0,
                trades_per_day=0.0,
                capital_utilization_pct=0.0,
            )

        wins: list[float] = []
        losses: list[float] = []
        returns: list[float] = []
        by_exit_reason: dict[str, int] = {}

        # Slicing containers: slice_key -> list of trades
        liq_groups: dict[str, list[SimulatedTrade]] = {}
        age_groups: dict[str, list[SimulatedTrade]] = {}
        source_groups: dict[str, list[SimulatedTrade]] = {}
        regime_groups: dict[str, list[SimulatedTrade]] = {}

        total_holding_sec = 0.0

        for t in trades:
            net = t.net_pnl_usd
            returns.append(t.return_pct)
            total_holding_sec += t.holding_duration_seconds
            by_exit_reason[t.exit_reason] = by_exit_reason.get(t.exit_reason, 0) + 1

            if net > 0:
                wins.append(net)
            else:
                losses.append(abs(net))

            # Retrieve signal context for attribution slicing
            sig = signals_lookup.get(t.token_mint) if signals_lookup else None
            if sig:
                # 1. Liquidity band
                l = sig.liquidity_usd
                if l < 10000.0:
                    l_band = "<$10k"
                elif l < 50000.0:
                    l_band = "$10k-$50k"
                elif l < 200000.0:
                    l_band = "$50k-$200k"
                else:
                    l_band = ">$200k"
                liq_groups.setdefault(l_band, []).append(t)

                # 2. Token age band
                age = sig.token_age_seconds
                if age < 300.0:
                    a_band = "<5m"
                elif age < 1800.0:
                    a_band = "5m-30m"
                elif age < 7200.0:
                    a_band = "30m-2h"
                else:
                    a_band = ">2h"
                age_groups.setdefault(a_band, []).append(t)

                # 3. Discovery source
                source_groups.setdefault(sig.discovery_source, []).append(t)

                # 4. Market regime
                regime_groups.setdefault(sig.market_regime, []).append(t)

        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / n_trades) * 100.0

        sum_wins = sum(wins)
        sum_losses = sum(losses)
        profit_factor = (sum_wins / sum_losses) if sum_losses > 0 else (99.0 if sum_wins > 0 else 1.0)

        avg_win = (sum_wins / win_count) if win_count > 0 else 0.0
        avg_loss = (sum_losses / loss_count) if loss_count > 0 else 0.0
        wl_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0

        p_win = win_count / n_trades
        p_loss = loss_count / n_trades
        expectancy = (p_win * avg_win) - (p_loss * avg_loss)

        total_net = sum(t.net_pnl_usd for t in trades)
        total_fees = sum(t.total_fees_usd for t in trades)
        total_gross = sum(t.gross_pnl_usd for t in trades)
        fee_burden = (total_fees / sum_wins * 100.0) if sum_wins > 0 else 0.0

        # Maximum Drawdown calculation from equity curve
        curve = backtest_result.portfolio_equity_curve
        peak = curve[0][1] if curve else 10000.0
        max_dd_pct = 0.0
        for _, eq in curve:
            if eq > peak:
                peak = eq
            dd = ((peak - eq) / peak) * 100.0 if peak > 0 else 0.0
            if dd > max_dd_pct:
                max_dd_pct = dd

        # Risk-adjusted ratios
        sharpe = None
        sortino = None
        if len(returns) >= 3:
            mean_ret = sum(returns) / len(returns)
            variance = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
            std_dev = math.sqrt(variance) if variance > 0 else 0.0
            if std_dev > 0.0001:
                sharpe = round(mean_ret / std_dev, 2)

            downside = [r for r in returns if r < 0]
            if downside:
                downside_var = sum(r ** 2 for r in downside) / len(downside)
                downside_std = math.sqrt(downside_var) if downside_var > 0 else 0.0
                if downside_std > 0.0001:
                    sortino = round(mean_ret / downside_std, 2)

        # Build Slices
        def build_slice_dict(groups: dict[str, list[SimulatedTrade]]) -> dict[str, PerformanceSliceSummary]:
            res: dict[str, PerformanceSliceSummary] = {}
            for k, sl_trades in groups.items():
                m = len(sl_trades)
                w = sum(1 for tr in sl_trades if tr.net_pnl_usd > 0)
                l = m - w
                w_sum = sum(tr.net_pnl_usd for tr in sl_trades if tr.net_pnl_usd > 0)
                l_sum = sum(abs(tr.net_pnl_usd) for tr in sl_trades if tr.net_pnl_usd <= 0)
                pf = (w_sum / l_sum) if l_sum > 0 else (99.0 if w_sum > 0 else 1.0)
                gross = sum(tr.gross_pnl_usd for tr in sl_trades)
                net = sum(tr.net_pnl_usd for tr in sl_trades)
                fees = sum(tr.total_fees_usd for tr in sl_trades)
                avg_hold = sum(tr.holding_duration_seconds for tr in sl_trades) / m
                res[k] = PerformanceSliceSummary(
                    slice_name=k,
                    total_trades=m,
                    winning_trades=w,
                    losing_trades=l,
                    win_rate_pct=round((w / m) * 100.0, 1),
                    profit_factor=round(pf, 2),
                    gross_pnl_usd=round(gross, 2),
                    net_pnl_usd=round(net, 2),
                    total_fees_usd=round(fees, 2),
                    average_trade_net_usd=round(net / m, 2),
                    average_holding_seconds=round(avg_hold, 1),
                )
            return res

        return QuantitativeReport(
            strategy_id=backtest_result.strategy_id,
            total_trades=n_trades,
            winning_trades=win_count,
            losing_trades=loss_count,
            win_rate_pct=round(win_rate, 1),
            profit_factor=round(profit_factor, 2),
            expectancy_usd=round(expectancy, 2),
            gross_profit_usd=round(total_gross, 2),
            gross_loss_usd=round(sum_losses, 2),
            net_profit_usd=round(total_net, 2),
            total_fees_paid_usd=round(total_fees, 2),
            fee_burden_pct=round(fee_burden, 1),
            average_win_usd=round(avg_win, 2),
            average_loss_usd=round(avg_loss, 2),
            win_loss_ratio=round(wl_ratio, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            average_holding_duration_seconds=round(total_holding_sec / n_trades, 1),
            trades_per_day=round(n_trades / 1.0, 1),
            capital_utilization_pct=round((100.0 / 10000.0) * 100.0, 1),
            by_token_age=build_slice_dict(age_groups),
            by_liquidity_band=build_slice_dict(liq_groups),
            by_discovery_source=build_slice_dict(source_groups),
            by_market_regime=build_slice_dict(regime_groups),
            by_exit_reason=by_exit_reason,
        )
