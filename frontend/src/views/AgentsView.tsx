import React, { useState } from "react";
import { AgentInvestigation } from "../api/client";
import { truncateMint, formatDuration, cn } from "../lib/utils";

interface AgentsViewProps {
  investigations: AgentInvestigation[];
  isLoading: boolean;
  onRefresh: () => void;
  onSelectToken: (mint: string) => void;
}

export const AgentsView: React.FC<AgentsViewProps> = ({
  investigations,
  isLoading,
  onRefresh,
  onSelectToken,
}) => {
  const [selectedInv, setSelectedInv] = useState<AgentInvestigation | null>(
    investigations.length > 0 ? investigations[0] : null
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Left 1 Col: List of Investigations */}
      <div className="bg-surface border border-surface-border rounded-xl p-4 flex flex-col space-y-4">
        <div className="flex items-center justify-between border-b border-surface-border pb-3">
          <div className="flex items-center space-x-2">
            <span className="material-symbols-rounded text-accent">psychology</span>
            <h3 className="text-sm font-semibold text-slate-100">Specialist Investigations</h3>
          </div>
          <button
            onClick={onRefresh}
            className="p-1.5 rounded-lg bg-surface-card hover:bg-surface-border text-muted hover:text-slate-100 transition-colors"
          >
            <span className={cn("material-symbols-rounded text-base", isLoading && "animate-spin")}>
              refresh
            </span>
          </button>
        </div>

        <div className="space-y-2.5 overflow-y-auto max-h-[70vh]">
          {investigations.map((inv) => {
            const isSelected = selectedInv?.investigation_id === inv.investigation_id;
            return (
              <div
                key={inv.investigation_id}
                onClick={() => setSelectedInv(inv)}
                className={cn(
                  "p-3 rounded-lg border transition-all cursor-pointer font-mono text-xs",
                  isSelected
                    ? "bg-accent/10 border-accent/40 shadow-[0_0_15px_rgba(139,92,246,0.15)]"
                    : "bg-surface-card border-surface-border hover:border-slate-700"
                )}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-sans font-bold text-slate-100 truncate">
                    {inv.token_name || truncateMint(inv.token_mint, 5)}
                  </span>
                  <span className={cn(
                    "text-[10px] px-2 py-0.5 rounded font-semibold uppercase",
                    inv.status === "completed"
                      ? "bg-success/20 text-success border border-success/30"
                      : inv.status === "failed"
                      ? "bg-danger/20 text-danger border border-danger/30"
                      : "bg-primary/20 text-primary border border-primary/30 animate-pulse"
                  )}>
                    {inv.status}
                  </span>
                </div>

                <div className="flex items-center justify-between text-[11px] text-muted">
                  <span>{inv.agent_findings_count} findings</span>
                  <span>{formatDuration(inv.duration_seconds)}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Right 2 Cols: Selected Investigation Finding Inspector */}
      <div className="lg:col-span-2 bg-surface border border-surface-border rounded-xl p-6 flex flex-col justify-between">
        {selectedInv ? (
          <div className="space-y-6">
            {/* Header info */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-surface-border pb-4">
              <div>
                <div className="flex items-center space-x-2">
                  <h3 className="text-base font-bold text-slate-100 font-sans">
                    {selectedInv.token_name || "Token Investigation"}
                  </h3>
                  <span className="text-xs font-mono text-muted">({selectedInv.investigation_id})</span>
                </div>
                <div
                  onClick={() => onSelectToken(selectedInv.token_mint)}
                  className="text-xs font-mono text-primary hover:underline cursor-pointer mt-1"
                >
                  Mint: {selectedInv.token_mint}
                </div>
              </div>

              <div className="flex items-center space-x-2">
                {selectedInv.models_used.map((m, idx) => (
                  <span key={idx} className="text-[10px] font-mono px-2 py-0.5 rounded bg-surface-card border border-surface-border text-muted">
                    {m}
                  </span>
                ))}
              </div>
            </div>

            {/* Findings Stack */}
            <div className="space-y-3 font-mono text-xs">
              <h4 className="text-xs font-semibold text-muted uppercase font-sans tracking-wider">
                Audited Agent Evidence Items ({selectedInv.findings.length})
              </h4>

              {selectedInv.findings.map((f: any, idx: number) => (
                <div key={idx} className="bg-surface-card p-4 rounded-xl border border-surface-border space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className="w-2 h-2 rounded-full bg-accent" />
                      <span className="font-bold text-slate-200 uppercase">{f.agent || "Specialist Agent"}</span>
                      <span className="text-[11px] text-muted font-normal">[{f.type || "evidence"}]</span>
                    </div>
                    <span className="text-[10px] text-muted">{f.status || "verified"}</span>
                  </div>
                  <p className="text-slate-300 leading-relaxed bg-surface p-3 rounded-lg border border-surface-border/50">
                    {f.details}
                  </p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-64 text-muted font-mono text-xs">
            <span className="material-symbols-rounded text-4xl mb-2 text-surface-border">smart_toy</span>
            Select an investigation from the list to inspect specialist agent findings.
          </div>
        )}
      </div>
    </div>
  );
};
