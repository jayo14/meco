# Meco Strategy Hypotheses & Paper Trading Evaluation

> [!IMPORTANT]
> Chronological temporal split applied: **Train Set (Earlier 65% of signals)** vs **Validation Set (Later 35% of signals)**. Realistic execution simulation models 1.5% base slippage + price impact + 0.50% roundtrip DEX fees + Solana gas fees.

## Summary of Hypothesis Performance (Train vs Out-of-Sample Test)

| Hypothesis | Train Sigs | Train Win% | Train Net PnL | Test Sigs | Test Win% | Test Net PnL | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| H0: Baseline Naive Follow (All S |        194 |      28.4% | $    -1752.00 |        90 |     32.2% | $    -586.67 | **REJECTED** |
| H1: Anti-Climax Filter (Low Volu |         66 |      33.3% | $     -391.87 |        37 |     27.0% | $    -260.39 | **REJECTED** |
| H2: Buy-Pressure Momentum Scalp |         76 |      28.9% | $     -724.30 |        26 |     34.6% | $     -89.59 | **REJECTED** |
| H3: Trailing Stop Momentum Rider |        179 |      24.0% | $    -1850.04 |        74 |     32.4% | $    -503.68 | **REJECTED** |

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
- **In-Sample Train Set:** 194 trades, 28.4% win rate, Mean Net: -8.51%, Total PnL: $-1752.00
- **Out-of-Sample Test Set:** 90 trades, 32.2% win rate, Mean Net: -6.00%, Total PnL: $-586.67

- **Evidence:** Train PnL: $-1752.00 (28.4% win), Test PnL: $-586.67 (32.2% win)
- **Counter-Evidence:** Test set mean net return is -6.00%. Slippage (~3-4% roundtrip) and $0.02 Solana fees consistently degrade theoretical gross gains.
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
- **In-Sample Train Set:** 66 trades, 33.3% win rate, Mean Net: -5.42%, Total PnL: $-391.87
- **Out-of-Sample Test Set:** 37 trades, 27.0% win rate, Mean Net: -6.52%, Total PnL: $-260.39

- **Evidence:** Train PnL: $-391.87 (33.3% win), Test PnL: $-260.39 (27.0% win)
- **Counter-Evidence:** Test set mean net return is -6.52%. Slippage (~3-4% roundtrip) and $0.02 Solana fees consistently degrade theoretical gross gains.
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
- **In-Sample Train Set:** 76 trades, 28.9% win rate, Mean Net: -9.01%, Total PnL: $-724.30
- **Out-of-Sample Test Set:** 26 trades, 34.6% win rate, Mean Net: -2.93%, Total PnL: $-89.59

- **Evidence:** Train PnL: $-724.30 (28.9% win), Test PnL: $-89.59 (34.6% win)
- **Counter-Evidence:** Test set mean net return is -2.93%. Slippage (~3-4% roundtrip) and $0.02 Solana fees consistently degrade theoretical gross gains.
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
- **In-Sample Train Set:** 179 trades, 24.0% win rate, Mean Net: -9.82%, Total PnL: $-1850.04
- **Out-of-Sample Test Set:** 74 trades, 32.4% win rate, Mean Net: -6.29%, Total PnL: $-503.68

- **Evidence:** Train PnL: $-1850.04 (24.0% win), Test PnL: $-503.68 (32.4% win)
- **Counter-Evidence:** Test set mean net return is -6.29%. Slippage (~3-4% roundtrip) and $0.02 Solana fees consistently degrade theoretical gross gains.
- **Known Limitations:** Discrete observation checkpoints (10s, 30s, 60s...) underestimate intra-checkpoint wick drawdowns.
- **Potential Leakage:** None.
- **Verdict:** `REJECTED (Negative EV after execution constraints)`

---
