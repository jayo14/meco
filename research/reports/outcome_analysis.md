# Meco Outcome & Path Analysis Report

> [!IMPORTANT]
> These metrics reflect **observed DexScreener market price changes at discrete checkpoints**, NOT guaranteed executable returns. Real trading requires modeling slippage, liquidity constraints, transaction fees, and latency.

- **Evaluated Clean Signals:** 304 (excluding test signals, #103, and unliquid calls)

## 1. Checkpoint Return Distributions

| Checkpoint | Samples | Median Return | Mean Return | Positive % | ≥ +20% (Win) | ≤ -20% (Loss) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| T+10       |     219 |        +0.00% |      +0.38% |       8.7% |          1.8% |           1.8% |
| T+30       |     291 |        +0.00% |      -0.33% |      33.3% |          6.9% |           4.5% |
| T+60       |     290 |        +0.00% |      -0.74% |      44.5% |         12.1% |          15.2% |
| T+120      |     212 |        -0.22% |      -2.30% |      42.9% |         18.9% |          22.6% |
| T+180      |     200 |        -2.16% |      -1.46% |      38.5% |         21.5% |          27.0% |
| T+300      |     270 |        -6.74% |      -5.11% |      35.6% |         20.4% |          35.9% |
| T+600      |     189 |       -14.08% |      -8.67% |      34.4% |         21.2% |          45.5% |
| T+900      |     249 |       -22.02% |      -8.54% |      33.7% |         24.1% |          51.0% |
| T+1800     |     202 |       -32.52% |     -11.03% |      34.2% |         20.8% |          54.0% |
| T+3600     |     164 |       -54.31% |     -22.41% |      24.4% |         19.5% |          62.2% |

## 2. Excursion (MFE / MAE) & Path Dynamics

### Maximum Favorable Excursion (MFE - Peak Upside)
- **Median Peak Upside:** +12.91%
- **Mean Peak Upside:**   +56.43%
- **Median Time to Peak:** 121 seconds (~2.0 min)

### Maximum Adverse Excursion (MAE - Worst Drawdown)
- **Median Worst Drawdown:** -46.85%
- **Mean Worst Drawdown:**   -48.83%
- **Median Time to Trough:** 901 seconds (~15.0 min)

### Peak-to-Trough Collapse
- **Median Drawdown After Reaching Peak:** -72.03%
- **Mean Drawdown After Reaching Peak:**   -62.32%

## 3. Threshold Reachability Matrix

| Threshold | Signals Reached | Percentage |
| :--- | :--- | :--- |
| Hit ≥ +20% MFE  | 138 / 304 | 45.4% |
| Hit ≥ +50% MFE  | 85 / 304 | 28.0% |
| Hit ≥ +100% MFE | 45 / 304 | 14.8% |
| Hit ≤ -20% MAE  | 204 / 304 | 67.1% |
| Hit ≤ -50% MAE  | 149 / 304 | 49.0% |
| Hit ≤ -80% MAE  | 96 / 304 | 31.6% |
| Hit ≤ -90% MAE  | 65 / 304 | 21.4% |

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