# Meco Anomaly & Data Quality Report

## Summary of Detected Anomalies

- **Total Anomaly Events Flagged:** 165
- **Critical:** 1
- **High:** 76
- **Medium:** 77
- **Informational:** 11

### Breakdown by Anomaly Category

| Anomaly Type | Occurrences | Default Action |
| :--- | :--- | :--- |
| severe_observation_delay | 69 | exclude_from_returns |
| no_liquid_pair_at_signal | 67 | exclude_all |
| non_standard_target | 11 | exclude_from_returns |
| dexscreener_fetch_failed | 8 | exclude_all |
| test_signal | 5 | exclude_all |
| primary_pair_switched | 2 | inspect |
| extreme_liquidity_drop | 1 | exclude_from_returns |
| signal_status_pending | 1 | exclude_all |
| solana_rpc_failed | 1 | exclude_all |

## Critical & High Severity Details

### 1. Signal #103 Liquidity Anomaly
- **Signal ID:** 103
- **Token:** `ETXqxfVoPN9f1qX1EV9qPWNqYuu5TUUUXMUM4SsniJga` ($COZY)
- **Initial Recorded State:** $345,863,635.06 liquidity, $0.3146 price on Raydium pool.
- **Subsequent State (T+900):** $20,824.37 liquidity, $0.00001863 price (-99.994%).
- **Cause / Hypothesis:** Artificial pool pairing with inflated token valuation or wash liquidity that was de-indexed/withdrawn.
- **Research Handling:** Kept intact in database, strictly excluded from outcome and return statistics to avoid contaminating aggregates.

### 2. Severe Observation Delays (Catch-up Gaps)
- Flagged count: 69 observations with delay > 300 seconds.
- **Cause:** When the development machine was asleep or offline (e.g. 15.69-hour gap between IDs 232 and 233), in-flight asyncio observation tasks executed immediately upon resumption with zero delay, recording `target_seconds=3600` or `21600` but an actual elapsed `seconds_since_signal` of 56,000s - 78,000s.
- **Research Handling:** An observation is only considered valid for a target checkpoint if `abs(seconds_since_signal - target_seconds) <= 60s`.

### 3. Primary Pair Switches Across Checkpoints
- **Signal #52:** Started on Raydium (`AZuZu...`), at T+900 switched to Meteora (`8yXp...`), then at T+1800 returned to Raydium as Raydium liquidity surpassed Meteora ($88.7K vs $65.8K).
- **Signal #223:** Started on PumpSwap (`2B8t...`) with $65K liquidity, subsequently created a Meteora pool (`4s2b...`) with $340K liquidity.

### 4. Market Availability Failures
- **65 signals (17.0%)** arrived with `market_status = 'no_liquid_pair'`. No pools with valid liquidity existed on DexScreener at signal time.
- **8 signals (2.1%)** suffered DexScreener HTTP timeouts/fetch failures at signal time.
- **1 signal (#226)** suffered Solana RPC validator timeout, leaving it in `pending` state.