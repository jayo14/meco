import React from "react";
import { formatUsd, formatPct, cn } from "../lib/utils";

interface ResearchViewProps {
  performance: any;
  isLoading: boolean;
  onRefresh: () => void;
}

export const ResearchView: React.FC<ResearchViewProps> = ({
  performance,
  isLoading,
  onRefresh,
}) => {
  if (isLoading && !performance) {
    return (
      <div className="flex items-center justify-center h-64 text-muted font-mono text-sm">
        <span className="material-symbols-rounded animate-spin mr-2">progress_activity</span>
        Computing quantitative performance metrics...
      </div>
    );
  }

  const p = performance || {};
  const curve: { timestamp: string; equity: number }[] = p.equity_curve || [];

  // Calculate SVG sparkline points
  const minEq = curve.length > 0 ? Math.min(...curve.map((c) => c.equity)) * 0.999 : 9990;
  const maxEq = curve.length > 0 ? Math.max(...curve.map((c) => c.equity)) * 1.001 : 10400;
  const range = maxEq - minEq || 1;

  const points = curve
    .map((c, i) => {
      const x = (i / (curve.length - 1 || 1)) * 500;
      const y = 120 - ((c.equity - minEq) / range) * 100;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="space-y-6">
      {/* Top Header Card */}
      <div className="bg-surface border border-surface-border p-5 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="material-symbols-rounded text-primary text-xl">insights</span>
            <h3 className="text-base font-bold text-slate-100 font-sans">Quantitative Research & Backtest Scorecard</h3>
          </div>
          <p className="text-xs text-muted font-mono mt-1">
            Period: {p.evaluation_period} | Sample: {p.sample_size_trades} trades across {p.sample_size_tokens} tokens
          </p>
        </div>

        <button
          onClick={onRefresh}
          className="self-start sm:self-center px-3 py-1.5 rounded-lg bg-surface-card hover:bg-surface-border text-xs text-slate-200 border border-surface-border font-mono transition-colors"
        >
          Re-evaluate Slices
        </button>
      </div>

      {/* KPI Matrix */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 font-mono">
        <div className="bg-surface p-3.5 rounded-xl border border-surface-border">
          <div className="text-[10px] text-muted uppercase">Win Rate</div>
          <div className="text-lg font-bold text-slate-100">{p.win_rate_pct?.toFixed(1)}%</div>
          <div className="text-[10px] text-muted">Out-of-Sample</div>
        </div>
        <div className="bg-surface p-3.5 rounded-xl border border-surface-border">
          <div className="text-[10px] text-muted uppercase">Profit Factor</div>
          <div className="text-lg font-bold text-success">{p.profit_factor?.toFixed(2)}</div>
          <div className="text-[10px] text-muted">Min Threshold: 1.25</div>
        </div>
        <div className="bg-surface p-3.5 rounded-xl border border-surface-border">
          <div className="text-[10px] text-muted uppercase">Expectancy</div>
          <div className="text-lg font-bold text-slate-100">{formatUsd(p.expectancy_usd)}</div>
          <div className="text-[10px] text-muted">Per Simulated Trade</div>
        </div>
        <div className="bg-surface p-3.5 rounded-xl border border-surface-border">
          <div className="text-[10px] text-muted uppercase">Max Drawdown</div>
          <div className="text-lg font-bold text-warning">{p.max_drawdown_pct?.toFixed(2)}%</div>
          <div className="text-[10px] text-muted">Ceiling: 20.0%</div>
        </div>
        <div className="bg-surface p-3.5 rounded-xl border border-surface-border">
          <div className="text-[10px] text-muted uppercase">Sharpe Ratio</div>
          <div className="text-lg font-bold text-primary">{p.sharpe_ratio?.toFixed(2) || "N/A"}</div>
          <div className="text-[10px] text-muted">Sortino: {p.sortino_ratio?.toFixed(2) || "N/A"}</div>
        </div>
        <div className="bg-surface p-3.5 rounded-xl border border-surface-border">
          <div className="text-[10px] text-muted uppercase">Avg Holding</div>
          <div className="text-lg font-bold text-slate-100">{p.average_holding_duration_seconds?.toFixed(0)}s</div>
          <div className="text-[10px] text-muted">~{(p.average_holding_duration_seconds / 60).toFixed(1)} mins</div>
        </div>
      </div>

      {/* Equity Curve & Champion / Challenger Status */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Equity Curve Sparkline Chart */}
        <div className="lg:col-span-2 bg-surface border border-surface-border rounded-xl p-5 font-mono">
          <div className="flex items-center justify-between mb-4 border-b border-surface-border pb-3">
            <h4 className="text-xs font-bold text-slate-100 uppercase tracking-wider">
              Simulated Portfolio Equity Curve
            </h4>
            <span className="text-xs text-success font-semibold">Net Profit: +${p.net_profit_usd}</span>
          </div>

          <div className="h-44 w-full flex flex-col justify-end">
            <svg viewBox="0 0 500 130" className="w-full h-full overflow-visible">
              <polyline
                fill="none"
                stroke="#00f0ff"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                points={points}
              />
            </svg>
            <div className="flex justify-between text-[10px] text-muted pt-2 border-t border-surface-border">
              <span>{curve[0]?.timestamp.slice(11, 16) || "00:00"}</span>
              <span>{curve[Math.floor(curve.length / 2)]?.timestamp.slice(11, 16) || "12:00"}</span>
              <span>{curve[curve.length - 1]?.timestamp.slice(11, 16) || "23:59"}</span>
            </div>
          </div>
        </div>

        {/* Champion / Challenger Promotion Status */}
        <div className="bg-surface border border-surface-border rounded-xl p-5 flex flex-col justify-between font-mono">
          <div>
            <div className="flex items-center justify-between mb-3 border-b border-surface-border pb-3">
              <h4 className="text-xs font-bold text-slate-100 uppercase tracking-wider">Champion / Challenger</h4>
              <span className="text-[10px] text-primary bg-primary/10 border border-primary/30 px-2 py-0.5 rounded">
                Gated Gateway
              </span>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <span className="text-muted block text-[10px]">ACTIVE CHAMPION</span>
                <span className="text-slate-100 font-bold text-sm">
                  {p.champion_status?.active_champion_id || "heuristic_baseline"}
                </span>
                <span className="text-muted text-[11px] ml-1">
                  v{p.champion_status?.active_champion_version || "1.0.0"}
                </span>
              </div>

              <div className="p-3 bg-surface-card rounded-lg border border-surface-border space-y-1 text-[11px]">
                <div className="flex justify-between">
                  <span className="text-muted">Total Audited Promotions:</span>
                  <span className="text-slate-200 font-semibold">{p.champion_status?.promotion_count || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted">Promotion Policy:</span>
                  <span className="text-success font-semibold">Strict Out-of-Sample</span>
                </div>
              </div>
            </div>
          </div>

          <div className="text-[10px] text-muted bg-surface-card/40 p-2.5 rounded border border-surface-border mt-4">
            Candidates cannot automatically self-promote. Must beat champion profit factor by &gt;5% on versioned manifests.
          </div>
        </div>
      </div>

      {/* Attribution Breakdown Tables */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 font-mono text-xs">
        {/* By Liquidity Band */}
        <div className="bg-surface border border-surface-border rounded-xl p-5">
          <h4 className="text-xs font-bold text-slate-100 uppercase tracking-wider mb-3">
            Performance by Liquidity Band
          </h4>
          <table className="w-full text-left">
            <thead className="text-[10px] text-muted border-b border-surface-border uppercase">
              <tr>
                <th className="py-2">Band</th>
                <th className="py-2">Trades</th>
                <th className="py-2">Win %</th>
                <th className="py-2">P. Factor</th>
                <th className="py-2 text-right">Net PnL</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {(p.attribution?.by_liquidity_band || []).map((row: any, i: number) => (
                <tr key={i} className="hover:bg-surface-card/40">
                  <td className="py-2 font-semibold text-slate-200">{row.band}</td>
                  <td className="py-2 text-muted">{row.trades}</td>
                  <td className="py-2">{row.win_rate.toFixed(1)}%</td>
                  <td className="py-2 text-primary">{row.profit_factor.toFixed(2)}</td>
                  <td className={cn("py-2 text-right font-bold", row.net_pnl >= 0 ? "text-success" : "text-danger")}>
                    {formatUsd(row.net_pnl)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* By Token Age Band */}
        <div className="bg-surface border border-surface-border rounded-xl p-5">
          <h4 className="text-xs font-bold text-slate-100 uppercase tracking-wider mb-3">
            Performance by Token Age
          </h4>
          <table className="w-full text-left">
            <thead className="text-[10px] text-muted border-b border-surface-border uppercase">
              <tr>
                <th className="py-2">Age Band</th>
                <th className="py-2">Trades</th>
                <th className="py-2">Win %</th>
                <th className="py-2">P. Factor</th>
                <th className="py-2 text-right">Net PnL</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {(p.attribution?.by_token_age || []).map((row: any, i: number) => (
                <tr key={i} className="hover:bg-surface-card/40">
                  <td className="py-2 font-semibold text-slate-200">{row.band}</td>
                  <td className="py-2 text-muted">{row.trades}</td>
                  <td className="py-2">{row.win_rate.toFixed(1)}%</td>
                  <td className="py-2 text-primary">{row.profit_factor.toFixed(2)}</td>
                  <td className={cn("py-2 text-right font-bold", row.net_pnl >= 0 ? "text-success" : "text-danger")}>
                    {formatUsd(row.net_pnl)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
