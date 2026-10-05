# Meco Dataset Audit Report

**Generated at:** 2026-10-05T21:13:31.079778+00:00

## 1. High-Level Signal Summary

- **Total Signals:** 384
- **Unique Telegram Messages:** 384
- **Unique Token Addresses:** 382
- **Token Repetition / Duplicate Rate:** 0.52%

### Source Distribution

| Source Channel | Signal Count | Share |
| :--- | :--- | :--- |
| Unknown/Test | 5 | 1.3% |
| Bullish Calls - Solana | 379 | 98.7% |

### Date Distribution

| Date | Signal Count |
| :--- | :--- |
| 2026-10-02 | 122 |
| 2026-10-03 | 110 |
| 2026-10-04 | 100 |
| 2026-10-05 | 52 |

### Solana Mint Validation Status

| Validation Status | Count | Notes |
| :--- | :--- | :--- |
| unvalidated | 73 | Pre-validation phase (Signals 1-73) |
| valid | 310 | Valid SPL Token mint |
| rpc_failed | 1 | Solana RPC error during validation |

### Market Availability Status

| Market Status | Count | Notes |
| :--- | :--- | :--- |
| available | 310 | Valid liquid pair found, observations scheduled |
| no_liquid_pair | 65 | DexScreener found no pool with liquidity |
| fetch_failed | 8 | DexScreener API network/timeout error |
| pending | 1 | Pipeline pending/aborted |

### Primary DEX Distribution (Signal Time)

| DEX ID | Initial Signals | Share |
| :--- | :--- | :--- |
| raydium | 15 | 3.9% |
| pumpswap | 274 | 71.4% |
| meteora | 21 | 5.5% |
| none | 74 | 19.3% |

## 2. Observation Coverage by Target Checkpoint

| Target | Eligible | Captured | Coverage % | Success | Failed | Med Delay (s) | Max Delay (s) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| T+10    |      310 |      220 |      71.0% |     219 |      1 |         +1.0s |        +28.0s |
| T+30    |      310 |      303 |      97.7% |     295 |      8 |         +1.0s |        +36.0s |
| T+60    |      309 |      300 |      97.1% |     293 |      7 |         +1.0s |        +27.0s |
| T+120   |      309 |      216 |      69.9% |     212 |      4 |         +1.0s |        +14.0s |
| T+180   |      309 |      208 |      67.3% |     201 |      7 |         +1.0s |      +5967.0s |
| T+300   |      309 |      284 |      91.9% |     274 |     10 |         +1.0s |     +55753.0s |
| T+600   |      307 |      202 |      65.8% |     194 |      8 |         +1.0s |     +55753.0s |
| T+900   |      307 |      265 |      86.3% |     258 |      7 |         +1.0s |     +55752.0s |
| T+1800  |      305 |      229 |      75.1% |     216 |     13 |         +1.0s |     +55754.0s |
| T+3600  |      300 |      192 |      64.0% |     188 |      4 |         +1.0s |     +56348.0s |
| T+21600 |      277 |       18 |       6.5% |      18 |      0 |     +56348.0s |     +56353.0s |
| T+86400 |      235 |        0 |       0.0% |       0 |      0 |           n/a |           n/a |

## 3. Pair-Level Observation Coverage

- **Total Stored Pair Rows:** 5125
- **Signals with Pair History:** 213 (Started at Signal #114)
- **Average Pairs per Checkpoint:** 2.63
- **Median Pairs per Checkpoint:** 2.0
- **Max Pairs per Checkpoint:** 27

### DEX Breakdown Across All Stored Pairs

| DEX | Pair Rows Captured |
| :--- | :--- |
| pumpswap | 1771 |
| pumpfun | 1770 |
| meteora | 1380 |
| meteoradbc | 122 |
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