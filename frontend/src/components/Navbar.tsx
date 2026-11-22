import React from "react";
import { cn } from "../lib/utils";

interface NavbarProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
  systemStatus: string;
  emergencyStop: boolean;
  portfolioEquity: number;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentTab,
  onSelectTab,
  systemStatus,
  emergencyStop,
  portfolioEquity,
}) => {
  const tabs = [
    { id: "overview", label: "Overview", icon: "dashboard" },
    { id: "discovery", label: "Discovery", icon: "radar" },
    { id: "agents", label: "Agents", icon: "smart_toy" },
    { id: "decisions", label: "Decisions", icon: "balance" },
    { id: "trading", label: "Paper Trading", icon: "candlestick_chart" },
    { id: "research", label: "Research & ML", icon: "insights" },
    { id: "controls", label: "Control Centre", icon: "tune" },
  ];

  return (
    <header className="sticky top-0 z-40 bg-surface/90 backdrop-blur-md border-b border-surface-border px-6 py-3 flex items-center justify-between">
      {/* Brand & Live Indicator */}
      <div className="flex items-center space-x-6">
        <div className="flex items-center space-x-3 cursor-pointer" onClick={() => onSelectTab("overview")}>
          <div className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/30 flex items-center justify-center text-primary shadow-[0_0_15px_rgba(0,240,255,0.2)]">
            <span className="material-symbols-rounded text-xl">satellite_alt</span>
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-lg tracking-wider text-slate-100 font-mono">MECO</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/15 text-primary border border-primary/30 font-mono font-semibold uppercase">
                Paper v1.0
              </span>
            </div>
            <div className="flex items-center space-x-1.5 text-xs text-muted">
              <span className={cn(
                "w-2 h-2 rounded-full animate-pulse",
                emergencyStop ? "bg-danger" : systemStatus === "operational" ? "bg-success" : "bg-warning"
              )} />
              <span className="capitalize">{emergencyStop ? "Emergency Halt" : systemStatus}</span>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="hidden md:flex items-center space-x-1 border-l border-surface-border pl-6">
          {tabs.map((tab) => {
            const isActive = currentTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onSelectTab(tab.id)}
                className={cn(
                  "flex items-center space-x-2 px-3 py-1.5 rounded-md text-xs font-medium transition-all",
                  isActive
                    ? "bg-primary/10 text-primary border border-primary/30 shadow-[0_0_10px_rgba(0,240,255,0.1)]"
                    : "text-muted hover:text-slate-100 hover:bg-surface-card"
                )}
              >
                <span className="material-symbols-rounded text-[18px]">{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Right Controls & Equity Pill */}
      <div className="flex items-center space-x-4">
        {/* Paper Equity Badge */}
        <div className="hidden sm:flex items-center space-x-2 bg-surface-card border border-surface-border rounded-lg px-3 py-1.5">
          <span className="material-symbols-rounded text-primary text-base">account_balance_wallet</span>
          <div className="text-right">
            <div className="text-[10px] text-muted uppercase font-mono tracking-wider">Paper Equity</div>
            <div className="text-xs font-mono font-semibold text-slate-100">
              ${portfolioEquity.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>
        </div>

        {/* Emergency Stop Status */}
        {emergencyStop && (
          <div className="flex items-center space-x-1.5 bg-danger/20 border border-danger text-danger text-xs px-3 py-1.5 rounded-lg animate-pulse font-mono font-semibold">
            <span className="material-symbols-rounded text-sm">emergency_home</span>
            <span>KILL SWITCH ENGAGED</span>
          </div>
        )}

        <button
          onClick={() => onSelectTab("controls")}
          className="p-2 rounded-lg bg-surface-card hover:bg-surface-border border border-surface-border text-muted hover:text-slate-100 transition-colors"
          title="Operator Controls"
        >
          <span className="material-symbols-rounded text-xl">settings</span>
        </button>
      </div>
    </header>
  );
};
