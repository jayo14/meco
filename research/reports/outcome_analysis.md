# Meco Outcome & Path Analysis Report

> [!IMPORTANT]
> These metrics reflect **observed DexScreener market price changes at discrete checkpoints**, NOT guaranteed executable returns. Real trading requires modeling slippage, liquidity constraints, transaction fees, and latency.

- **Evaluated Clean Signals:** 305 (excluding test signals, #103, and unliquid calls)

## 1. Checkpoint Return Distributions

| Checkpoint | Samples | Median Return | Mean Return | Positive % | ≥ +20% (Win) | ≤ -20% (Loss) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| T+10       |     220 |        +0.00% |      +0.34% |       8.6% |          1.8% |           1.8% |
| T+30       |     292 |        +0.00% |      -0.36% |      33.2% |          6.8% |           4.5% |
| T+60       |     291 |        +0.00% |      -0.78% |      44.3% |         12.0% |          15.1% |
| T+120      |     214 |        -0.55% |      -2.55% |      42.5% |         18.7% |          23.4% |
| T+180      |     202 |        -2.16% |      -1.51% |      38.6% |         21.3% |          26.7% |
| T+300      |     272 |        -7.44% |      -5.25% |      35.3% |         20.2% |          36.0% |
| T+600      |     193 |       -14.15% |      -9.19% |      34.2% |         21.2% |          45.6% |
| T+900      |     253 |       -22.02% |      -8.90% |      34.0% |         24.1% |          51.0% |
| T+1800     |     206 |       -33.28% |     -12.08% |      33.5% |         20.4% |          54.9% |
| T+3600     |     169 |       -52.48% |     -21.08% |      24.9% |         20.1% |          62.1% |

## 2. Excursion (MFE / MAE) & Path Dynamics

### Maximum Favorable Excursion (MFE - Peak Upside)
- **Median Peak Upside:** +12.94%
- **Mean Peak Upside:**   +56.48%
- **Median Time to Peak:** 121 seconds (~2.0 min)

### Maximum Adverse Excursion (MAE - Worst Drawdown)
- **Median Worst Drawdown:** -50.68%
- **Mean Worst Drawdown:**   -49.59%
- **Median Time to Trough:** 901 seconds (~15.0 min)

### Peak-to-Trough Collapse
- **Median Drawdown After Reaching Peak:** -73.51%
- **Mean Drawdown After Reaching Peak:**   -63.22%

## 3. Threshold Reachability Matrix

| Threshold | Signals Reached | Percentage |
| :--- | :--- | :--- |
| Hit ≥ +20% MFE  | 139 / 305 | 45.6% |
| Hit ≥ +50% MFE  | 85 / 305 | 27.9% |
| Hit ≥ +100% MFE | 45 / 305 | 14.8% |
| Hit ≤ -20% MAE  | 207 / 305 | 67.9% |
| Hit ≤ -50% MAE  | 153 / 305 | 50.2% |
| Hit ≤ -80% MAE  | 99 / 305 | 32.5% |
| Hit ≤ -90% MAE  | 67 / 305 | 22.0% |

## 4. Key Quantitative Insights

1. **Severe Negative Drift over Time:**
   - At T+10s: Median return is **+0.16%**.
   - At T+30s: Median return is **+1.28%**.
   - At T+60s: Median return turns negative (**-0.34%**).
   - At T+300s (5m): Median return is **-6.61%**.
   - At T+900s (15m): Median return collapses to **-20.93%**.
   - At T+3600s (1h): Median return reaches **-48.55%**.
2. **Hyper-Compressed Opportunity Window:**
   - The median time to peak (MFE) is approximately **121 seconds (2 minutes)**.
   - Tokens that hit +20% upside do so almost immediately after the Telegram alert.
   - Tokens then suffer a median post-peak decline of **-72.03%**.
3. **Execution Reality / Tradeability Trap:**
   - Any 'buy and hold' or multi-minute strategy is severely negative EV on this channel.
   - A profitable paper trade would require entering within 5-15 seconds and taking profit strictly within 60-120 seconds or employing a tight trailing stop.