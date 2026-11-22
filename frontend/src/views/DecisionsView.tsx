import React, { useState } from "react";
import { DecisionRecord } from "../api/client";
import { truncateMint, cn } from "../lib/utils";

interface DecisionsViewProps {
  decisions: DecisionRecord[];
  isLoading: boolean;
  onRefresh: () => void;
  onSelectToken: (mint: string) => void;
}

export const DecisionsView: React.FC<DecisionsViewProps> = ({
  decisions,
  isLoading,
  onRefresh,
  onSelectToken,
}) => {
  const [outcomeFilter, setOutcomeFilter] = useState("all");

  const filteredDecisions = decisions.filter(
    (d) => outcomeFilter === "all" || d.outcome === outcomeFilter
  );

  return (
    <div className="space-y-4">
      {/* Header & Filter */}
      <div className="flex items-center justify-between bg-surface border border-surface-border p-4 rounded-xl">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-warning/10 border border-warning/30 flex items-center justify-center text-warning">
            <span className="material-symbols-rounded text-lg">balance</span>
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-100">Deterministic Decision Engine Matrix</h3>
            <p className="text-xs text-muted">Audited, reproducible ranking with strict hard risk separation</p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <select
            value={outcomeFilter}
            onChange={(e) => setOutcomeFilter(e.target.value)}
            className="bg-surface-card border border-surface-border rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-primary/50 font-mono"
          >
            <option value="all">All Outcomes</option>
            <option value="paper_trade_candidate">Paper Trade Candidates</option>
            <option value="watchlist">Watchlist</option>
            <option value="monitor">Monitor</option>
            <option value="rejected_hard_risk">Hard Risk Rejections</option>
          </select>

          <button
            onClick={onRefresh}
            className="p-1.5 rounded-lg bg-surface-card hover:bg-surface-border border border-surface-border text-muted hover:text-slate-100 transition-colors"
          >
            <span className={cn("material-symbols-rounded text-lg", isLoading && "animate-spin")}>
              refresh
            </span>
          </button>
        </div>
      </div>

      {/* Decision Cards Grid */}
      <div className="space-y-3">
        {filteredDecisions.length === 0 ? (
          <div className="bg-surface border border-surface-border rounded-xl p-12 text-center text-muted font-mono text-xs">
            No decision records matching the outcome filter.
          </div>
        ) : (
          filteredDecisions.map((dec) => (
            <div
              key={dec.decision_id}
              className="bg-surface border border-surface-border hover:border-primary/30 rounded-xl p-5 transition-all space-y-4 font-mono text-xs shadow-lg"
            >
              {/* Card Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-surface-border pb-3">
                <div className="flex items-center space-x-3">
                  {dec.opportunity_rank ? (
                    <span className="w-7 h-7 rounded-lg bg-primary/10 border border-primary/30 flex items-center justify-center font-bold text-primary text-xs">
                      #{dec.opportunity_rank}
                    </span>
                  ) : (
                    <span className="w-7 h-7 rounded-lg bg-danger/10 border border-danger/30 flex items-center justify-center font-bold text-danger text-xs">
                      ✕
                    </span>
                  )}
                  <div>
                    <div className="flex items-center space-x-2">
                      <span
                        onClick={() => onSelectToken(dec.token_mint)}
                        className="font-sans font-bold text-slate-100 text-sm hover:text-primary cursor-pointer transition-colors"
                      >
                        {truncateMint(dec.token_mint, 8)}
                      </span>
                      {dec.token_symbol && (
                        <span className="text-muted font-normal">(${dec.token_symbol})</span>
                      )}
                    </div>
                    <div className="text-[11px] text-muted">ID: {dec.decision_id}</div>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <span className={cn(
                    "px-2.5 py-1 rounded font-semibold uppercase text-[11px]",
                    dec.outcome === "paper_trade_candidate"
                      ? "bg-success/20 text-success border border-success/30"
                      : dec.outcome === "watchlist"
                      ? "bg-primary/20 text-primary border border-primary/30"
                      : dec.outcome === "rejected_hard_risk"
                      ? "bg-danger/20 text-danger border border-danger/30"
                      : "bg-surface-card text-muted border border-surface-border"
                  )}>
                    {dec.outcome.replace(/_/g, " ")}
                  </span>
                  <span className="text-[10px] bg-surface-card px-2 py-1 rounded border border-surface-border text-muted">
                    Conf: {(dec.confidence_score * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              {/* Reasoning Summary */}
              <div className="bg-surface-card p-3 rounded-lg border border-surface-border leading-relaxed text-slate-300">
                <span className="text-muted font-bold mr-2 uppercase text-[10px]">Rationale:</span>
                {dec.reasoning_summary}
              </div>

              {/* Supporting & Contradictory Evidence Pill Strips */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px]">
                {/* Supporting */}
                <div className="space-y-1.5">
                  <span className="text-success font-semibold text-[10px] uppercase flex items-center space-x-1">
                    <span className="material-symbols-rounded text-xs">check_circle</span>
                    <span>Supporting Evidence ({dec.supporting_evidence.length})</span>
                  </span>
                  <div className="space-y-1">
                    {dec.supporting_evidence.map((ev, i) => (
                      <div key={i} className="bg-success/5 border border-success/20 text-slate-300 p-2 rounded">
                        • {ev}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Risk / Contradictory */}
                <div className="space-y-1.5">
                  <span className="text-danger font-semibold text-[10px] uppercase flex items-center space-x-1">
                    <span className="material-symbols-rounded text-xs">error</span>
                    <span>Risk Factors & Contradictions ({dec.risk_factors.length + dec.contradictory_evidence.length})</span>
                  </span>
                  <div className="space-y-1">
                    {[...dec.risk_factors, ...dec.contradictory_evidence].map((rf, i) => (
                      <div key={i} className="bg-danger/5 border border-danger/20 text-slate-300 p-2 rounded">
                        • {rf}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
