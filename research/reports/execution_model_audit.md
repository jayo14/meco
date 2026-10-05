# Meco Execution Model Audit & Sensitivity Analysis

## 1. Parameter Classification & Methodology

Every variable in Meco's execution simulator is formally audited and classified under scientific reporting standards:

| Parameter | Simulator Default | Classification | Bias Direction | Technical Basis |
| :--- | :--- | :--- | :--- | :--- |
| `initial_price` | `signal.price_usd` | **OBSERVED** | `neutral` | Captured via DexScreener API at signal arrival. |
| `initial_liquidity` | `signal.liquidity_usd` | **OBSERVED** | `neutral` | Pool liquidity reported by DexScreener at signal time. |
| `position_size_usd` | `100.0` | **ASSUMED** | `neutral` | Standard nominal trade size per alert. |
| `base_slippage_pct` | `1.5` | **ASSUMED** | `aggressive` | 1.5% fixed allowance. Favorable to trader compared to Telegram's 15% recommended slippage. |
| `price_impact_factor` | `2.0` | **DERIVED** | `neutral` | Derived from constant product AMM mechanics: impact ≈ 2 * (size / liquidity). |
| `dex_fee_pct` | `0.25` | **ESTIMATED** | `aggressive` | 0.25% per swap (Raydium standard). Favorable to trader compared to Pump.fun's 1.0%. |
| `solana_tx_fee_usd` | `0.01` | **ESTIMATED** | `neutral` | Base lamports + median priority fee for competitive block inclusion. |
| `min_pool_liquidity_usd` | `5000.0` | **ASSUMED** | `neutral` | Protects against executing into dead or zero-liquidity pools. |
| `exit_price` | `observed checkpoint price` | **OBSERVED** | `neutral` | Captured at discrete intervals; intra-interval wicks are UNKNOWN. |
| `intra_interval_wicks` | `untracked` | **UNKNOWN** | `aggressive` | Discrete sampling understates intra-checkpoint stop-out spikes, flattering theoretical returns. |

### Interpretation of Parameter Biases:
- **Base Slippage (1.5%):** Classified as **AGGRESSIVE** (favorable to trader). In real meme-coin trading, the Telegram channel recommends 15% slippage due to high block-level volatility.
- **Price Impact:** Derived from constant-product AMM mechanics ($2 \times \frac{\text{size}}{\text{liquidity}}$). Accurately penalizes small pools (<$10k).
- **DEX Fees (0.25%):** Classified as **AGGRESSIVE** (favorable to trader). Pump.fun charges 1.0%, Raydium charges 0.25%. Assuming 0.25% flat gives trading the benefit of the lowest possible fee rate.
- **Intra-Checkpoint Wicks:** Classified as **UNKNOWN / AGGRESSIVE**. Discrete sampling (T+10s, 30s, 60s...) fails to capture microsecond stop-outs, meaning theoretical backtests actually overestimate survival rates.

---

## 2. Friction Sensitivity Grid Analysis

To verify whether the negative research conclusion is an artifact of fee overestimation, we evaluate performance across four friction tiers:
- **Zero Friction (Theoretical Limit):** 0% slippage, 0 price impact, $0 fees.
- **Low Friction (Institutional Limit):** 0.5% slippage, 1.0 impact, 0.15% DEX fee, $0.005 gas.
- **Baseline Friction:** 1.5% slippage, 2.0 impact, 0.25% DEX fee, $0.01 gas.
- **High Friction (Retail Meme Reality):** 3.0% slippage, 3.0 impact, 1.0% DEX fee, $0.025 gas.

| Friction Tier | Trades | Win Rate % | Mean Gross Ret | Mean Net Ret | Total PnL ($100 Size) | Expectancy / Trade |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **zero_friction** |    278 |      41.4% |         -2.68% |       -2.68% | $             -745.15 | $            -2.68 |
| **low_friction** |    278 |      36.0% |         -2.63% |       -4.43% | $            -1316.41 | $            -4.74 |
| **baseline_friction** |    278 |      33.5% |         -2.47% |       -6.96% | $            -2078.63 | $            -7.48 |
| **high_friction** |    278 |      27.0% |         -2.52% |      -10.51% | $            -3492.47 | $           -12.56 |

---

## 3. Robustness Verdict

1. **Is the Negative Conclusion Fragile?**
   - **NO.** Even under **Zero Friction** (theoretical zero slippage, zero impact, zero fees), trading the raw Telegram signal fails to generate positive net expectancy across the full dataset.
   - The median price drift after 2 minutes is systematically negative (-6.7% at 5m, -22% at 15m).
2. **Impact of Higher Friction:**
   - Under realistic retail conditions (High Friction), total drawdown accelerates severely, confirming that live trading on this channel would rapidly deplete capital.
3. **Conclusion:**
   - The lack of an executable trading edge is a property of the underlying signal timing, not an artifact of execution modeling.