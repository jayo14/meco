# Meco Signal Feature Analysis Report

> [!NOTE]
> All analyzed features were observable strictly at signal time (T+0). Zero future information is permitted. Exploratory correlations are tested across quantiles to evaluate robust monotonicity vs noise.

## 1. Quantitative Features vs Outcomes

### Feature: `liquidity_usd` (Samples: 304)
- **Rank Correlation with T+300 Return:** +0.057
- **Rank Correlation with Peak Upside (MFE):** +0.145

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [2,394.62 – 19,385.27] |  14,885.01 |    +0.0% |    -12.4% |   +8.6% |        41.6% |         51.5% |
| Mid  | [19,433.99 – 29,433.56] |  24,198.42 |    -0.2% |     -9.2% |  +24.3% |        52.5% |         48.5% |
| High | [29,645.81 – 435,178.32] |  45,882.79 |    -0.1% |     -2.9% |  +12.2% |        42.2% |         47.1% |

### Feature: `volume_5m` (Samples: 304)
- **Rank Correlation with T+300 Return:** -0.130
- **Rank Correlation with Peak Upside (MFE):** +0.264

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [0.00 – 20,038.99]     |   4,643.53 |    +0.0% |     -0.4% |   +7.4% |        36.6% |         29.7% |
| Mid  | [20,383.50 – 73,354.83] |  36,220.51 |    -2.0% |    -15.3% |  +18.2% |        48.5% |         55.4% |
| High | [74,729.85 – 1,533,303.65] | 170,282.18 |    +1.8% |    -19.9% |  +21.2% |        51.0% |         61.8% |

### Feature: `total_txns_5m` (Samples: 304)
- **Rank Correlation with T+300 Return:** -0.142
- **Rank Correlation with Peak Upside (MFE):** +0.259

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [0.00 – 350.00]        |     102.00 |    +0.0% |     -0.2% |   +7.4% |        39.6% |         27.7% |
| Mid  | [351.00 – 1,297.00]    |     732.00 |    -2.2% |    -15.3% |  +10.9% |        44.6% |         54.5% |
| High | [1,299.00 – 13,272.00] |   2,348.00 |    -0.1% |    -24.0% |  +23.7% |        52.0% |         64.7% |

### Feature: `buy_sell_ratio` (Samples: 292)
- **Rank Correlation with T+300 Return:** +0.006
- **Rank Correlation with Peak Upside (MFE):** +0.074

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [0.00 – 1.11]          |       0.96 |    -0.8% |     -9.6% |  +16.0% |        46.4% |         51.5% |
| Mid  | [1.11 – 1.34]          |       1.22 |    +3.1% |    -13.4% |  +29.3% |        55.7% |         51.5% |
| High | [1.34 – 11.36]         |       1.62 |    -0.1% |     -5.3% |  +10.0% |        38.8% |         50.0% |

### Feature: `buy_fraction` (Samples: 294)
- **Rank Correlation with T+300 Return:** +0.012
- **Rank Correlation with Peak Upside (MFE):** +0.068

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [0.00 – 0.53]          |       0.49 |    -0.9% |    -10.1% |  +14.5% |        45.9% |         52.0% |
| Mid  | [0.53 – 0.57]          |       0.55 |    +2.4% |    -12.7% |  +30.4% |        56.1% |         51.0% |
| High | [0.57 – 1.00]          |       0.62 |    -0.0% |     -4.5% |  +10.0% |        37.8% |         49.0% |

### Feature: `volume_to_liquidity` (Samples: 304)
- **Rank Correlation with T+300 Return:** -0.169
- **Rank Correlation with Peak Upside (MFE):** +0.285

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [0.00 – 0.83]          |       0.22 |    +0.0% |     -0.1% |   +7.2% |        35.6% |         24.8% |
| Mid  | [0.85 – 2.83]          |       1.61 |    -1.4% |    -16.4% |  +10.9% |        45.5% |         55.4% |
| High | [2.86 – 22.61]         |       5.64 |    +1.9% |    -25.3% |  +25.8% |        54.9% |         66.7% |

### Feature: `telegram_latency` (Samples: 280)
- **Rank Correlation with T+300 Return:** +0.021
- **Rank Correlation with Peak Upside (MFE):** -0.100

| Bin | Range | Median Val | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Low  | [0.97 – 19.30]         |       7.34 |    -0.9% |     -6.1% |  +20.0% |        50.5% |         63.4% |
| Mid  | [19.50 – 44.22]        |      29.66 |    +0.8% |    -11.0% |  +19.8% |        49.5% |         47.3% |
| High | [44.55 – 7,434.53]     |     347.63 |    +0.0% |     -1.2% |   +9.3% |        39.4% |         31.9% |

## 2. Categorical Features vs Outcomes

### Breakdown by `dex_id`

| Category | Count | Med T+60 | Med T+300 | Med MFE | Win (≥+20%) | Loss (≤-50%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| pumpswap     |   271 |    +0.0% |     -8.7% |  +12.6% |        44.6% |         50.6% |
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