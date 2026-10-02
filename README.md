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

## Analytics

Meco comes with an analytics script that cross-references initial market snapshots against post-call checkpoint observations (e.g., `T+900s`). It calculates median price returns, median liquidity decay, and initial feature differences between winners and losers.

Run the analysis script via:
```bash
python -m scripts.analyze_signals
```

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
