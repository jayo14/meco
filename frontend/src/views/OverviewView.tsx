import React from "react";
import { SystemOverview } from "../api/client";
import { formatUsd, formatPct, cn } from "../lib/utils";

interface OverviewViewProps {
  overview?: SystemOverview;
  isLoading: boolean;
  onNavigate: (tab: string) => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  overview,
  isLoading,
  onNavigate,
}) => {
  if (isLoading && !overview) {
    return (
      <div className="flex items-center justify-center h-64 text-muted font-mono text-sm">
        <span className="material-symbols-rounded animate-spin mr-2">progress_activity</span>
        Synchronizing system telemetry...
      </div>
    );
  }

  const kpis = [
    {
      title: "Tokens Discovered",
      value: overview?.total_tokens_discovered ?? 0,
      subValue: `+${overview?.new_tokens_last_24h ?? 0} in last 24h`,
      icon: "radar",
      color: "text-primary",
      onClick: () => onNavigate("discovery"),
    },
    {
      title: "Active Investigations",
      value: overview?.tokens_under_investigation_count ?? 0,
      subValue: `${overview?.tokens_enriching_count ?? 0} enriching metadata`,
      icon: "smart_toy",
      color: "text-accent",
      onClick: () => onNavigate("agents"),
    },
    {
      title: "Watchlisted Opportunities",
      value: overview?.watchlisted_opportunities_count ?? 0,
      subValue: `${overview?.rejected_opportunities_count ?? 0} rejected by hard risk`,
      icon: "balance",
      color: "text-warning",
      onClick: () => onNavigate("decisions"),
    },
    {
      title: "Simulated Net Equity",
      value: formatUsd(overview?.portfolio_net_equity),
      subValue: `Drawdown: ${overview?.current_drawdown_pct.toFixed(2) ?? "0.00"}%`,
      icon: "account_balance_wallet",
      color: "text-success",
      onClick: () => onNavigate("trading"),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Top Banner Notice: Paper Simulation Mode */}
      <div className="bg-surface-card border border-primary/20 rounded-xl p-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-lg bg-primary/10 border border-primary/30 flex items-center justify-center text-primary">
            <span className="material-symbols-rounded text-xl">science</span>
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-100 flex items-center space-x-2">
              <span>Autonomous Paper Simulation Gateway Active</span>
              <span className="text-[10px] bg-primary/20 text-primary border border-primary/40 px-2 py-0.5 rounded-full font-mono uppercase font-bold">
                Zero Broadcast
              </span>
            </h2>
            <p className="text-xs text-muted">
              Live transaction signing is disabled. All entries, exits, slippage, and AMM pricing are strictly simulated.
            </p>
          </div>
        </div>

        <button
          onClick={() => onNavigate("controls")}
          className="hidden sm:flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-surface border border-surface-border text-xs text-slate-300 hover:text-slate-100 hover:border-primary/40 transition-colors"
        >
          <span className="material-symbols-rounded text-sm">tune</span>
          <span>Configure Engine</span>
        </button>
      </div>

      {/* KPI Matrix Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((kpi, idx) => (
          <div
            key={idx}
            onClick={kpi.onClick}
            className="bg-surface border border-surface-border hover:border-primary/40 rounded-xl p-5 cursor-pointer transition-all hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)] group"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-medium text-muted">{kpi.title}</span>
              <span className={cn("material-symbols-rounded text-xl transition-transform group-hover:scale-110", kpi.color)}>
                {kpi.icon}
              </span>
            </div>
            <div className="text-2xl font-bold font-mono text-slate-100 mb-1">
              {kpi.value}
            </div>
            <div className="text-xs text-muted flex items-center space-x-1">
              <span>{kpi.subValue}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Detailed Portfolio & Strategy Strip */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Paper Accounting Breakdown */}
        <div className="lg:col-span-2 bg-surface border border-surface-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4 border-b border-surface-border pb-3">
            <div className="flex items-center space-x-2">
              <span className="material-symbols-rounded text-primary">pie_chart</span>
              <h3 className="text-sm font-semibold text-slate-100">Paper Capital & PnL Ledger</h3>
            </div>
            <span className="text-xs font-mono text-muted">Strict Decimal Accounting</span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
            <div className="bg-surface-card p-3 rounded-lg border border-surface-border">
              <div className="text-[11px] text-muted uppercase font-mono">Available</div>
              <div className="text-base font-bold font-mono text-slate-100">
                {formatUsd(overview?.portfolio_available_capital)}
              </div>
            </div>
            <div className="bg-surface-card p-3 rounded-lg border border-surface-border">
              <div className="text-[11px] text-muted uppercase font-mono">Reserved</div>
              <div className="text-base font-bold font-mono text-warning">
                {formatUsd(overview?.portfolio_reserved_capital)}
              </div>
            </div>
            <div className="bg-surface-card p-3 rounded-lg border border-surface-border">
              <div className="text-[11px] text-muted uppercase font-mono">Realised PnL</div>
              <div className={cn(
                "text-base font-bold font-mono",
                (overview?.realised_pnl_usd ?? 0) >= 0 ? "text-success" : "text-danger"
              )}>
                {formatUsd(overview?.realised_pnl_usd)}
              </div>
            </div>
            <div className="bg-surface-card p-3 rounded-lg border border-surface-border">
              <div className="text-[11px] text-muted uppercase font-mono">Unrealised PnL</div>
              <div className={cn(
                "text-base font-bold font-mono",
                (overview?.unrealised_pnl_usd ?? 0) >= 0 ? "text-success" : "text-danger"
              )}>
                {formatUsd(overview?.unrealised_pnl_usd)}
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between bg-surface-card/60 p-3 rounded-lg border border-surface-border text-xs">
            <span className="text-muted">Total Paid Slippage, Priority Gas & DEX Fees:</span>
            <span className="font-mono font-semibold text-slate-200">
              {formatUsd(overview?.total_fees_paid_usd)}
            </span>
          </div>
        </div>

        {/* Right Col: Active Autonomous Strategies */}
        <div className="bg-surface border border-surface-border rounded-xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4 border-b border-surface-border pb-3">
              <div className="flex items-center space-x-2">
                <span className="material-symbols-rounded text-accent">memory</span>
                <h3 className="text-sm font-semibold text-slate-100">Active Strategies</h3>
              </div>
              <span className="text-xs font-mono text-muted">
                {overview?.active_strategies_count ?? 0} running
              </span>
            </div>

            <div className="space-y-3">
              {(overview?.active_strategies ?? ["momentum_breakout", "volume_spike_scalp", "ml_momentum_v1"]).map((strat, i) => (
                <div key={i} className="flex items-center justify-between bg-surface-card p-2.5 rounded-lg border border-surface-border">
                  <div className="flex items-center space-x-2.5">
                    <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
                    <span className="text-xs font-mono font-medium text-slate-200">{strat}</span>
                  </div>
                  <span className="text-[10px] text-muted font-mono uppercase bg-surface px-2 py-0.5 rounded border border-surface-border">
                    Autonomous
                  </span>
                </div>
              ))}
            </div>
          </div>

          <button
            onClick={() => onNavigate("controls")}
            className="w-full mt-4 py-2 rounded-lg bg-surface-card hover:bg-surface-border text-xs font-medium text-slate-300 border border-surface-border transition-colors text-center"
          >
            Manage Strategy Parameters
          </button>
        </div>
      </div>
    </div>
  );
};
