import React, { useState } from "react";
import { PaperPosition } from "../api/client";
import { formatUsd, formatPct, truncateMint, formatDuration, cn } from "../lib/utils";

interface TradingViewProps {
  positions: PaperPosition[];
  proposals: any[];
  isLoading: boolean;
  onRefresh: () => void;
  onClosePosition: (positionId: string) => void;
  onSelectToken: (mint: string) => void;
}

export const TradingView: React.FC<TradingViewProps> = ({
  positions,
  proposals,
  isLoading,
  onRefresh,
  onClosePosition,
  onSelectToken,
}) => {
  const [activeTab, setActiveTab] = useState<"open" | "closed" | "proposals">("open");

  const openPositions = positions.filter((p) => p.status === "open" || p.status === "partially_exited");
  const closedPositions = positions.filter((p) => p.status === "closed");

  const totalOpenValue = openPositions.reduce((sum, p) => sum + p.quantity * p.current_mark_price, 0);
  const totalUnrealised = openPositions.reduce((sum, p) => sum + p.unrealised_pnl_usd, 0);
  const totalRealised = closedPositions.reduce((sum, p) => sum + p.realised_pnl_usd, 0);

  return (
    <div className="space-y-6">
      {/* Paper Trading Banner */}
      <div className="bg-surface-card border border-warning/30 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-warning/10 border border-warning/30 flex items-center justify-center text-warning">
            <span className="material-symbols-rounded text-xl">candlestick_chart</span>
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-bold text-slate-100">Autonomous Paper Trading Engine</h3>
              <span className="text-[10px] font-mono uppercase bg-warning/20 text-warning px-2 py-0.5 rounded font-bold border border-warning/40">
                Simulated Sandbox
              </span>
            </div>
            <p className="text-xs text-muted">
              Constant-product AMM slippage, 0.25% Raydium fees, and Solana priority fees are factored into all marks.
            </p>
          </div>
        </div>

        <button
          onClick={onRefresh}
          className="self-start sm:self-center px-3 py-1.5 rounded-lg bg-surface border border-surface-border text-xs text-slate-300 hover:text-slate-100 transition-colors flex items-center space-x-1.5 font-mono"
        >
          <span className={cn("material-symbols-rounded text-base", isLoading && "animate-spin")}>refresh</span>
          <span>Refresh Fills</span>
        </button>
      </div>

      {/* Summary Scorecard */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 font-mono">
        <div className="bg-surface p-4 rounded-xl border border-surface-border">
          <div className="text-[10px] text-muted uppercase">Active Paper Positions</div>
          <div className="text-xl font-bold text-slate-100">{openPositions.length}</div>
          <div className="text-[11px] text-muted">Exposure: {formatUsd(totalOpenValue)}</div>
        </div>
        <div className="bg-surface p-4 rounded-xl border border-surface-border">
          <div className="text-[10px] text-muted uppercase">Open Unrealised PnL</div>
          <div className={cn("text-xl font-bold", totalUnrealised >= 0 ? "text-success" : "text-danger")}>
            {formatUsd(totalUnrealised)}
          </div>
          <div className="text-[11px] text-muted">Mark-to-Market</div>
        </div>
        <div className="bg-surface p-4 rounded-xl border border-surface-border">
          <div className="text-[10px] text-muted uppercase">Closed Realised PnL</div>
          <div className={cn("text-xl font-bold", totalRealised >= 0 ? "text-success" : "text-danger")}>
            {formatUsd(totalRealised)}
          </div>
          <div className="text-[11px] text-muted">{closedPositions.length} settled trades</div>
        </div>
        <div className="bg-surface p-4 rounded-xl border border-surface-border">
          <div className="text-[10px] text-muted uppercase">Pending Proposals</div>
          <div className="text-xl font-bold text-accent">{proposals.length}</div>
          <div className="text-[11px] text-muted">Risk Gateway queue</div>
        </div>
      </div>

      {/* View Switcher Tabs */}
      <div className="flex items-center space-x-2 border-b border-surface-border pb-2 text-xs font-mono">
        <button
          onClick={() => setActiveTab("open")}
          className={cn(
            "px-4 py-2 rounded-lg font-medium transition-colors flex items-center space-x-2",
            activeTab === "open" ? "bg-primary/20 text-primary border border-primary/30" : "text-muted hover:text-slate-100"
          )}
        >
          <span>Open Positions</span>
          <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-surface-card border border-surface-border">
            {openPositions.length}
          </span>
        </button>
        <button
          onClick={() => setActiveTab("closed")}
          className={cn(
            "px-4 py-2 rounded-lg font-medium transition-colors flex items-center space-x-2",
            activeTab === "closed" ? "bg-primary/20 text-primary border border-primary/30" : "text-muted hover:text-slate-100"
          )}
        >
          <span>Closed History</span>
          <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-surface-card border border-surface-border">
            {closedPositions.length}
          </span>
        </button>
        <button
          onClick={() => setActiveTab("proposals")}
          className={cn(
            "px-4 py-2 rounded-lg font-medium transition-colors flex items-center space-x-2",
            activeTab === "proposals" ? "bg-primary/20 text-primary border border-primary/30" : "text-muted hover:text-slate-100"
          )}
        >
          <span>Active Proposals</span>
          <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-surface-card border border-surface-border">
            {proposals.length}
          </span>
        </button>
      </div>

      {/* POSITIONS TABLE */}
      <div className="bg-surface border border-surface-border rounded-xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-surface-card border-b border-surface-border text-muted uppercase text-[10px]">
              <tr>
                <th className="py-3 px-4">Position / Token</th>
                <th className="py-3 px-4">Strategy</th>
                <th className="py-3 px-4">Entry / Current Price</th>
                <th className="py-3 px-4">Committed Size</th>
                <th className="py-3 px-4">Unrealised PnL</th>
                <th className="py-3 px-4">Peak / Excursions</th>
                <th className="py-3 px-4">Stop / Take Profit</th>
                <th className="py-3 px-4">Duration</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {activeTab === "open" && openPositions.length === 0 && (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-muted">
                    No open paper positions active at this time.
                  </td>
                </tr>
              )}

              {activeTab === "open" &&
                openPositions.map((pos) => {
                  const gainPct = ((pos.current_mark_price - pos.entry_price) / pos.entry_price) * 100.0;
                  return (
                    <tr key={pos.position_id} className="hover:bg-surface-card/60 transition-colors">
                      <td className="py-3 px-4">
                        <div
                          onClick={() => onSelectToken(pos.token_mint)}
                          className="font-bold text-slate-100 hover:text-primary cursor-pointer transition-colors"
                        >
                          {pos.token_symbol || truncateMint(pos.token_mint, 5)}
                        </div>
                        <div className="text-[10px] text-muted">{truncateMint(pos.token_mint, 6)}</div>
                      </td>

                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded bg-surface-card border border-surface-border text-slate-300 text-[11px]">
                          {pos.strategy_id}
                        </span>
                      </td>

                      <td className="py-3 px-4">
                        <div className="text-slate-100 font-semibold">{formatUsd(pos.current_mark_price)}</div>
                        <div className="text-[10px] text-muted">Entry: {formatUsd(pos.entry_price)}</div>
                      </td>

                      <td className="py-3 px-4">
                        <div className="text-slate-200">{formatUsd(pos.capital_committed)}</div>
                        <div className="text-[10px] text-muted">{pos.quantity.toFixed(1)} tokens</div>
                      </td>

                      <td className="py-3 px-4">
                        <div className={cn("font-bold text-sm", pos.unrealised_pnl_usd >= 0 ? "text-success" : "text-danger")}>
                          {formatUsd(pos.unrealised_pnl_usd)}
                        </div>
                        <div className={cn("text-[10px]", gainPct >= 0 ? "text-success" : "text-danger")}>
                          {formatPct(gainPct)}
                        </div>
                      </td>

                      <td className="py-3 px-4 text-[11px]">
                        <div className="text-success">MFE: +${pos.max_favourable_excursion_usd.toFixed(2)}</div>
                        <div className="text-danger">MAE: -${pos.max_adverse_excursion_usd.toFixed(2)}</div>
                      </td>

                      <td className="py-3 px-4 text-[11px]">
                        <div className="text-danger">SL: {formatUsd(pos.stop_loss_price)}</div>
                        <div className="text-success">TP: {formatUsd(pos.take_profit_price)}</div>
                      </td>

                      <td className="py-3 px-4 text-muted text-[11px]">
                        {formatDuration(pos.holding_duration_seconds)}
                      </td>

                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => onClosePosition(pos.position_id)}
                          className="px-2.5 py-1 rounded bg-danger/10 hover:bg-danger/20 text-danger border border-danger/30 text-[11px] font-semibold transition-colors"
                        >
                          Manual Exit
                        </button>
                      </td>
                    </tr>
                  );
                })}

              {/* CLOSED POSITIONS */}
              {activeTab === "closed" &&
                closedPositions.map((pos) => (
                  <tr key={pos.position_id} className="hover:bg-surface-card/60 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-bold text-slate-100">{pos.token_symbol || truncateMint(pos.token_mint, 5)}</div>
                      <div className="text-[10px] text-muted">ID: {pos.position_id.slice(0, 8)}</div>
                    </td>
                    <td className="py-3 px-4">{pos.strategy_id}</td>
                    <td className="py-3 px-4">{formatUsd(pos.entry_price)}</td>
                    <td className="py-3 px-4">{formatUsd(pos.capital_committed)}</td>
                    <td className="py-3 px-4">
                      <span className={cn("font-bold", pos.realised_pnl_usd >= 0 ? "text-success" : "text-danger")}>
                        {formatUsd(pos.realised_pnl_usd)}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-muted">Fees: {formatUsd(pos.total_fees_paid_usd)}</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded bg-surface-card border border-surface-border text-[10px] uppercase font-semibold text-slate-300">
                        {pos.exit_reason || "closed"}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-muted">{formatDuration(pos.holding_duration_seconds)}</td>
                    <td className="py-3 px-4 text-right text-muted text-[10px]">Settled</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
