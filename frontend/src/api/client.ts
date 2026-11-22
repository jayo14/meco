/**
 * Typed API Client for Meco Dashboard.
 */

export interface SystemOverview {
  system_status: string;
  total_tokens_discovered: number;
  new_tokens_last_24h: number;
  tokens_enriching_count: number;
  tokens_under_investigation_count: number;
  watchlisted_opportunities_count: number;
  rejected_opportunities_count: number;
  open_paper_positions_count: number;
  closed_paper_positions_count: number;
  portfolio_starting_capital: number;
  portfolio_available_capital: number;
  portfolio_reserved_capital: number;
  portfolio_net_equity: number;
  realised_pnl_usd: number;
  unrealised_pnl_usd: number;
  total_fees_paid_usd: number;
  current_drawdown_pct: number;
  active_strategies_count: number;
  active_strategies: string[];
  emergency_stop_active: boolean;
  as_of: string;
}

export interface TokenSummary {
  token_mint: string;
  token_id?: number;
  name?: string;
  symbol?: string;
  discovery_source: string;
  discovered_at: string;
  first_seen_price_usd?: number;
  current_price_usd?: number;
  pool_liquidity_usd?: number;
  volume_5m_usd?: number;
  lifecycle_state: string;
  enrichment_status: string;
  top10_holder_share_pct?: number;
  mint_authority_revoked?: boolean;
  freeze_authority_revoked?: boolean;
  risk_level: string;
  opportunity_score?: number;
  latest_decision_outcome?: string;
}

export interface TokenDetail {
  token_mint: string;
  token_id?: number;
  name?: string;
  symbol?: string;
  decimals?: number;
  total_supply?: number;
  discovery_source: string;
  discovered_at: string;
  lifecycle_state: string;
  enrichment_status: string;
  dex_id?: string;
  pair_address?: string;
  pool_liquidity_usd?: number;
  initial_liquidity_usd?: number;
  current_price_usd?: number;
  volume_5m_usd?: number;
  volume_1h_usd?: number;
  buys_5m?: number;
  sells_5m?: number;
  price_change_5m?: number;
  mint_authority?: string;
  freeze_authority?: string;
  mint_authority_revoked?: boolean;
  freeze_authority_revoked?: boolean;
  is_honeypot?: boolean;
  transfer_fee_bps?: number;
  holder_count?: number;
  top10_holder_share_pct?: number;
  deployer_address?: string;
  deployer_prior_token_count?: number;
  deployer_risk_score?: number;
  suspicious_sniper_count?: number;
  social_post_count_1h?: number;
  social_reach_estimate?: number;
  social_sentiment_score?: number;
  narrative_tier?: string;
  narrative_keywords?: string[];
  investigations: any[];
  decisions: any[];
  positions: any[];
}

export interface AgentInvestigation {
  investigation_id: string;
  token_mint: string;
  token_name?: string;
  status: string;
  started_at: string;
  completed_at?: string;
  duration_seconds?: number;
  agent_findings_count: number;
  findings: any[];
  models_used: string[];
  summary_verdict?: string;
}

export interface DecisionRecord {
  decision_id: string;
  token_mint: string;
  token_symbol?: string;
  outcome: string;
  opportunity_rank?: number;
  opportunity_score?: number;
  confidence_score: number;
  risk_level: string;
  reasoning_summary: string;
  supporting_evidence: string[];
  contradictory_evidence: string[];
  risk_factors: string[];
  missing_information: string[];
  decision_timestamp: string;
  expiration_timestamp: string;
  is_expired: boolean;
}

export interface PaperPosition {
  position_id: string;
  proposal_id: string;
  token_mint: string;
  token_symbol?: string;
  strategy_id: string;
  status: string;
  entry_time: string;
  entry_price: number;
  current_mark_price: number;
  quantity: number;
  capital_committed: number;
  unrealised_pnl_usd: number;
  realised_pnl_usd: number;
  total_fees_paid_usd: number;
  stop_loss_price?: number;
  take_profit_price?: number;
  peak_price: number;
  max_favourable_excursion_usd: number;
  max_adverse_excursion_usd: number;
  holding_duration_seconds: number;
  exit_reason?: string;
  closed_at?: string;
  is_simulated: boolean;
}

export interface SystemHealth {
  overall_status: string;
  database_connected: boolean;
  rpc_connected: boolean;
  rpc_latency_ms: number;
  discovery_sources: any[];
  background_backlog_count: number;
  agent_engine_status: string;
  paper_engine_status: string;
  emergency_stop_engaged: boolean;
  recent_errors: any[];
  as_of: string;
}

const BASE_URL = "/api";

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`API Error ${res.status}: ${errorText}`);
  }
  return res.json();
}

export const apiClient = {
  getOverview: () => fetchJson<SystemOverview>(`${BASE_URL}/overview`),
  getDiscoveryTokens: (params?: { limit?: number; source?: string; risk?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.set("limit", String(params.limit));
    if (params?.source) searchParams.set("source", params.source);
    if (params?.risk) searchParams.set("risk", params.risk);
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    return fetchJson<TokenSummary[]>(`${BASE_URL}/discovery${query}`);
  },
  getTokenDetail: (mint: string) => fetchJson<TokenDetail>(`${BASE_URL}/tokens/${mint}`),
  getAgentInvestigations: (params?: { limit?: number; status?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.set("limit", String(params.limit));
    if (params?.status) searchParams.set("status", params.status);
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    return fetchJson<AgentInvestigation[]>(`${BASE_URL}/agents/investigations${query}`);
  },
  getDecisions: (params?: { limit?: number; outcome?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.set("limit", String(params.limit));
    if (params?.outcome) searchParams.set("outcome", params.outcome);
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    return fetchJson<DecisionRecord[]>(`${BASE_URL}/decisions${query}`);
  },
  getPaperPositions: (params?: { status?: string }) => {
    const query = params?.status ? `?status=${params.status}` : "";
    return fetchJson<PaperPosition[]>(`${BASE_URL}/trading/positions${query}`);
  },
  getPaperProposals: () => fetchJson<any[]>(`${BASE_URL}/trading/proposals`),
  getResearchPerformance: () => fetchJson<any>(`${BASE_URL}/research/performance`),
  getSystemHealth: () => fetchJson<SystemHealth>(`${BASE_URL}/health`),
  triggerInvestigation: (mint: string) =>
    fetchJson<{ message: string; task_id?: string }>(`${BASE_URL}/agents/investigate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token_mint: mint }),
    }),
  executeControl: (command: {
    action: string;
    confirmation?: boolean;
    target_id?: string;
    parameters?: Record<string, any>;
    operator_notes?: string;
  }) =>
    fetchJson<{ success: boolean; message?: string; [key: string]: any }>(
      `${BASE_URL}/controls/execute`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(command),
      }
    ),
  createTelemetryStream: (onMessage: (data: any) => void) => {
    const es = new EventSource(`${BASE_URL}/stream/events`);
    es.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        onMessage(parsed);
      } catch (err) {
        console.error("Failed to parse SSE event:", err);
      }
    };
    return es;
  },
};

export const api = apiClient;
