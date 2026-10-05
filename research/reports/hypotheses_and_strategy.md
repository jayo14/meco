# Meco Strategy Hypotheses & Paper Trading Evaluation

> [!IMPORTANT]
> Chronological temporal split applied: **Train Set (Earlier 65% of signals)** vs **Validation Set (Later 35% of signals)**. Realistic execution simulation models 1.5% base slippage + price impact + 0.50% roundtrip DEX fees + Solana gas fees.

## Summary of Hypothesis Performance (Train vs Out-of-Sample Test)

| Hypothesis | Train Sigs | Train Win% | Train Net PnL | Test Sigs | Test Win% | Test Net PnL | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| H0: Baseline Naive Follow (All S |        190 |      28.9% | $    -1664.90 |        88 |     31.8% | $    -600.45 | **REJECTED** |
| H1: Anti-Climax Filter (Low Volu |         64 |      34.4% | $     -363.01 |        36 |     27.8% | $    -218.75 | **REJECTED** |
| H2: Buy-Pressure Momentum Scalp |         75 |      29.3% | $     -701.49 |        25 |     36.0% | $     -43.25 | **REJECTED** |
| H3: Trailing Stop Momentum Rider |        176 |      24.4% | $    -1768.98 |        72 |     31.9% | $    -554.08 | **REJECTED** |

## Detailed Hypotheses Documentation

### H0: Baseline Naive Follow (All Signals)

**Rationale:** Test whether blindly trading every valid signal from this channel yields positive EV after realistic slippage and fees.

- **Feature Condition:** `Any valid signal with price > 0 and liquidity >= $5,000`
- **Entry Condition:** Market buy at T+0 with 1.5% base slippage + price impact
- **Exit Condition:** Take profit +25% or stop loss -15% or timeout at 180s
- **Stop Loss:** -15.0%
- **Take Profit:** 25.0%
- **Max Holding Period:** 180s

#### Performance Breakdown
- **In-Sample Train Set:** 190 trades, 28.9% win rate, Mean Net: -8.24%, Total PnL: $-1664.90
- **Out-of-Sample Test Set:** 88 trades, 31.8% win rate, Mean Net: -6.30%, Total PnL: $-600.45

- **Evidence:** Train PnL: $-1664.90 (28.9% win), Test PnL: $-600.45 (31.8% win)
- **Counter-Evidence:** Test set mean net return is -6.30%. Slippage (~3-4% roundtrip) and $0.02 Solana fees consistently degrade theoretical gross gains.
- **Known Limitations:** Does not filter for illiquid tokens or post-pump exhaustion.
- **Potential Leakage:** None (pure baseline).
- **Verdict:** `REJECTED (Negative EV after execution constraints)`

---

### H1: Anti-Climax Filter (Low Volume/Liquidity)

**Rationale:** Tokens called with low prior 5m volume (< $35k) and low volume-to-liquidity (<= 1.2) have not yet experienced severe volume climax/exhaustion and suffer lower catastrophic drawdowns.

- **Feature Condition:** `volume_5m <= $35,000 AND (volume_5m / liquidity_usd) <= 1.2`
- **Entry Condition:** Market buy at T+0 with slippage + impact model
- **Exit Condition:** Take profit +20% or stop loss -12% or timeout at 120s
- **Stop Loss:** -12.0%
- **Take Profit:** 20.0%
- **Max Holding Period:** 120s

#### Performance Breakdown
- **In-Sample Train Set:** 64 trades, 34.4% win rate, Mean Net: -5.15%, Total PnL: $-363.01
- **Out-of-Sample Test Set:** 36 trades, 27.8% win rate, Mean Net: -5.56%, Total PnL: $-218.75

- **Evidence:** Train PnL: $-363.01 (34.4% win), Test PnL: $-218.75 (27.8% win)
- **Counter-Evidence:** Test set mean net return is -5.56%. Slippage (~3-4% roundtrip) and $0.02 Solana fees consistently degrade theoretical gross gains.
- **Known Limitations:** Smaller sample size; many low-volume tokens have sluggish price action that times out.
- **Potential Leakage:** Features are strictly T+0 signal-time measurements.
- **Verdict:** `REJECTED (Negative EV after execution constraints)`

---

### H2: Buy-Pressure Momentum Scalp

**Rationale:** Tokens with high initial buy/sell ratio (>= 1.30) and healthy liquidity (>= $15,000) have sufficient buy momentum to hit a quick +20% scalp before the inevitable 2-minute peak reversal.

- **Feature Condition:** `buy_sell_ratio >= 1.30 AND liquidity_usd >= $15,000`
- **Entry Condition:** Market buy at T+0 with slippage + impact model
- **Exit Condition:** Take profit +20% or stop loss -12% or timeout at 120s
- **Stop Loss:** -12.0%
- **Take Profit:** 20.0%
- **Max Holding Period:** 120s

#### Performance Breakdown
- **In-Sample Train Set:** 75 trades, 29.3% win rate, Mean Net: -8.83%, Total PnL: $-701.49
- **Out-of-Sample Test Set:** 25 trades, 36.0% win rate, Mean Net: -1.21%, Total PnL: $-43.25

- **Evidence:** Train PnL: $-701.49 (29.3% win), Test PnL: $-43.25 (36.0% win)
- **Counter-Evidence:** Test set mean net return is -1.21%. Slippage (~3-4% roundtrip) and $0.02 Solana fees consistently degrade theoretical gross gains.
- **Known Limitations:** High buy ratio at T+0 can sometimes represent the tail-end of retail chasing rather than sustained accumulation.
- **Potential Leakage:** Zero lookahead. Buy/sell counts are pre-signal 5m window.
- **Verdict:** `REJECTED (Negative EV after execution constraints)`

---

### H3: Trailing Stop Momentum Rider

**Rationale:** Instead of a static take profit, enter tokens with liquidity >= $15k and trailing stop (trail 10% from peak once in profit) to capture outsized upside spikes while capping downside.

- **Feature Condition:** `liquidity_usd >= $15,000`
- **Entry Condition:** Market buy at T+0 with slippage + impact model
- **Exit Condition:** Trailing stop 10% from peak, or stop loss -15%, max hold 300s
- **Stop Loss:** -15.0%
- **Take Profit:** 100.0%
- **Max Holding Period:** 300s

#### Performance Breakdown
- **In-Sample Train Set:** 176 trades, 24.4% win rate, Mean Net: -9.53%, Total PnL: $-1768.98
- **Out-of-Sample Test Set:** 72 trades, 31.9% win rate, Mean Net: -7.18%, Total PnL: $-554.08

- **Evidence:** Train PnL: $-1768.98 (24.4% win), Test PnL: $-554.08 (31.9% win)
- **Counter-Evidence:** Test set mean net return is -7.18%. Slippage (~3-4% roundtrip) and $0.02 Solana fees consistently degrade theoretical gross gains.
- **Known Limitations:** Discrete observation checkpoints (10s, 30s, 60s...) underestimate intra-checkpoint wick drawdowns.
- **Potential Leakage:** None.
- **Verdict:** `REJECTED (Negative EV after execution constraints)`

---
