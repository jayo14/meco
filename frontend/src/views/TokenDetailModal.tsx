import React, { useState } from "react";
import { TokenDetail } from "../api/client";
import { formatUsd, formatPct, truncateMint, cn } from "../lib/utils";

interface TokenDetailModalProps {
  token: TokenDetail | null;
  isOpen: boolean;
  onClose: () => void;
  onTriggerInvestigation: (mint: string) => void;
}

export const TokenDetailModal: React.FC<TokenDetailModalProps> = ({
  token,
  isOpen,
  onClose,
  onTriggerInvestigation,
}) => {
  const [activeTab, setActiveTab] = useState<"overview" | "security" | "social" | "agents" | "decisions">("overview");

  if (!isOpen || !token) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-background/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="w-full max-w-4xl max-h-[90vh] bg-surface border border-surface-border rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        {/* Modal Header */}
        <div className="p-6 border-b border-surface-border flex items-center justify-between bg-surface-card/40">
          <div className="flex items-center space-x-4">
            <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/30 flex items-center justify-center text-primary font-bold text-lg font-mono">
              {token.symbol?.slice(0, 3) || "TOK"}
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-lg font-bold text-slate-100">{token.name || "Unknown Token"}</h2>
                {token.symbol && (
                  <span className="text-xs font-mono text-muted bg-surface-card px-2 py-0.5 rounded border border-surface-border">
                    ${token.symbol}
                  </span>
                )}
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-primary/20 text-primary border border-primary/30 uppercase font-semibold">
                  {token.discovery_source}
                </span>
              </div>
              <div className="text-xs font-mono text-muted flex items-center space-x-2 mt-1">
                <span>Mint: {token.token_mint}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={() => onTriggerInvestigation(token.token_mint)}
              className="px-3 py-1.5 rounded-lg bg-accent/20 hover:bg-accent/30 text-accent border border-accent/40 text-xs font-medium flex items-center space-x-1.5 transition-colors"
            >
              <span className="material-symbols-rounded text-sm">psychology</span>
              <span>Trigger AI Agent</span>
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-lg bg-surface-card hover:bg-surface-border text-muted hover:text-slate-100 transition-colors"
            >
              <span className="material-symbols-rounded text-xl">close</span>
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center space-x-1 px-6 border-b border-surface-border bg-surface-card/20 text-xs">
          {[
            { id: "overview", label: "Pool & Market", icon: "candlestick_chart" },
            { id: "security", label: "Security & Holders", icon: "security" },
            { id: "social", label: "Social & Narrative", icon: "forum" },
            { id: "agents", label: `Agent Evidence (${token.investigations.length})`, icon: "smart_toy" },
            { id: "decisions", label: `Decisions (${token.decisions.length})`, icon: "balance" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={cn(
                "flex items-center space-x-1.5 py-3 px-3 font-medium border-b-2 transition-all",
                activeTab === tab.id
                  ? "border-primary text-primary font-semibold"
                  : "border-transparent text-muted hover:text-slate-100"
              )}
            >
              <span className="material-symbols-rounded text-base">{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Tab Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 text-xs font-mono">
          {/* TAB 1: OVERVIEW */}
          {activeTab === "overview" && (
            <div className="space-y-6">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="bg-surface-card p-3 rounded-xl border border-surface-border">
                  <div className="text-muted text-[10px] uppercase">Spot Price</div>
                  <div className="text-base font-bold text-slate-100">{formatUsd(token.current_price_usd)}</div>
                  <div className="text-[11px] text-muted">5m Change: {formatPct(token.price_change_5m)}</div>
                </div>
                <div className="bg-surface-card p-3 rounded-xl border border-surface-border">
                  <div className="text-muted text-[10px] uppercase">Pool Liquidity</div>
                  <div className="text-base font-bold text-slate-100">{formatUsd(token.pool_liquidity_usd)}</div>
                  <div className="text-[11px] text-muted">Initial: {formatUsd(token.initial_liquidity_usd)}</div>
                </div>
                <div className="bg-surface-card p-3 rounded-xl border border-surface-border">
                  <div className="text-muted text-[10px] uppercase">5m Volume</div>
                  <div className="text-base font-bold text-slate-100">{formatUsd(token.volume_5m_usd)}</div>
                  <div className="text-[11px] text-muted">1h Vol: {formatUsd(token.volume_1h_usd)}</div>
                </div>
                <div className="bg-surface-card p-3 rounded-xl border border-surface-border">
                  <div className="text-muted text-[10px] uppercase">Transactions (5m)</div>
                  <div className="text-base font-bold text-slate-100">
                    {(token.buys_5m ?? 0) + (token.sells_5m ?? 0)} txns
                  </div>
                  <div className="text-[11px] text-success">
                    {token.buys_5m ?? 0} buys / {token.sells_5m ?? 0} sells
                  </div>
                </div>
              </div>

              {/* Pool & Token Metadata */}
              <div className="bg-surface-card p-4 rounded-xl border border-surface-border space-y-2">
                <h4 className="text-xs font-semibold text-slate-100 font-sans uppercase tracking-wider text-muted mb-3">
                  Canonical Token Specification
                </h4>
                <div className="grid grid-cols-2 gap-4 text-xs">
                  <div>
                    <span className="text-muted">Primary DEX:</span>{" "}
                    <span className="text-slate-100 uppercase">{token.dex_id || "Raydium"}</span>
                  </div>
                  <div>
                    <span className="text-muted">Lifecycle State:</span>{" "}
                    <span className="text-slate-100 uppercase font-semibold">{token.lifecycle_state}</span>
                  </div>
                  <div>
                    <span className="text-muted">Decimals:</span>{" "}
                    <span className="text-slate-100">{token.decimals ?? 9}</span>
                  </div>
                  <div>
                    <span className="text-muted">Total Supply:</span>{" "}
                    <span className="text-slate-100">{(token.total_supply ?? 1000000000).toLocaleString()}</span>
                  </div>
                  <div className="col-span-2">
                    <span className="text-muted">Discovered At:</span>{" "}
                    <span className="text-slate-100">{token.discovered_at}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: SECURITY */}
          {activeTab === "security" && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-surface-card p-4 rounded-xl border border-surface-border space-y-3">
                  <h4 className="text-xs font-semibold text-slate-100 font-sans uppercase tracking-wider text-muted">
                    Authority Safety Matrix
                  </h4>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-muted">Mint Authority:</span>
                      {token.mint_authority_revoked ? (
                        <span className="text-success font-semibold">REVOKED (Safe)</span>
                      ) : (
                        <span className="text-danger font-semibold">ACTIVE (Danger)</span>
                      )}
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted">Freeze Authority:</span>
                      {token.freeze_authority_revoked ? (
                        <span className="text-success font-semibold">REVOKED (Safe)</span>
                      ) : (
                        <span className="text-danger font-semibold">ACTIVE (Danger)</span>
                      )}
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted">Honeypot Signature:</span>
                      <span className={token.is_honeypot ? "text-danger font-bold" : "text-success"}>
                        {token.is_honeypot ? "FLAGGED HONEYPOT" : "Clean"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted">Transfer Fee:</span>
                      <span className="text-slate-100">{token.transfer_fee_bps ?? 0} bps</span>
                    </div>
                  </div>
                </div>

                <div className="bg-surface-card p-4 rounded-xl border border-surface-border space-y-3">
                  <h4 className="text-xs font-semibold text-slate-100 font-sans uppercase tracking-wider text-muted">
                    Holders & Deployer Risk
                  </h4>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-muted">Total Unique Holders:</span>
                      <span className="text-slate-100 font-bold">{token.holder_count ?? "--"}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted">Top 10 Holder Concentration:</span>
                      <span className={cn(
                        "font-bold",
                        (token.top10_holder_share_pct ?? 0) > 35 ? "text-danger" : "text-slate-100"
                      )}>
                        {token.top10_holder_share_pct ? `${token.top10_holder_share_pct.toFixed(1)}%` : "--"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted">Deployer Prior Tokens:</span>
                      <span className="text-slate-100">{token.deployer_prior_token_count ?? 0} tokens</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted">Deployer Risk Score:</span>
                      <span className="text-slate-100">{token.deployer_risk_score ?? "0.0"}/100</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: SOCIAL */}
          {activeTab === "social" && (
            <div className="bg-surface-card p-4 rounded-xl border border-surface-border space-y-4">
              <h4 className="text-xs font-semibold text-slate-100 font-sans uppercase tracking-wider text-muted">
                Social Intelligence & Narrative Momentum
              </h4>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div>
                  <div className="text-muted text-[10px]">Post Volume (1h)</div>
                  <div className="text-base font-bold text-slate-100">{token.social_post_count_1h ?? 0} posts</div>
                </div>
                <div>
                  <div className="text-muted text-[10px]">Estimated Reach</div>
                  <div className="text-base font-bold text-slate-100">{(token.social_reach_estimate ?? 0).toLocaleString()}</div>
                </div>
                <div>
                  <div className="text-muted text-[10px]">Sentiment Score</div>
                  <div className="text-base font-bold text-primary">{token.social_sentiment_score ?? 0.0}</div>
                </div>
                <div>
                  <div className="text-muted text-[10px]">Narrative Tier</div>
                  <div className="text-base font-bold text-accent uppercase">{token.narrative_tier || "None"}</div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: AGENT EVIDENCE */}
          {activeTab === "agents" && (
            <div className="space-y-3">
              {token.investigations.length === 0 ? (
                <div className="p-8 text-center text-muted">
                  No automated specialist investigations recorded for this token yet.
                </div>
              ) : (
                token.investigations.map((inv: any, i: number) => (
                  <div key={i} className="bg-surface-card p-4 rounded-xl border border-surface-border space-y-3">
                    <div className="flex items-center justify-between border-b border-surface-border pb-2">
                      <div className="flex items-center space-x-2">
                        <span className="material-symbols-rounded text-primary text-base">smart_toy</span>
                        <span className="font-semibold text-slate-100">{inv.agent || "Specialist Agent"}</span>
                        <span className="text-[10px] text-muted">({inv.investigation_id})</span>
                      </div>
                      <span className="text-[10px] text-success uppercase font-semibold">{inv.status}</span>
                    </div>
                    <div className="space-y-2">
                      {(inv.findings || []).map((f: any, fIdx: number) => (
                        <div key={fIdx} className="bg-surface p-2.5 rounded-lg border border-surface-border text-xs">
                          <div className="text-primary font-semibold uppercase text-[10px]">{f.type || f.status}</div>
                          <div className="text-slate-300 mt-0.5">{f.details}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* TAB 5: DECISIONS */}
          {activeTab === "decisions" && (
            <div className="space-y-3">
              {token.decisions.length === 0 ? (
                <div className="p-8 text-center text-muted">
                  No formal decisions generated by the Decision Engine yet.
                </div>
              ) : (
                token.decisions.map((dec: any, i: number) => (
                  <div key={i} className="bg-surface-card p-4 rounded-xl border border-surface-border space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-100 uppercase">{dec.outcome.replace(/_/g, " ")}</span>
                      <span className="text-muted text-[10px]">{dec.timestamp}</span>
                    </div>
                    <div className="flex items-center space-x-4 text-[11px] text-muted">
                      <span>Opportunity Score: <strong className="text-primary">{dec.opportunity_score}</strong></span>
                      <span>Confidence: <strong className="text-slate-200">{(dec.confidence * 100).toFixed(0)}%</strong></span>
                    </div>
                    <p className="text-slate-300 text-xs bg-surface p-2.5 rounded-lg border border-surface-border leading-relaxed">
                      {dec.reasoning}
                    </p>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
