# Meco Quantitative Research Report: Executive Summary

**Date Generated:** 2026-10-05T21:41:20.948775+00:00
**Dataset Window:** 2026-10-02 to 2026-10-05 (4 Days)
**Total Captured Signals:** 386 (384 unique token mints)
**Clean Evaluated Signals:** 305 (excluding test calls, unliquid pools, and anomaly #103)

---

## 1. Core Mission Question & Empirical Verdict

> **Core Research Question:**
> *When a particular Telegram signal appears, is there measurable information available at that moment that can help predict a sufficiently attractive future market opportunity after accounting for execution constraints and risk?*

### Empirical Verdict: **NO EXECUTABLE EDGE FOUND (NEGATIVE EXPECTED VALUE)**

After rigorous chronological auditing and execution modeling accounting for real-world slippage, DEX pool fees, and network latency:
- **The raw signal source ('Bullish Calls - Solana') is not predictive of profitable future trading opportunities.**
- The signal operates as a delayed public notification channel for tokens that have already experienced their primary accumulation.
- While superficial marketing metrics show tokens 'pumping' (45.4% reach ≥ +20% at some micro-interval), the peak occurs at a median of **121 seconds (2 minutes)** after signal arrival, followed immediately by a catastrophic **-72.03% median collapse**.
- Once execution friction (1.5% base slippage + pool price impact + 0.50% roundtrip DEX fees + gas) is subtracted, all tested hypotheses—including naive follow, momentum scalp, anti-climax filter, and trailing stops—produce consistent net capital losses across both in-sample training and out-of-sample validation periods.

---

## 2. Quantitative Summary of Market Behavior

| Metric | Observed Value | Interpretation |
| :--- | :--- | :--- |
| **Median Checkpoint Return (T+10s)** | +0.00% | Latency cushion: prices have rarely begun moving on DEX within 10s. |
| **Median Checkpoint Return (T+60s)** | +0.00% | Equilibrium point: 44.5% positive, 55.5% flat or negative. |
| **Median Checkpoint Return (T+300s)** | -7.44% | Reversal in full effect: median return is distinctly negative. |
| **Median Checkpoint Return (T+900s)** | -22.02% | Deep decay: median token has lost ~22% of its initial value. |
| **Median Peak Upside (MFE)** | +12.94% | Modest median upside before failure; heavily right-skewed by rare outliers. |
| **Median Time to Peak (MFE)** | 121 seconds | Extremely compressed window (~2 min). Impossible for manual traders. |
| **Median Worst Drawdown (MAE)** | -50.68% | Severe downside risk: half of all tokens lose ≥ 46.8% of value. |
| **Drawdown After Peak** | -73.51% | Severe post-peak drop: even 'winners' immediately dump. |
| **Catastrophic Collapse Rate (≤ -80%)** | 32.5% | Roughly 1 in 3 called tokens essentially go to zero. |

---

## 3. Data Quality & Historical Artifacts

1. **Signal #103 Liquidity Anomaly:** Signal #103 reported $345.8M initial liquidity on Raydium pool `E7VkHPd...` that collapsed to $20.8K at T+900 (-99.994%). Correctly flagged and excluded from returns calculations while preserved in the raw database.
2. **Offline Catch-Up Observations:** 69 observations exhibited multi-hour delays (up to 15.6 hours) caused by local laptop sleep cycles. An observation validity threshold (`|actual - target| <= 60s`) was introduced to prevent stale data contamination.
3. **Unliquid Market Rate:** 65 signals (16.9%) arrived without any liquid pool on DexScreener, indicating the token had either not yet pooled, was rug-pulled instantly, or was an invalid call.
4. **Feature Evolution:**
   - Solana mint validation began at Signal #74 (309 valid, 1 rpc_failed).
   - Pair-level candidate tracking began at Signal #114 (5,125 pair records across 213 signals, averaging 2.63 pairs per checkpoint).

---

## 4. Hypothesis Testing & Paper Trading Results

All strategies were evaluated chronologically: **Train Set (earlier 65%)** vs **Test Set (later 35%)** with $100 simulated position size:

| Strategy | Feature Filter | Train Win% | Train Net PnL | Test Win% | Test Net PnL | Scientific Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **H0: Baseline Naive Follow** | `Any valid signal with price > ` | 28.9% | $-1664.90 | 31.8% | $-600.45 | `REJECTED` |
| **H1: Anti-Climax Filter (L** | `volume_5m <= $35,000 AND (volu` | 34.4% | $-363.01 | 27.8% | $-218.75 | `REJECTED` |
| **H2: Buy-Pressure Momentum** | `buy_sell_ratio >= 1.30 AND liq` | 29.3% | $-701.49 | 36.0% | $-43.25 | `REJECTED` |
| **H3: Trailing Stop Momentu** | `liquidity_usd >= $15,000` | 24.4% | $-1768.98 | 31.9% | $-554.08 | `REJECTED` |

### Why Did All Hypotheses Fail?
1. **Late-Stage Market Arrival:** The observed free-channel signals are consistent with a late-stage distribution pattern. However, the available data cannot establish whether VIP participants caused the observed market behavior or whether the free channel itself functions as exit liquidity. By the time the free channel post appears, the initial momentum has typically already occurred.
2. **The Friction Barrier:** To profit from a token whose median peak is +12.9% within 120s, a trader must overcome:
   - ~1.5% entry slippage
   - ~1.5% exit slippage
   - 0.50% roundtrip DEX fee
   - Solana gas priority fees
   - High failure risk on quick stop-outs (-12% to -15%)
   The net expected value is mathematically negative.

---

## 5. Recommended Strategic Next Steps

1. **DO NOT deploy live real-money trading on this channel.** Real capital would be systematically drained by friction and negative drift.
2. **Continuous Background Monitoring (VPS Preparation):** Move Meco to a VPS so collection never suffers offline catch-up gaps. Continue accumulating unpolluted data to observe whether market regime shifts alter channel behavior.
3. **Investigate Alternative Signal Sources or Pre-Call On-Chain Events:** True edge on Solana meme-coins requires detecting token creation or whale swaps on-chain *before* or *independent of* public Telegram channels.
4. **Maintain Strict Scientific Rigor:** Reject any proposal to overfit parameters or trade live without verified forward paper-trading profit.