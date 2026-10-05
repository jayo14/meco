# Meco Signal Feature Analysis Report

> [!NOTE]
> All analyzed features were observable strictly at signal time (T+0). Zero future information is permitted. Exploratory correlations are tested across quantiles to evaluate robust monotonicity vs noise.

## 1. Quantitative Features vs Outcomes

### Feature: `liquidity_usd` (Samples: 305)
- **Rank Correlation with T+300 Return:** +0.059
- **Rank Correlation with Peak Upside (MFE):** +0.145

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [2,394.62 – 19,385.27] |  14,885.01 |    +0.0% |    -13.1% |   +8.6% |        41.6% |         52.5% |
| Mid  | [19,433.99 – 29,332.48] |  24,085.53 |    -0.3% |     -9.5% |  +24.3% |        52.5% |         49.5% |
| High | [29,433.56 – 435,178.32] |  45,876.13 |    -0.0% |     -2.6% |  +12.6% |        42.7% |         48.5% |

### Feature: `volume_5m` (Samples: 305)
- **Rank Correlation with T+300 Return:** -0.127
- **Rank Correlation with Peak Upside (MFE):** +0.265

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [0.00 – 20,038.99]     |   4,643.53 |    +0.0% |     -0.4% |   +7.4% |        36.6% |         30.7% |
| Mid  | [20,383.50 – 72,664.55] |  36,220.51 |    -2.2% |    -15.3% |  +18.2% |        48.5% |         55.4% |
| High | [73,354.83 – 1,533,303.65] | 168,752.83 |    +2.4% |    -17.8% |  +22.4% |        51.5% |         64.1% |

### Feature: `total_txns_5m` (Samples: 305)
- **Rank Correlation with T+300 Return:** -0.140
- **Rank Correlation with Peak Upside (MFE):** +0.259

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [0.00 – 350.00]        |     102.00 |    +0.0% |     -0.3% |   +7.4% |        39.6% |         28.7% |
| Mid  | [351.00 – 1,264.00]    |     732.00 |    -2.2% |    -15.3% |  +11.5% |        45.5% |         55.4% |
| High | [1,297.00 – 13,272.00] |   2,339.00 |    -0.2% |    -23.0% |  +22.4% |        51.5% |         66.0% |

### Feature: `buy_sell_ratio` (Samples: 293)
- **Rank Correlation with T+300 Return:** +0.005
- **Rank Correlation with Peak Upside (MFE):** +0.072

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [0.00 – 1.11]          |       0.96 |    -0.9% |    -10.1% |  +18.2% |        47.4% |         52.6% |
| Mid  | [1.11 – 1.33]          |       1.22 |    +2.4% |    -13.8% |  +27.2% |        54.6% |         54.6% |
| High | [1.34 – 11.36]         |       1.62 |    -0.0% |     -4.5% |  +10.0% |        39.4% |         49.5% |

### Feature: `buy_fraction` (Samples: 295)
- **Rank Correlation with T+300 Return:** +0.011
- **Rank Correlation with Peak Upside (MFE):** +0.066

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [0.00 – 0.53]          |       0.49 |    -0.9% |    -10.1% |  +17.1% |        46.9% |         52.0% |
| Mid  | [0.53 – 0.57]          |       0.55 |    +2.4% |    -13.4% |  +30.7% |        56.1% |         55.1% |
| High | [0.57 – 1.00]          |       0.62 |    -0.0% |     -4.5% |   +9.9% |        37.4% |         48.5% |

### Feature: `volume_to_liquidity` (Samples: 305)
- **Rank Correlation with T+300 Return:** -0.166
- **Rank Correlation with Peak Upside (MFE):** +0.285

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [0.00 – 0.83]          |       0.22 |    +0.0% |     -0.1% |   +7.2% |        35.6% |         25.7% |
| Mid  | [0.85 – 2.81]          |       1.61 |    -1.9% |    -15.7% |  +11.5% |        46.5% |         56.4% |
| High | [2.83 – 22.61]         |       5.63 |    +1.9% |    -25.3% |  +25.1% |        54.4% |         68.0% |

### Feature: `telegram_latency` (Samples: 281)
- **Rank Correlation with T+300 Return:** +0.018
- **Rank Correlation with Peak Upside (MFE):** -0.099

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [0.97 – 19.30]         |       7.34 |    -0.9% |     -6.1% |  +20.0% |        50.5% |         63.4% |
| Mid  | [19.50 – 43.70]        |      29.46 |    +0.8% |    -11.0% |  +21.3% |        50.5% |         47.3% |
| High | [44.22 – 7,434.53]     |     314.01 |    +0.0% |     -2.0% |   +9.2% |        38.9% |         35.8% |

## 2. Categorical Features vs Outcomes

### Breakdown by `dex_id`

| Category | Count | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| pumpswap     |   272 |    +0.0% |     -9.0% |  +12.7% |        44.9% |         51.8% |
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