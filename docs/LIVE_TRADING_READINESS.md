# Meco Live Trading Readiness Assessment & Wallet Architecture Specification

This document provides a quantitative, evidence-based assessment of whether Meco is ready to progress from autonomous paper trading to controlled live trading, along with the formal architecture specification for an isolated signing wallet.

> [!CAUTION]
> **SAFETY DECLARATION:**
> - Live trading is **NOT ENABLED**.
> - No private keys or seed phrases exist in this repository, environment variables, or databases.
> - No transactions are signed or broadcast to any blockchain network.
> - Real capital is never moved.
> - Any future live pilot requires explicit written sign-off from a human operator.

---

## 1. Evidence Review

A rigorous audit of all historical data, simulated executions, and operational telemetry reveals the following empirical realities:

### 1.1 Trading Duration & Sample Size
- **Historical Analysis Window:** 4 days (October 2 to October 5, 2026), capturing 393 signals (391 unique token mints), with 311 clean signals evaluated.
- **Completed Paper Trades:** 284 simulated trades evaluated across 4 core strategy hypotheses (`H0` Naive Follow, `H1` Anti-Climax, `H2` Buy-Pressure Momentum, `H3` Trailing Stop Momentum Rider).
- **Production Pipeline State:** The multi-source independent token discovery engine (PumpPortal WebSocket, Solana RPC poller), multi-agent investigation system, and PostgreSQL connection pooling were hardened in Phases 4–9. Continuous 24/7 VPS forward data accumulation on independent sources is in its early stages.

### 1.2 Net Returns After Realistic Execution Costs
Under standard scientific reporting, **gross returns are completely rejected as evidence of profitability**. After accounting for realistic execution friction (1.5% base slippage, constant-product AMM price impact $2 \times \frac{\text{size}}{\text{liquidity}}$, 0.50% roundtrip DEX fees, and priority gas fees):

| Strategy Hypothesis | Evaluated Condition | In-Sample Train Win% | In-Sample Train Net PnL | Out-of-Sample Test Win% | Out-of-Sample Test Net PnL | Scientific Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **H0: Baseline Naive Follow** | Any signal with price > 0, liq >= $5k | 28.4% | -$1,752.00 | 32.2% | -$586.67 | **FALSIFIED (Negative EV)** |
| **H1: Anti-Climax Filter** | volume_5m <= $35k, vol/liq <= 1.2 | 33.3% | -$391.87 | 27.0% | -$260.39 | **FALSIFIED (Negative EV)** |
| **H2: Buy-Pressure Momentum** | buy_sell_ratio >= 1.30, liq >= $15k | 28.9% | -$724.30 | 34.6% | -$89.59 | **FALSIFIED (Negative EV)** |
| **H3: Trailing Stop Momentum** | liq >= $15k, trail 10% from peak | 24.0% | -$1,850.04 | 32.4% | -$503.68 | **FALSIFIED (Negative EV)** |

- **Net Expectancy:** Systematically negative across all hypotheses, ranging between **-$2.68 and -$12.66 per $100 trade**.
- **Profit Factor:** **< 0.70** across all strategies (sub-1.0 denotes gross trading losses exceed gross gains).
- **Maximum Drawdown:** Severe, exceeding **-40% to -50%** across static follow and trailing stop approaches.

### 1.3 Performance by Token Age and Market Dynamics
- **Systematic Delay of Public Signals:** On-chain pool creation timestamp analysis of 220 tokens revealed a **median pool age of 15.8 minutes (946 seconds)** when the Telegram call was broadcast. **0.0%** of tokens were under 2 minutes old.
- **Extreme Reversal Speed:** Median time to reach peak price (Maximum Favourable Excursion, MFE) was **121 seconds** (+12.7% median upside), followed immediately by a **median post-peak collapse of -72.0%**.
- **Catastrophic Collapse Rate:** **32.8%** of called tokens experienced a drawdown exceeding -80%.
- **Liquidity Anomaly Events:** Signal #103 experienced an instant -99.994% liquidity drainage ($345.8M pool evaporated to $20.8K within 15 minutes).

---

