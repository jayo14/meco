# Meco On-Chain Data Source Review & Feasibility Analysis

## 1. Executive Evaluation Matrix

| Data Source | Data Available | Latency | Rate Limits | Cost | Reliability | Complexity | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Standard Solana RPC (HTTP JSON-RPC)** | getSignaturesForAddress, getTransaction, getAccountInfo, getTokenSupply | 600ms - 1,500ms | Strict (10-40 req/s on public RPC; 429 errors under heavy load) | $0 (public) / $50-$250/mo (dedicated node) | Medium (public RPC has intermittent rate limits and dropped requests) | High (requires manual pagination and transaction instruction parsing) | Suitable for ad-hoc point checks and account state polling; unsuitable for full historical transaction backfills across hundreds of tokens without dedicated node. |
| **Solana RPC WebSocket Subscriptions (WSS)** | logsSubscribe, programSubscribe, accountSubscribe, slotSubscribe | 50ms - 200ms | Persistent socket; connection limits apply | $0 (public) / $49-$199/mo (dedicated) | High for active stream; vulnerable to silent disconnects without heartbeat | Medium (requires event loop reconnects and instruction filter) | Best technical approach for real-time pre-signal detection of new pool creations or whale swaps directly from validators. |
| **Pump.fun Bonding Curve PDA State Polling** | Virtual/real SOL & token reserves, curve completion status (151 bytes account data) | 200ms - 500ms | Single getAccountInfo call per token | $0 | High (deterministic state on-chain, avoids paginating thousands of transaction signatures) | Low (simple PDA derivation: ['bonding-curve', mint_bytes]) | Highly practical for pump.fun tokens: allows instant measurement of pool progress and pre-signal bonding curve state with 1 RPC call. |
| **DexScreener Token & Pair API (Current Architecture)** | DEX pairs, 5m/1h/24h volume, buy/sell transaction counts, liquidity, pairCreatedAt | 200ms - 400ms | 300 req/min (generous free tier) | $0 | High (~98% success rate in Meco audit) | Low (already fully integrated) | Ideal for signal-time market snapshot and post-signal checkpoint tracking; lacks sub-minute pre-signal candle history. |
| **Specialized Indexer / Webhook APIs (Helius / Birdeye)** | Enriched swap events, whale buy alerts, pre-parsed token creation webhooks, 1m historical OHLCV | 100ms - 300ms | Generous credit-based tiers | Free tier (50k credits) / $49-$199/mo | High (managed indexing infrastructure) | Low / Medium | Recommended when scaling beyond point prototypes into production pre-signal ingestion. |

---

## 2. Empirical Findings from Live Solana RPC Audit

During live on-chain testing against active tokens from the Meco dataset (e.g. Signal #380 on PumpSwap/Pump.fun):

1. **High Transaction Density:**
   - Querying `getSignaturesForAddress` on the token mint returned **over 5,000 transactions** in a single 60-minute window around signal arrival.
   - Paginating through pair signatures (`GTkRge26...`) required **7 RPC calls (7,000 signatures)** to reach the exact Telegram creation timestamp (`20:54:29`).
   - **Feasibility Barrier:** Pulling full transaction details (`getTransaction`) for all historical signatures across 384 tokens would require **over 2,000,000 RPC requests**. On free/public RPC nodes, this immediately triggers HTTP 429 rate limits.
2. **Bonding Curve PDA Shortcut:**
   - Pump.fun tokens use a deterministic program derived address: `Pubkey.find_program_address([b'bonding-curve', mint_bytes], PUMP_PROGRAM_ID)`.
   - Querying the bonding curve account directly (`getAccountInfo`) returns the exact virtual/real token and SOL reserves with **1 single RPC call (151 bytes)**, avoiding millions of transaction signature fetches.
   - Empirical test confirmed: The bonding curve for Signal #380 was created **36.7 minutes prior** to the public Telegram signal, demonstrating substantial on-chain trading activity prior to public alerts.

---

## 3. Recommended Technical Architecture for Pre-Signal Detection

- **Phase 1 (Lightweight State Polling):** Use deterministic PDA derivation (`bonding-curve`) and DexScreener `pairCreatedAt` timestamp to measure token age and liquidity velocity at zero marginal cost.
- **Phase 2 (Real-Time WebSocket Stream):** For prospective live detection on a VPS, subscribe to `logsSubscribe` filtered by Pump.fun Program ID (`6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`) or Raydium AMM (`675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8`). This provides 50ms-200ms notification of newly created bonding curves before any Telegram aggregator can broadcast.