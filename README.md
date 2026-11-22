# Meco 📡

Meco is a high-resolution, data-driven Solana meme coin signal ingestion and analysis engine. It listens to specific Telegram channels, extracts token contract addresses in real-time, validates them on-chain, and tracks their exact market price and liquidity trajectories over scheduled checkpoints via DexScreener.

Meco is built to answer one question: **"What actually happens to a token's price and liquidity *after* it is called?"**

## Features

- **Durable Ingestion Pipeline:** Uses Telethon to instantly capture messages and persist them to a PostgreSQL database, tracking exact Telegram network latency.
- **On-Chain Validation:** Queries Solana RPC with exponential backoff to verify the token is a legitimate SPL mint before proceeding.
- **High-Resolution Market Tracking:** Immediately queries DexScreener for the token's market status, storing all candidate pairs to avoid survivorship bias.
- **Scheduled Observations:** Spawns asynchronous tasks to record the token's price, liquidity, and volume at precise intervals: `T+10s, T+30s, T+60s, T+2m, T+3m, T+5m, T+10m, T+15m, T+30m, T+1h, T+6h, T+24h`.
- **Idempotent Persistence:** Database architecture uses constraint-based duplication protection so that scheduled observations can never crash or double-record data.
- **Read-Only Analytics:** Includes built-in analytical scripts to isolate cohorts (Winners vs. Losers), calculate median latency, compute median drawdowns, and investigate initial market features (liquidity, volume, buy/sell ratios) without touching trading logic.

## Architecture & Tech Stack

- **Python 3.11+**
- **Telethon** (Telegram MTProto client)
- **SQLAlchemy & asyncpg** (Asynchronous PostgreSQL interaction)
- **Alembic** (Database schema migrations)
- **Solana.py / Solders** (On-chain validation)
- **httpx** (Asynchronous DexScreener requests)
- **Docker & Docker Compose** (Containerized deployment)

---

## Setup & Installation