## 2. Statistical Confidence & Risk Assessment

The available dataset is **statistically insufficient** to support live trading deployment due to several fundamental biases and constraints:

1. **Small Sample Size:** 311 clean signals collected over 4 calendar days represent a single micro-regime. A statistically robust sample requires at least 1,000+ forward events across varying volatility environments.
2. **Adverse Selection Bias:** Public free-tier Telegram channels function primarily as delayed broadcasts or exit liquidity for early snipers. Trading exclusively on these alerts guarantees entry after primary accumulation.
3. **Friction Sensitivity:** As audited in [`research/reports/execution_model_audit.md`](file:///home/codegallantx/moi/meco/research/reports/execution_model_audit.md), even under theoretical zero-friction conditions (0% slippage, $0 fees), the raw channel has negative drift (-2.78% mean return). Realistic retail friction deepens the drag to -10.61% per trade.
4. **Survivorship Bias:** Evaluating only tokens chosen by alert channels ignores the baseline death rate of all Solana meme tokens created on-chain.

---

## 3. Strategy Stability & Governance

Meco's software architecture exhibits high stability and governance rigor:
- **Versioned Strategy Registry:** All strategies (`momentum_breakout`, `liquidity_surge`) have immutable semantic versions registered in [`app/trading/strategy.py`](file:///home/codegallantx/moi/meco/app/trading/strategy.py).
- **Experiment Tracking:** Machine learning model artifacts and point-in-time dataset hashes are tracked via `ExperimentRegistry` with strict lock controls preventing runtime self-modification.
- **Rollback Capability:** The `ChampionChallengerGateway` enforces automated statistical comparison and rollback to the active baseline if a challenger deteriorates.
- **Deterministic Hard Risk Controls:** The [`PreTradeRiskGateway`](file:///home/codegallantx/moi/meco/app/trading/risk_gateway.py) evaluates non-negotiable safety rules (max position size, portfolio exposure cap, daily loss limit, max drawdown circuit breaker) and cannot be overridden by LLMs or decision engine scores.
- **Emergency Stop:** A latching kill switch is operational via API (`/api/controls/emergency-stop`) and automatically activated upon daily loss breach.

---

## 4. Execution Feasibility: Paper vs. Live Reality

Significant divergences exist between simulated paper assumptions and live Solana mainnet conditions:

| Execution Dimension | Paper Simulation Model | Live Mainnet Reality | Impact on Real Trading |
| :--- | :--- | :--- | :--- |
| **Quote Availability** | Instantaneous via DexScreener/RPC | 400ms block slots, mempool race | Executed price often 5-15% worse than quote |
| **Price Impact** | Constant-product approximation ($2 \times \frac{\text{size}}{\text{liq}}$) | Micro-pool depth changes between slot arrival | Sizable slippage spikes on small pools (<$20k) |
| **Priority Fees** | Static $0.01 allowance (10k microlamports) | Dynamic spikes up to 500k+ microlamports | Severe fee drag during Solana network congestion |
| **Transaction Drops** | Simulated 100% inclusion if liquidity valid | 5-25% drop rate during heavy mempool congestion | Unhedged exposure, missed stop-losses, timeouts |
| **Exit Feasibility** | Assumed executable at mark price | Honeypots, blacklists, LP drains | High probability of total loss on rug pulls |

---

## 5. Dedicated Meco Wallet Architecture Proposal

To ensure complete safety when live trading is eventually evaluated, a dedicated wallet architecture is specified in [`app/trading/wallet_spec.py`](file:///home/codegallantx/moi/meco/app/trading/wallet_spec.py).

```
┌────────────────────────────────────────────────────────┐
│                   Meco Core Daemon                     │
│        (Proposal Generator & Risk Gateway)             │
└──────────────────────────┬─────────────────────────────┘
                           │ 1. Form Trade Intent
                           ▼
┌────────────────────────────────────────────────────────┐
│             TransactionPolicyValidator                 │
│  - Max 0.5 SOL per swap                                │
│  - Max 2.0 SOL total exposure                          │
│  - Daily 1.0 SOL loss circuit breaker                  │
│  - Program ID Whitelist (Raydium, Pump.fun, System)    │
│  - Zero authority mutations / Zero external transfers  │
└──────────────────────────┬─────────────────────────────┘
                           │ 2. Validated Payload Only
                           ▼
┌────────────────────────────────────────────────────────┐
│            Isolated Signer Service / HSM               │
│  - Runs as restricted non-root user `meco-signer`      │
│  - Local Unix domain socket IPC                        │
│  - Private key NEVER enters Python memory or LLM space │
│  - Independent policy double-check before signing      │
└──────────────────────────┬─────────────────────────────┘
                           │ 3. Signed Raw Wire Bytes
                           ▼
┌────────────────────────────────────────────────────────┐
│                 Solana RPC Cluster                     │
└────────────────────────────────────────────────────────┘
```

### 5.1 Core Architectural Principles
1. **Air-Gapped Signing Boundary:** Private keys are strictly quarantined inside a dedicated local microservice (`meco-signer`) or hardware module. The main Python platform, LLMs, and agent orchestrators **never** see or handle raw private keys.
2. **Dedicated Hot Wallet:** Never use a personal, treasury, or high-value wallet. The Meco wallet is a standalone disposable address initialized with small, strictly capped operating capital (maximum 2.0 SOL).
3. **Strict Whitelist of Program IDs:**
   - Allowed: Raydium AMM V4, Raydium CPMM, Pump.fun, Jupiter V6, Token Program, Associated Token Program, System Program.
   - Forbidden: Any transfer to personal accounts, arbitrary program invocations, staking, or contract upgrades.
4. **Authority Mutation Prohibition:** Any transaction attempting `SetAuthority`, `Assign`, or token mint/freeze delegate changes is rejected.
5. **Hardware & OS Isolation:** Signer process executes under dedicated user credentials with read-only access to `/etc/meco/keys` (`chmod 600`).

---

## 6. Live Trading Readiness Verdict

### Formal Scientific Verdict:
# **READY FOR EXTENDED PAPER TRADING**
*(Live Real-Money Trading is **STRICTLY PROHIBITED** at this stage)*

### Rationale:
1. **Negative Expected Value on Existing Signals:** Every tested strategy on the public Telegram signal source generates net financial losses after realistic transaction costs. Deploying live capital today would result in systematic drawdown.
2. **Independent Discovery Verification Required:** The newly built independent token discovery engine (PumpPortal WebSocket, Solana RPC poller) addresses the 15.8-minute late-arrival problem of public Telegram calls. However, this pipeline requires forward paper-trading validation to confirm that early detection creates positive net expectancy.
3. **Absence of Operator Approval:** Live trading strictly requires deliberate, written human sign-off.

---

## 7. Measurable Conditions Required for Live Pilot Approval

Before any controlled live trading pilot (even with micro-capital of 0.1 SOL) can be proposed to the human operator, all of the following measurable criteria must be satisfied simultaneously:

1. **Continuous Forward Execution:** At least **30 to 60 consecutive days** of 24/7 continuous paper trading on the production Linux daemon without crashes or unhandled task dropouts.
2. **Statistical Sample Size:** A minimum of **500 completed simulated trades** across at least **150 unique tokens** generated via independent on-chain discovery.
3. **Statistically Significant Net Expectancy:** At least one versioned strategy must demonstrate a positive net expectancy of **>= +$0.50 per $100 trade** after full friction modeling (3.0% slippage + price impact + 0.50% roundtrip DEX fees + priority fees) with a t-statistic >= 2.0 (p-value < 0.05).
4. **Out-of-Sample Stability:** The winning strategy must maintain an out-of-sample Sharpe Ratio **>= 1.20** and Profit Factor **>= 1.30** across at least two distinct Solana market regimes.
5. **Drawdown Boundary:** Forward simulated maximum portfolio drawdown must remain strictly below **15.0%**.
6. **Isolated Signer Implementation:** The isolated `meco-signer` daemon must be implemented and verified on Solana Devnet with full audit logging.
7. **Explicit Human Sign-Off:** The human operator must explicitly grant written approval to activate live pilot mode.
