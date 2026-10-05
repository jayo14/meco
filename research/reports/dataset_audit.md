# Meco Dataset Audit Report

**Generated at:** 2026-10-05T21:41:20.948775+00:00

## 1. High-Level Signal Summary

- **Total Signals:** 386
- **Unique Telegram Messages:** 386
- **Unique Token Addresses:** 384
- **Token Repetition / Duplicate Rate:** 0.52%

### Source Distribution

| Source Channel | Signal Count | Share |
| :--- | :--- | :--- |
| Unknown/Test | 5 | 1.3% |
| Bullish Calls - Solana | 381 | 98.7% |

### Date Distribution

| Date | Signal Count |
| :--- | :--- |
| 2026-10-02 | 122 |
| 2026-10-03 | 110 |
| 2026-10-04 | 100 |
| 2026-10-05 | 54 |

### Solana Mint Validation Status

| Validation Status | Count | Notes |
| :--- | :--- | :--- |
| unvalidated | 73 | Pre-validation phase (Signals 1-73) |
| valid | 312 | Valid SPL Token mint |
| rpc_failed | 1 | Solana RPC error during validation |

### Market Availability Status

| Market Status | Count | Notes |
| :--- | :--- | :--- |
| available | 311 | Valid liquid pair found, observations scheduled |
| no_liquid_pair | 66 | DexScreener found no pool with liquidity |
| fetch_failed | 8 | DexScreener API network/timeout error |
| pending | 1 | Pipeline pending/aborted |

### Primary DEX Distribution (Signal Time)

| DEX ID | Initial Signals | Share |
| :--- | :--- | :--- |
| raydium | 15 | 3.9% |
| pumpswap | 275 | 71.2% |
| meteora | 21 | 5.4% |
| none | 75 | 19.4% |

## 2. Observation Coverage by Target Checkpoint

| Target | Eligible | Captured | Coverage % | Success | Failed | Med Delay (s) | Max Delay (s) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| T+10    |      311 |      221 |      71.1% |     220 |      1 |         +1.0s |        +28.0s |
| T+30    |      311 |      304 |      97.7% |     296 |      8 |         +1.0s |        +36.0s |
| T+60    |      311 |      302 |      97.1% |     295 |      7 |         +1.0s |        +27.0s |
| T+120   |      311 |      218 |      70.1% |     214 |      4 |         +1.0s |        +14.0s |
| T+180   |      311 |      210 |      67.5% |     203 |      7 |         +1.0s |      +5967.0s |
| T+300   |      311 |      286 |      92.0% |     276 |     10 |         +1.0s |     +55753.0s |
| T+600   |      311 |      206 |      66.2% |     198 |      8 |         +1.0s |     +55753.0s |
| T+900   |      311 |      269 |      86.5% |     262 |      7 |         +1.0s |     +55752.0s |
| T+1800  |      309 |      233 |      75.4% |     220 |     13 |         +1.0s |     +55754.0s |
| T+3600  |      305 |      197 |      64.6% |     193 |      4 |         +1.0s |     +56348.0s |
| T+21600 |      277 |       18 |       6.5% |      18 |      0 |     +56348.0s |     +56353.0s |
| T+86400 |      238 |        0 |       0.0% |       0 |      0 |           n/a |           n/a |

## 3. Pair-Level Observation Coverage

- **Total Stored Pair Rows:** 5197
- **Signals with Pair History:** 214 (Started at Signal #114)
- **Average Pairs per Checkpoint:** 2.63
- **Median Pairs per Checkpoint:** 2.0
- **Max Pairs per Checkpoint:** 27

### DEX Breakdown Across All Stored Pairs

| DEX | Pair Rows Captured |
| :--- | :--- |
| pumpswap | 1797 |
| pumpfun | 1796 |
| meteora | 1399 |
| meteoradbc | 123 |
| raydium | 78 |
| orca | 4 |

## 4. Key Audit Findings & Structural Realities

1. **Test Signals:** 5 early signals (#1, #2, #3, #5, #10) were manually or locally injected test runs (Wrapped SOL and test mints) with `source_name=None`. They must be isolated from strategy research.
2. **Feature Timeline Evolution:**
   - Signals 1-73: Solana mint validation had not yet been deployed.
   - Signal #74+: Solana on-chain mint validation was operational (309 valid, 1 rpc_failed).
   - Signals 1-113: Pair-level snapshots were not yet stored in `market_pair_observations`.
   - Signal #114+: Full candidate pair snapshots captured for all observations.
   - Observation intervals: Early signals only targeted 30, 60, 300, 900s. Targets 10, 120, 180, 600s were added later; 21600s (6h) was added around signal 170+; 86400s (24h) has 0 captures due to local sleep/offline cycles.
3. **Observation Timing Precision:** When the process is active, median delay is exactly 1.0s. However, 69 observations exhibit delays >300s (up to ~15.6 hours) caused by laptop sleep/restarts catching up on expired targets.
4. **No-Liquid-Pair Rate:** 65 of 383 signals (17.0%) had no liquid DexScreener pair at arrival time, meaning the signal called a token that could not be verified on automated DEX pools immediately.