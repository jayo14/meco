import React, { useState } from "react";
import { TokenSummary } from "../api/client";
import { formatUsd, formatPct, truncateMint, cn } from "../lib/utils";

interface DiscoveryViewProps {
  tokens: TokenSummary[];
  isLoading: boolean;
  onSelectToken: (mint: string) => void;
  onRefresh: () => void;
}

export const DiscoveryView: React.FC<DiscoveryViewProps> = ({
  tokens,
  isLoading,
  onSelectToken,
  onRefresh,
}) => {
  const [search, setSearch] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [riskFilter, setRiskFilter] = useState("all");

  const filteredTokens = tokens.filter((t) => {
    const matchesSearch =
      !search ||
      t.token_mint.toLowerCase().includes(search.toLowerCase()) ||
      (t.name && t.name.toLowerCase().includes(search.toLowerCase())) ||
      (t.symbol && t.symbol.toLowerCase().includes(search.toLowerCase()));

    const matchesSource = sourceFilter === "all" || t.discovery_source === sourceFilter;
    const matchesRisk = riskFilter === "all" || t.risk_level === riskFilter;

    return matchesSearch && matchesSource && matchesRisk;
  });

  return (
    <div className="space-y-4">
      {/* Search & Filter Toolbar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-surface border border-surface-border p-4 rounded-xl">
        <div className="flex-1 relative">
          <span className="material-symbols-rounded absolute left-3 top-1/2 -translate-y-1/2 text-muted text-lg">
            search
          </span>
          <input
            type="text"
            placeholder="Search by mint, token name, or symbol..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-surface-card border border-surface-border rounded-lg pl-9 pr-4 py-2 text-xs text-slate-100 placeholder-muted focus:outline-none focus:border-primary/50 font-mono"
          />
        </div>

        <div className="flex items-center space-x-2">
          {/* Source Filter */}
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="bg-surface-card border border-surface-border rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-primary/50 font-mono"
          >
            <option value="all">All Sources</option>
            <option value="pumpfun">Pump.fun</option>
            <option value="dexscreener">DexScreener</option>
            <option value="telegram">Telegram</option>
          </select>

          {/* Risk Filter */}
          <select
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value)}
            className="bg-surface-card border border-surface-border rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-primary/50 font-mono"
          >
            <option value="all">All Risk Levels</option>
            <option value="low">Low Risk</option>
            <option value="medium">Medium Risk</option>
            <option value="high">High Risk</option>
            <option value="critical">Critical / Honeypot</option>
          </select>

          <button
            onClick={onRefresh}
            className="p-2 rounded-lg bg-surface-card hover:bg-surface-border border border-surface-border text-muted hover:text-slate-100 transition-colors"
            title="Refresh Discovery Stream"
          >
            <span className={cn("material-symbols-rounded text-lg", isLoading && "animate-spin")}>
              refresh
            </span>
          </button>
        </div>
      </div>

      {/* Discovery Feed Table */}
      <div className="bg-surface border border-surface-border rounded-xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-surface-card border-b border-surface-border text-muted font-mono uppercase text-[10px] tracking-wider">
              <tr>
                <th className="py-3 px-4">Token</th>
                <th className="py-3 px-4">Source</th>
                <th className="py-3 px-4">Price / Liquidity</th>
                <th className="py-3 px-4">5m Volume</th>
                <th className="py-3 px-4">Top 10 %</th>
                <th className="py-3 px-4">Authorities</th>
                <th className="py-3 px-4">Opportunity Score</th>
                <th className="py-3 px-4">Decision</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border font-mono">
              {filteredTokens.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-muted">
                    No tokens found matching the filter criteria.
                  </td>
                </tr>
              ) : (
                filteredTokens.map((t) => (
                  <tr
                    key={t.token_mint}
                    onClick={() => onSelectToken(t.token_mint)}
                    className="hover:bg-surface-card/60 cursor-pointer transition-colors group"
                  >
                    {/* Token & Mint */}
                    <td className="py-3 px-4">
                      <div className="font-sans font-semibold text-slate-100 group-hover:text-primary transition-colors flex items-center space-x-1.5">
                        <span>{t.name || "Unknown Token"}</span>
                        {t.symbol && (
                          <span className="text-[10px] text-muted font-mono font-normal">
                            (${t.symbol})
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-muted font-mono flex items-center space-x-1">
                        <span>{truncateMint(t.token_mint, 6)}</span>
                      </div>
                    </td>

                    {/* Source */}
                    <td className="py-3 px-4">
                      <span className="text-[11px] px-2 py-0.5 rounded bg-surface-card border border-surface-border text-slate-300 capitalize">
                        {t.discovery_source}
                      </span>
                    </td>

                    {/* Price & Liquidity */}
                    <td className="py-3 px-4">
                      <div className="text-slate-100 font-medium">
                        {formatUsd(t.current_price_usd)}
                      </div>
                      <div className="text-[11px] text-muted">
                        Liq: {formatUsd(t.pool_liquidity_usd)}
                      </div>
                    </td>

                    {/* 5m Volume */}
                    <td className="py-3 px-4">
                      <div className="text-slate-200">
                        {formatUsd(t.volume_5m_usd)}
                      </div>
                    </td>

                    {/* Top 10 Holder Share */}
                    <td className="py-3 px-4">
                      {t.top10_holder_share_pct !== undefined && t.top10_holder_share_pct !== null ? (
                        <span className={cn(
                          "text-[11px] font-semibold",
                          t.top10_holder_share_pct > 35 ? "text-danger" : "text-slate-300"
                        )}>
                          {t.top10_holder_share_pct.toFixed(1)}%
                        </span>
                      ) : (
                        <span className="text-muted">--</span>
                      )}
                    </td>

                    {/* Authorities Badges */}
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-1">
                        {t.mint_authority_revoked === true ? (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-success/10 text-success border border-success/30" title="Mint Authority Revoked">
                            MINT REVOKED
                          </span>
                        ) : t.mint_authority_revoked === false ? (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-danger/10 text-danger border border-danger/30" title="Mint Authority Active">
                            MINT ACTIVE
                          </span>
                        ) : (
                          <span className="text-muted text-[10px]">--</span>
                        )}

                        {t.freeze_authority_revoked === true ? (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-success/10 text-success border border-success/30" title="Freeze Authority Revoked">
                            FREEZE REVOKED
                          </span>
                        ) : t.freeze_authority_revoked === false ? (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-danger/10 text-danger border border-danger/30" title="Freeze Authority Active">
                            FREEZE ACTIVE
                          </span>
                        ) : null}
                      </div>
                    </td>

                    {/* Opportunity Score */}
                    <td className="py-3 px-4">
                      {t.opportunity_score !== undefined && t.opportunity_score !== null ? (
                        <div className="flex items-center space-x-2">
                          <span className="font-bold text-slate-100">{t.opportunity_score.toFixed(1)}</span>
                          <div className="w-12 h-1.5 bg-surface-card rounded-full overflow-hidden">
                            <div
                              className="h-full bg-primary"
                              style={{ width: `${Math.min(100, Math.max(0, t.opportunity_score))}%` }}
                            />
                          </div>
                        </div>
                      ) : (
                        <span className="text-muted text-[11px]">Pending</span>
                      )}
                    </td>

                    {/* Decision Outcome */}
                    <td className="py-3 px-4">
                      {t.latest_decision_outcome ? (
                        <span className={cn(
                          "text-[10px] px-2 py-0.5 rounded font-semibold uppercase",
                          t.latest_decision_outcome === "paper_trade_candidate"
                            ? "bg-success/20 text-success border border-success/30"
                            : t.latest_decision_outcome === "watchlist"
                            ? "bg-primary/20 text-primary border border-primary/30"
                            : t.latest_decision_outcome === "rejected_hard_risk"
                            ? "bg-danger/20 text-danger border border-danger/30"
                            : "bg-surface-card text-muted border border-surface-border"
                        )}>
                          {t.latest_decision_outcome.replace(/_/g, " ")}
                        </span>
                      ) : (
                        <span className="text-muted text-[10px]">Evaluating</span>
                      )}
                    </td>

                    {/* Action */}
                    <td className="py-3 px-4 text-right">
                      <span className="material-symbols-rounded text-muted group-hover:text-primary transition-colors text-base">
                        arrow_forward
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
