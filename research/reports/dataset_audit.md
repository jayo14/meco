# Meco Dataset Audit Report

**Generated at:** 2026-10-05T22:32:06.534389+00:00

## 1. High-Level Signal Summary

- **Total Signals:** 393
- **Unique Telegram Messages:** 393
- **Unique Token Addresses:** 391
- **Token Repetition / Duplicate Rate:** 0.51%

### Source Distribution

| Source Channel | Signal Count | Share |
| :--- | :--- | :--- |
| Unknown/Test | 5 | 1.3% |
| Bullish Calls - Solana | 388 | 98.7% |

### Date Distribution

| Date | Signal Count |
| :--- | :--- |
| 2026-10-02 | 122 |
| 2026-10-03 | 110 |
| 2026-10-04 | 100 |
| 2026-10-05 | 61 |

### Solana Mint Validation Status

| Validation Status | Count | Notes |
| :--- | :--- | :--- |
| unvalidated | 73 | Pre-validation phase (Signals 1-73) |
| valid | 319 | Valid SPL Token mint |
| rpc_failed | 1 | Solana RPC error during validation |

### Market Availability Status

| Market Status | Count | Notes |
| :--- | :--- | :--- |
| available | 317 | Valid liquid pair found, observations scheduled |
| no_liquid_pair | 67 | DexScreener found no pool with liquidity |
| fetch_failed | 8 | DexScreener API network/timeout error |
| pending | 1 | Pipeline pending/aborted |

### Primary DEX Distribution (Signal Time)

| DEX ID | Initial Signals | Share |
| :--- | :--- | :--- |
| raydium | 15 | 3.8% |
| pumpswap | 281 | 71.5% |
| meteora | 21 | 5.3% |
| none | 76 | 19.3% |

## 2. Observation Coverage by Target Checkpoint

| Target | Eligible | Captured | Coverage % | Success | Failed | Med Delay (s) | Max Delay (s) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| T+10    |      317 |      227 |      71.6% |     226 |      1 |         +1.0s |        +28.0s |
| T+30    |      317 |      310 |      97.8% |     302 |      8 |         +1.0s |        +36.0s |
| T+60    |      317 |      308 |      97.2% |     301 |      7 |         +1.0s |        +27.0s |
| T+120   |      316 |      223 |      70.6% |     219 |      4 |         +1.0s |        +14.0s |
| T+180   |      316 |      215 |      68.0% |     208 |      7 |         +1.0s |      +5967.0s |
| T+300   |      316 |      291 |      92.1% |     281 |     10 |         +1.0s |     +55753.0s |
| T+600   |      313 |      208 |      66.5% |     199 |      9 |         +1.0s |     +55753.0s |
| T+900   |      313 |      271 |      86.6% |     264 |      7 |         +1.0s |     +55752.0s |
| T+1800  |      312 |      236 |      75.6% |     223 |     13 |         +1.0s |     +55754.0s |
| T+3600  |      311 |      203 |      65.3% |     199 |      4 |         +1.0s |     +56348.0s |
| T+21600 |      277 |       18 |       6.5% |      18 |      0 |     +56348.0s |     +56353.0s |
| T+86400 |      251 |        0 |       0.0% |       0 |      0 |           n/a |           n/a |

## 3. Pair-Level Observation Coverage

- **Total Stored Pair Rows:** 5299
- **Signals with Pair History:** 220 (Started at Signal #114)
- **Average Pairs per Checkpoint:** 2.62
- **Median Pairs per Checkpoint:** 2.0
- **Max Pairs per Checkpoint:** 27

### DEX Breakdown Across All Stored Pairs

| DEX | Pair Rows Captured |
| :--- | :--- |
| pumpswap | 1841 |
| pumpfun | 1840 |
| meteora | 1412 |
| meteoradbc | 124 |
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