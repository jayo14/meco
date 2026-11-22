import React, { useState } from "react";
import { SystemHealth } from "../api/client";
import { ConfirmationModal } from "../components/ConfirmationModal";
import { cn } from "../lib/utils";

interface ControlCentreViewProps {
  health?: SystemHealth;
  isLoading: boolean;
  onRefresh: () => void;
  onExecuteControl: (cmd: { action: string; confirmation?: boolean; target_id?: string; parameters?: any; operator_notes?: string }) => Promise<any>;
}

export const ControlCentreView: React.FC<ControlCentreViewProps> = ({
  health,
  isLoading,
  onRefresh,
  onExecuteControl,
}) => {
  const [modalConfig, setModalConfig] = useState<{
    isOpen: boolean;
    title: string;
    description: string;
    action: string;
    targetId?: string;
    variant: "danger" | "warning" | "primary";
  }>({
    isOpen: false,
    title: "",
    description: "",
    action: "",
    variant: "danger",
  });

  const [discoveryPaused, setDiscoveryPaused] = useState(false);
  const [enrichmentPaused, setEnrichmentPaused] = useState(false);
  const [strategies, setStrategies] = useState<Record<string, boolean>>({
    momentum_breakout: true,
    volume_spike_scalp: true,
    ml_momentum_v1: true,
  });

  const emergencyActive = health?.emergency_stop_engaged || false;

  const handleToggleEmergencyStop = () => {
    if (!emergencyActive) {
      setModalConfig({
        isOpen: true,
        title: "Engage Emergency Stop Kill Switch",
        description:
          "CRITICAL SAFETY ACTION: This will immediately freeze all paper trading proposal evaluations and block any new simulated entries across all strategies. AI agents cannot override this stop.",
        action: "emergency_stop",
        variant: "danger",
      });
    } else {
      setModalConfig({
        isOpen: true,
        title: "Reset Emergency Stop",
        description:
          "Resume paper trading execution gateway. Active strategies will once again be permitted to evaluate opportunities and simulate entries.",
        action: "reset_emergency_stop",
        variant: "warning",
      });
    }
  };

  const handleConfirmModal = async () => {
    try {
      await onExecuteControl({
        action: modalConfig.action,
        confirmation: true,
        target_id: modalConfig.targetId,
        operator_notes: "Operator confirmed via Control Centre UI",
      });
      setModalConfig((prev) => ({ ...prev, isOpen: false }));
      onRefresh();
    } catch (err: any) {
      alert(`Command failed: ${err.message}`);
    }
  };

  const handleToggleDiscovery = async () => {
    const action = discoveryPaused ? "resume_discovery" : "pause_discovery";
    await onExecuteControl({ action, confirmation: false });
    setDiscoveryPaused(!discoveryPaused);
    onRefresh();
  };

  const handleToggleEnrichment = async () => {
    const action = enrichmentPaused ? "resume_enrichment" : "pause_enrichment";
    await onExecuteControl({ action, confirmation: false });
    setEnrichmentPaused(!enrichmentPaused);
    onRefresh();
  };

  const handleToggleStrategy = async (stratId: string) => {
    const nextState = !strategies[stratId];
    await onExecuteControl({
      action: "toggle_strategy",
      target_id: stratId,
      parameters: { enabled: nextState },
    });
    setStrategies((prev) => ({ ...prev, [stratId]: nextState }));
  };

  return (
    <div className="space-y-6">
      {/* 1. Emergency Kill Switch Strip */}
      <div className={cn(
        "p-6 rounded-2xl border flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition-all shadow-2xl",
        emergencyActive
          ? "bg-danger/15 border-danger/50 shadow-[0_0_30px_rgba(239,68,68,0.2)]"
          : "bg-surface border-surface-border"
      )}>
        <div className="flex items-center space-x-4">
          <div className={cn(
            "w-12 h-12 rounded-xl border flex items-center justify-center text-2xl",
            emergencyActive ? "bg-danger/20 border-danger text-danger animate-pulse" : "bg-surface-card border-surface-border text-muted"
          )}>
            <span className="material-symbols-rounded">
              {emergencyActive ? "emergency_home" : "lock_open"}
            </span>
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-base font-bold text-slate-100 font-sans">
                {emergencyActive ? "EMERGENCY STOP ENGAGED" : "Execution Safety Gateway"}
              </h3>
              <span className={cn(
                "text-[10px] font-mono px-2 py-0.5 rounded uppercase font-bold",
                emergencyActive ? "bg-danger text-white" : "bg-success/20 text-success border border-success/30"
              )}>
                {emergencyActive ? "Halted" : "Armed & Ready"}
              </span>
            </div>
            <p className="text-xs text-muted font-mono mt-0.5">
              Hard constraint: AI agents cannot override manual emergency stop. All new entries blocked when engaged.
            </p>
          </div>
        </div>

        <button
          onClick={handleToggleEmergencyStop}
          className={cn(
            "px-6 py-2.5 rounded-xl font-mono text-xs font-bold uppercase tracking-wider transition-all shadow-lg",
            emergencyActive
              ? "bg-warning hover:bg-warning/90 text-background shadow-[0_0_20px_rgba(245,158,11,0.3)]"
              : "bg-danger hover:bg-danger/90 text-white shadow-[0_0_20px_rgba(239,68,68,0.3)]"
          )}
        >
          {emergencyActive ? "Reset Emergency Stop" : "ENGAGE KILL SWITCH"}
        </button>
      </div>

      {/* 2. Operational Control Toggles */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 font-mono text-xs">
        {/* Subsystem Pipeline Controls */}
        <div className="bg-surface border border-surface-border rounded-xl p-5 space-y-4">
          <h4 className="text-xs font-bold text-slate-100 uppercase tracking-wider font-sans border-b border-surface-border pb-3">
            Subsystem Pipeline Toggles
          </h4>

          <div className="flex items-center justify-between p-3 bg-surface-card rounded-lg border border-surface-border">
            <div>
              <div className="font-semibold text-slate-200">Discovery Engine Ingestion</div>
              <div className="text-[10px] text-muted">Pump.fun WS, DexScreener Poller & Telegram</div>
            </div>
            <button
              onClick={handleToggleDiscovery}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-bold uppercase transition-colors",
                discoveryPaused
                  ? "bg-warning/20 text-warning border border-warning/40"
                  : "bg-success/20 text-success border border-success/40"
              )}
            >
              {discoveryPaused ? "PAUSED" : "ACTIVE"}
            </button>
          </div>

          <div className="flex items-center justify-between p-3 bg-surface-card rounded-lg border border-surface-border">
            <div>
              <div className="font-semibold text-slate-200">Specialist Agent Enrichment</div>
              <div className="text-[10px] text-muted">Security, Market, Risk & Social LLM Agents</div>
            </div>
            <button
              onClick={handleToggleEnrichment}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-bold uppercase transition-colors",
                enrichmentPaused
                  ? "bg-warning/20 text-warning border border-warning/40"
                  : "bg-success/20 text-success border border-success/40"
              )}
            >
              {enrichmentPaused ? "PAUSED" : "ACTIVE"}
            </button>
          </div>
        </div>

        {/* Strategy Enablement Matrix */}
        <div className="bg-surface border border-surface-border rounded-xl p-5 space-y-4">
          <h4 className="text-xs font-bold text-slate-100 uppercase tracking-wider font-sans border-b border-surface-border pb-3">
            Active Strategy Controls
          </h4>

          {Object.entries(strategies).map(([stratId, enabled]) => (
            <div key={stratId} className="flex items-center justify-between p-3 bg-surface-card rounded-lg border border-surface-border">
              <div>
                <div className="font-semibold text-slate-200">{stratId}</div>
                <div className="text-[10px] text-muted">Autonomous signal evaluation</div>
              </div>
              <button
                onClick={() => handleToggleStrategy(stratId)}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-xs font-bold uppercase transition-colors",
                  enabled
                    ? "bg-primary/20 text-primary border border-primary/40"
                    : "bg-surface border border-surface-border text-muted"
                )}
              >
                {enabled ? "ENABLED" : "DISABLED"}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* 3. System Health & Infrastructure Diagnostics */}
      <div className="bg-surface border border-surface-border rounded-xl p-5 font-mono text-xs space-y-4">
        <div className="flex items-center justify-between border-b border-surface-border pb-3">
          <div className="flex items-center space-x-2">
            <span className="material-symbols-rounded text-success">dns</span>
            <h4 className="text-xs font-bold text-slate-100 uppercase tracking-wider font-sans">
              System Health & Infrastructure Telemetry
            </h4>
          </div>
          <span className="text-muted">RPC Latency: {health?.rpc_latency_ms?.toFixed(1) || "28.5"}ms</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {(health?.discovery_sources || []).map((src: any, i: number) => (
            <div key={i} className="bg-surface-card p-3 rounded-lg border border-surface-border space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-200">{src.source_name}</span>
                <span className={cn(
                  "w-2 h-2 rounded-full",
                  src.status === "connected" ? "bg-success animate-pulse" : "bg-warning"
                )} />
              </div>
              <div className="text-[10px] text-muted flex justify-between">
                <span>Protocol: {src.type}</span>
                <span>{src.latency_ms}ms</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Confirmation Modal Guard */}
      <ConfirmationModal
        isOpen={modalConfig.isOpen}
        title={modalConfig.title}
        description={modalConfig.description}
        variant={modalConfig.variant}
        confirmText="Confirm Operation"
        onConfirm={handleConfirmModal}
        onCancel={() => setModalConfig((prev) => ({ ...prev, isOpen: false }))}
      />
    </div>
  );
};
