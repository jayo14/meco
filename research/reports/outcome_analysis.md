# Meco Outcome & Path Analysis Report

> [!IMPORTANT]
> These metrics reflect **observed DexScreener market price changes at discrete checkpoints**, NOT guaranteed executable returns. Real trading requires modeling slippage, liquidity constraints, transaction fees, and latency.

- **Evaluated Clean Signals:** 311 (excluding test signals, #103, and unliquid calls)

## 1. Checkpoint Return Distributions

| Checkpoint | Samples | Median Return | Mean Return | Positive % | ≥ +20% (Win) | ≤ -20% (Loss) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| T+10       |     226 |        +0.00% |      +0.33% |       8.4% |          1.8% |           1.8% |
| T+30       |     298 |        +0.00% |      -0.42% |      33.2% |          6.7% |           4.7% |
| T+60       |     297 |        +0.00% |      -1.24% |      43.8% |         11.8% |          15.5% |
| T+120      |     219 |        -0.44% |      -3.07% |      42.9% |         18.7% |          23.7% |
| T+180      |     207 |        -2.36% |      -2.31% |      38.6% |         21.3% |          27.1% |
| T+300      |     277 |        -8.02% |      -5.65% |      35.0% |         20.2% |          36.5% |
| T+600      |     194 |       -14.27% |      -9.30% |      34.0% |         21.1% |          45.9% |
| T+900      |     255 |       -22.15% |      -9.34% |      33.7% |         23.9% |          51.4% |
| T+1800     |     209 |       -32.99% |     -12.40% |      33.5% |         20.1% |          55.0% |
| T+3600     |     175 |       -59.37% |     -22.96% |      24.0% |         19.4% |          63.4% |

## 2. Excursion (MFE / MAE) & Path Dynamics

### Maximum Favorable Excursion (MFE - Peak Upside)
- **Median Peak Upside:** +12.73%
- **Mean Peak Upside:**   +55.69%
- **Median Time to Peak:** 121 seconds (~2.0 min)

### Maximum Adverse Excursion (MAE - Worst Drawdown)
- **Median Worst Drawdown:** -50.68%
- **Mean Worst Drawdown:**   -49.58%
- **Median Time to Trough:** 901 seconds (~15.0 min)

### Peak-to-Trough Collapse
- **Median Drawdown After Reaching Peak:** -73.51%
- **Mean Drawdown After Reaching Peak:**   -63.01%

## 3. Threshold Reachability Matrix

| Threshold | Signals Reached | Percentage |
| :--- | :--- | :--- |
| Hit ≥ +20% MFE  | 140 / 311 | 45.0% |
| Hit ≥ +50% MFE  | 86 / 311 | 27.7% |
| Hit ≥ +100% MFE | 45 / 311 | 14.5% |
| Hit ≤ -20% MAE  | 210 / 311 | 67.5% |
| Hit ≤ -50% MAE  | 156 / 311 | 50.2% |
| Hit ≤ -80% MAE  | 102 / 311 | 32.8% |
| Hit ≤ -90% MAE  | 69 / 311 | 22.2% |

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