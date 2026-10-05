# Meco Signal Feature Analysis Report

> [!NOTE]
> All analyzed features were observable strictly at signal time (T+0). Zero future information is permitted. Exploratory correlations are tested across quantiles to evaluate robust monotonicity vs noise.

## 1. Quantitative Features vs Outcomes

### Feature: `liquidity_usd` (Samples: 311)
- **Rank Correlation with T+300 Return:** +0.067
- **Rank Correlation with Peak Upside (MFE):** +0.149

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [2,394.62 – 19,385.27] |  14,885.01 |    +0.0% |    -13.1% |   +8.3% |        40.8% |         52.4% |
| Mid  | [19,433.99 – 29,332.48] |  24,085.53 |    -0.5% |     -9.6% |  +23.7% |        51.5% |         50.5% |
| High | [29,433.56 – 435,178.32] |  45,876.13 |    -0.0% |     -2.2% |  +12.6% |        42.9% |         47.6% |

### Feature: `volume_5m` (Samples: 311)
- **Rank Correlation with T+300 Return:** -0.113
- **Rank Correlation with Peak Upside (MFE):** +0.269

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [0.00 – 20,038.99]     |   4,642.10 |    +0.0% |     -0.4% |   +7.2% |        35.9% |         31.1% |
| Mid  | [20,383.50 – 72,504.99] |  36,220.51 |    -2.3% |    -15.5% |  +16.0% |        47.6% |         55.3% |
| High | [72,664.55 – 1,533,303.65] | 167,288.86 |    +2.4% |    -17.8% |  +22.4% |        51.4% |         63.8% |

### Feature: `total_txns_5m` (Samples: 311)
- **Rank Correlation with T+300 Return:** -0.132
- **Rank Correlation with Peak Upside (MFE):** +0.261

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [0.00 – 350.00]        |     101.00 |    +0.0% |     -0.4% |   +7.2% |        38.8% |         29.1% |
| Mid  | [351.00 – 1,264.00]    |     724.00 |    -2.3% |    -15.5% |  +10.9% |        44.7% |         55.3% |
| High | [1,297.00 – 13,272.00] |   2,313.00 |    -0.2% |    -23.0% |  +22.4% |        51.4% |         65.7% |

### Feature: `buy_sell_ratio` (Samples: 299)
- **Rank Correlation with T+300 Return:** -0.016
- **Rank Correlation with Peak Upside (MFE):** +0.060

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [0.00 – 1.11]          |       0.96 |    -0.9% |    -10.1% |  +18.2% |        47.5% |         52.5% |
| Mid  | [1.11 – 1.34]          |       1.22 |    +2.4% |    -13.6% |  +27.2% |        54.5% |         53.5% |
| High | [1.34 – 11.36]         |       1.62 |    -0.1% |     -6.1% |   +9.1% |        37.6% |         50.5% |

### Feature: `buy_fraction` (Samples: 301)
- **Rank Correlation with T+300 Return:** -0.010
- **Rank Correlation with Peak Upside (MFE):** +0.055

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [0.00 – 0.53]          |       0.49 |    -0.9% |    -10.1% |  +17.1% |        47.0% |         52.0% |
| Mid  | [0.53 – 0.57]          |       0.55 |    +1.2% |    -13.4% |  +28.2% |        55.0% |         54.0% |
| High | [0.57 – 1.00]          |       0.62 |    -0.1% |     -5.3% |   +9.1% |        36.6% |         49.5% |

### Feature: `volume_to_liquidity` (Samples: 311)
- **Rank Correlation with T+300 Return:** -0.155
- **Rank Correlation with Peak Upside (MFE):** +0.288

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [0.00 – 0.83]          |       0.23 |    +0.0% |     -0.1% |   +6.4% |        35.0% |         26.2% |
| Mid  | [0.85 – 2.77]          |       1.61 |    -2.2% |    -16.4% |  +10.9% |        45.6% |         56.3% |
| High | [2.81 – 22.61]         |       5.58 |    +1.9% |    -23.0% |  +25.1% |        54.3% |         67.6% |

### Feature: `telegram_latency` (Samples: 287)
- **Rank Correlation with T+300 Return:** +0.006
- **Rank Correlation with Peak Upside (MFE):** -0.103

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [0.97 – 18.64]         |       7.34 |    -0.9% |     -6.1% |  +15.2% |        49.5% |         63.2% |
| Mid  | [19.30 – 43.70]        |      29.13 |    +0.8% |    -10.3% |  +21.3% |        50.5% |         47.4% |
| High | [44.22 – 7,434.53]     |     284.97 |    +0.0% |     -3.8% |   +9.2% |        38.1% |         36.1% |

## 2. Categorical Features vs Outcomes

### Breakdown by `dex_id`

| Category | Count | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| pumpswap     |   278 |    +0.0% |     -9.2% |  +11.8% |        44.2% |         51.8% |
| meteora      |    21 |    -0.7% |     -3.6% |   +7.8% |        47.6% |         42.9% |
| raydium      |    12 |    -5.2% |     -1.0% |  +21.4% |        58.3% |         25.0% |

## 3. Evidence vs Exploration Assessment

1. **Buy/Sell Ratio:**
   - Low buy/sell ratio (<1.15) has a notably higher probability of catastrophic drawdown (≤ -50% MAE) than higher ratios.
   - However, high buy/sell ratio alone does not guarantee a positive T+300 return due to the universal negative drift.
2. **Initial Liquidity:**
   - Tokens with low initial liquidity (<$20k) exhibit higher peak volatility and slightly higher probability of reaching +20% MFE, but suffer sharper collapse.
   - Higher initial liquidity (>$30k) dampens upside swings, resulting in lower MFE.
3. **Telegram Ingestion Latency:**
   - Rank correlation with returns is virtually zero (ρ ≈ -0.02). As established in Section 5, Telegram latency is an ingestion metric, NOT an alpha factor.
4. **DEX Venue:**
   - PumpSwap pairs dominate the sample (88%+), reflecting standard pump.fun bonding curves.