### Option 1: Docker Deployment (Recommended)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/meco.git
   cd meco
   ```

2. **Configure your environment:**
   Copy `.env.example` to `.env` and fill in your credentials (Telegram API ID/Hash, Solana RPC URL, etc.).
   ```bash
   cp .env.example .env
   ```

3. **Start the stack:**
   ```bash
   docker compose up -d --build
   ```
   *Note: On first run, check the logs (`docker compose logs -f app`) as Telethon will prompt for your Telegram phone number and login code.*

### Option 2: Local Development

1. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up PostgreSQL:**
   Ensure PostgreSQL is running locally and update your `.env` with the correct connection string:
   ```env
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/meco
   ```

4. **Initialize database schema & migrations:**
   ```bash
   python -m app.database.init_db
   alembic upgrade head
   ```

5. **Run the listener:**
   ```bash
   python -m app.telegram.client
   ```

---

## Research & Analytics Suite

Meco includes a reproducible, read-only quantitative research suite designed to audit data quality, track path-dependent excursion metrics (MFE/MAE), test signal-time features with zero lookahead bias, validate paper-trading hypotheses across chronological splits, audit execution model friction, and investigate on-chain pre-signal dynamics:

- **Run entire research pipeline and generate full report package:**
  ```bash
  python -m scripts.research
  ```
- **Audit historical signal and observation coverage:**
  ```bash
  python -m scripts.audit_dataset
  ```
- **Analyze path-dependent returns and MFE/MAE excursions:**
  ```bash
  python -m scripts.analyze_outcomes
  ```
- **Analyze signal-time features vs. subsequent returns:**
  ```bash
  python -m scripts.analyze_features
  ```
- **Scan for anomalies, liquidity shifts, and delay artifacts:**
  ```bash
  python -m scripts.detect_anomalies
  ```
- **Audit execution model assumptions and friction sensitivity grid:**
  ```bash
  python -m scripts.audit_execution_model
  ```
- **Summarize historical baseline freeze and forward-testing cohort:**
  ```bash
  python -m scripts.baseline_cohort
  ```
- **Review practical on-chain Solana data sources:**
  ```bash
  python -m scripts.review_onchain_sources
  ```
- **Reconstruct pre-signal pool age and on-chain timing plan:**
  ```bash
  python -m scripts.analyze_presignal
  ```
- **Generate formatted Markdown and JSON reports in `research/reports/`:**
  ```bash
  python -m scripts.generate_research_report
  ```

All generated reports are stored in `research/reports/`:
- [`executive_summary.md`](file:///home/codegallantx/moi/meco/research/reports/executive_summary.md): High-level quantitative synthesis and strategic conclusions.
- [`dataset_audit.md`](file:///home/codegallantx/moi/meco/research/reports/dataset_audit.md): Data health, checkpoint completeness, and latency profile.
- [`anomaly_report.md`](file:///home/codegallantx/moi/meco/research/reports/anomaly_report.md): Excluded signals, extreme price moves, and liquidity shifts.
- [`outcome_analysis.md`](file:///home/codegallantx/moi/meco/research/reports/outcome_analysis.md): MFE, MAE, checkpoint distributions, and post-peak drawdowns.
- [`feature_analysis.md`](file:///home/codegallantx/moi/meco/research/reports/feature_analysis.md): Correlation and quintile analysis of zero-lookahead features.
- [`hypotheses_and_strategy.md`](file:///home/codegallantx/moi/meco/research/reports/hypotheses_and_strategy.md): In-sample vs out-of-sample chronological backtests.
- [`execution_model_audit.md`](file:///home/codegallantx/moi/meco/research/reports/execution_model_audit.md): Parameter classification and 4-tier friction sensitivity grid.
- [`forward_testing_baseline.md`](file:///home/codegallantx/moi/meco/research/reports/forward_testing_baseline.md): Cohort partition boundary (Signals 1-387 frozen).
- [`onchain_data_source_review.md`](file:///home/codegallantx/moi/meco/research/reports/onchain_data_source_review.md): Practical Solana RPC/data source assessment.
- [`presignal_research_plan.md`](file:///home/codegallantx/moi/meco/research/reports/presignal_research_plan.md): Pre-signal empirical findings (15.8m pool age) and prospective design.

---

## Production VPS Operation & Reliability

Meco is hardened for continuous 24/7 VPS operation on resource-constrained Linux servers. See complete operating runbooks in [`docs/OPERATIONS.md`](file:///home/codegallantx/moi/meco/docs/OPERATIONS.md).

- **Systemd Service Units:**
  - [`systemd/meco.service`](file:///home/codegallantx/moi/meco/systemd/meco.service): Unified daemon supervisor (discovery, enrichment, paper trading, and FastAPI control centre).
  - [`systemd/meco-telegram.service`](file:///home/codegallantx/moi/meco/systemd/meco-telegram.service): Isolated Telegram MTProto listener service.
  - [`systemd/meco-backup.timer`](file:///home/codegallantx/moi/meco/systemd/meco-backup.timer): Automated daily 03:00 UTC database backup with randomized jitter.
- **Automated Health Check:**
  ```bash
  python -m scripts.healthcheck
  ```
  Evaluates PostgreSQL connectivity, signal stream, observation backlogs, agent investigations, and active positions.
- **Resource Capacity Audit:**
  ```bash
  python -m scripts.resource_audit
  ```
  Measures process RSS memory footprint, system RAM headroom, database disk size, pool connection usage, and RPC latency.
- **Automated Backup & Recovery:**
  ```bash
  python -m scripts.backup_db                      # Manual compressed backup (.sql.gz)
  python -m scripts.backup_db --restore <dump>     # Verified disaster recovery restore
  ```
- **Security & Log Redaction:**
  Automated regex redaction strips database passwords, private keys, Bearer tokens, Telegram hashes, and LLM API keys before writing to logs. All control operations require token authentication.

---

## Testing

Meco uses `pytest` for unit testing. To run the test suite:
```bash
pytest
```
To check for formatting and linting:
```bash
ruff check app tests
```

---

## License
MIT License
