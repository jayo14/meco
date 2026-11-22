# Meco Production Operations & Runbook

This runbook outlines standard operating procedures, architectural topology, configuration standards, disaster recovery protocols, and failure remediation guides for maintaining the Meco autonomous intelligence platform in production on resource-constrained Linux VMs.

---

## 1. System Architecture & Process Model

Meco is designed to run predictably on a single Linux host (e.g., Ubuntu 22.04/24.04 LTS, 2-4 vCPUs, 4GB-8GB RAM). The platform decomposes into two coordinated processes:

```
                          ┌────────────────────────┐
                          │   System Supervisor    │
                          │     (app.runner)       │
                          └───────────┬────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
          ▼                           ▼                           ▼
┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐
│ Discovery Engine │        │ FastAPIDashboard │        │ Observation Task │
│ (PumpPortal WS,  │        │ Control Centre   │        │ Supervisor       │
│ Solana RPC Poller│        │ (Port 8000)      │        │ (Checkpoints)    │
└──────────────────┘        └──────────────────┘        └──────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          │                                                       │
          ▼                                                       ▼
┌──────────────────────────┐                            ┌──────────────────┐
│ Autonomous Paper Engine  │                            │ Dedicated MTProto│
│ (Risk Gateway & Sizer)   │                            │ Listener Service │
└──────────────────────────┘                            │(meco-telegram)   │
                                                        └──────────────────┘
```

1. **`meco.service` (Unified Daemon):** Runs `python -m app.runner`. Coordinates startup, runs the checkpoint recovery scanner, starts WebSocket/RPC token discovery, starts the social intelligence ingestion loop, initializes the autonomous paper trading engine, and serves the FastAPI operator dashboard.
2. **`meco-telegram.service` (Isolated MTProto Listener):** Runs `python -m app.telegram.client`. Isolated in its own process to prevent Telegram MTProto network reconnection stalls or protocol hiccups from affecting dashboard availability or paper trading executions.
3. **`meco-backup.timer` (Automated Backup Scheduler):** Systemd timer triggering `meco-backup.service` once daily at 03:00 UTC with a 15-minute randomized jitter.

---

## 2. Prerequisites & Environment Setup

### 2.1 OS Dependencies (Ubuntu / Debian)
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip postgresql postgresql-contrib libpq-dev gzip
```

### 2.2 PostgreSQL Setup
Meco requires PostgreSQL 14+ with local Unix socket or loopback (`127.0.0.1`) binding:
```bash
sudo -u postgres psql -c "CREATE USER meco WITH PASSWORD 'meco_secure_password';"
sudo -u postgres psql -c "CREATE DATABASE meco OWNER meco;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE meco TO meco;"
```

### 2.3 Application Virtualenv & Migrations
```bash
cd /opt/meco
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run migrations to head
alembic upgrade head
```

---

## 3. Configuration & Security

Configuration is managed via environment variables loaded through Pydantic Settings from `.env`. A complete, sanitized configuration template is provided in `.env.example`.

### 3.1 Essential Environment Variables
```env
# Application
APP_NAME=meco
APP_ENV=production
LOG_LEVEL=INFO

# PostgreSQL Connection & Pooling
DATABASE_URL=postgresql+asyncpg://meco:meco_secure_password@127.0.0.1:5432/meco
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=5
DB_POOL_RECYCLE=300
DB_POOL_TIMEOUT=30.0
DB_POOL_PRE_PING=true

# Operator Security & Authentication
API_AUTH_TOKEN=generate_a_random_64_char_hex_token_here
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Solana RPC & Discovery
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
ENABLE_PUMPPORTAL_DISCOVERY=true
ENABLE_SOLANA_RPC_DISCOVERY=true

# Telegram Ingestion
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=your_telegram_api_hash
TELEGRAM_SESSION_NAME=meco
```

### 3.2 Sensitive Data Redaction
Meco enforces automated regex log redaction via `app/security/redaction.py`. Sensitive credentials—including database passwords inside connection URLs, Solana private keys (base58), Bearer tokens, Telegram API hashes, and LLM API keys (`sk-...`)—are automatically replaced with `[REDACTED]` prior to hitting stdout or disk logs.

### 3.3 Operator Authentication
All sensitive dashboard endpoints under `/api/controls/*` (emergency stops, manual liquidations, strategy toggling) require authentication. Pass the configured `API_AUTH_TOKEN` via:
- HTTP Header: `Authorization: Bearer <API_AUTH_TOKEN>` or
- HTTP Header: `X-API-Key: <API_AUTH_TOKEN>`

---

## 4. Systemd Service Deployment

Production systemd unit files are provided in `systemd/`:

1. **Install unit files:**
   ```bash
   sudo cp systemd/meco.service /etc/systemd/system/
   sudo cp systemd/meco-telegram.service /etc/systemd/system/
   sudo cp systemd/meco-backup.service /etc/systemd/system/
   sudo cp systemd/meco-backup.timer /etc/systemd/system/
   ```

2. **Reload systemd daemon:**
   ```bash
   sudo systemctl daemon-reload
   ```

3. **Enable and start services:**
   ```bash
   sudo systemctl enable --now meco.service
   sudo systemctl enable --now meco-telegram.service
   sudo systemctl enable --now meco-backup.timer
   ```

4. **Verify status:**
   ```bash
   sudo systemctl status meco.service
   sudo systemctl status meco-telegram.service
   sudo systemctl list-timers meco-backup.timer
   ```

---

## 5. Operations, Health Checks & Monitoring

### 5.1 Platform Healthcheck Script
Run the built-in comprehensive healthcheck to evaluate database connectivity, canonical tokens, observation backlogs, agent investigations, and active positions:
```bash
.venv/bin/python -m scripts.healthcheck
```
Exit code `0` indicates healthy status; exit code `1` indicates critical threshold violation.

### 5.2 Real-Time Resource Capacity Audit
Audit process memory, system RAM headroom, PostgreSQL storage footprint, active database connections, table row distributions, and RPC latencies:
```bash
.venv/bin/python -m scripts.resource_audit
```
Sample output:
- **Process RSS:** ~78 MB
- **Open File Descriptors:** 42 / 1024
- **Database Size:** ~10 MB
- **DB Active Connections:** 2 / 15 pool limit
- **RPC Latency (Solana):** 80-140 ms

### 5.3 HTTP Health Endpoint
The API exposes an automated health probe:
```bash
curl -i http://localhost:8000/api/health
```

---

## 6. Backup, Verification & Disaster Recovery

### 6.1 Historical Data Policy
**Strict Policy:** Never purge historical discovery events, price observations, agent outputs, or trade proposals. Historical data is the ground truth needed for quantitative research, backtesting, and model retraining. Database storage overhead is minimal (~10-20 MB per 100k signals).

### 6.2 Manual Database Backup
To take an immediate compressed snapshot:
```bash
.venv/bin/python -m scripts.backup_db --output-dir /opt/meco/backups
```
This utility:
1. Executes `pg_dump` with transaction consistency.
2. Compresses output into `.sql.gz`.
3. Verifies archive integrity with `gzip -t`.
4. Prunes backups older than the retention period (default: 7 days).

### 6.3 Disaster Recovery Restore Procedure
To restore from a backup archive:
```bash
# 1. Stop services to prevent database write collisions
sudo systemctl stop meco.service meco-telegram.service

# 2. Restore database from archive
.venv/bin/python -m scripts.backup_db --restore /opt/meco/backups/meco_backup_20261122_030000.sql.gz --dbname meco

# 3. Verify database tables and schema
.venv/bin/alembic current

# 4. Restart services
sudo systemctl start meco.service meco-telegram.service
```

---

## 7. Failure Recovery Runbooks

### 7.1 Recovery After VM Reboot or Process Crash
When `meco.service` restarts after an unexpected crash or system reboot, the daemon automatically invokes `recover_pending_observations()`.
- Signals created within the past 24 hours with scheduled checkpoints are inspected.
- Checkpoints that expired while the system was offline are recorded with status `missed_offline` to prevent spurious delayed observations.
- Future checkpoints are seamlessly rescheduled into the active asyncio task scheduler.

### 7.2 Handling Telegram MTProto Disconnects
If the Telegram client disconnects or encounters rate limiting:
- Telethon handles automatic exponential reconnection.
- Check logs: `journalctl -u meco-telegram.service -f`
- If session authorization is invalidated, stop service and regenerate session:
  ```bash
  sudo systemctl stop meco-telegram.service
  .venv/bin/python -m app.telegram.client  # Enter 2FA / code interactively
  sudo systemctl start meco-telegram.service
  ```

### 7.3 Handling Solana RPC Rate Limiting (HTTP 429)
The on-chain enrichment client implements adaptive exponential backoff with jitter:
- Default retry policy: 3 attempts with base delay 0.5s up to 8s.
- If persistent 429 errors occur, configure a private RPC endpoint (e.g. Helius, QuickNode, Triton) in `.env`:
  ```env
  SOLANA_RPC_URL=https://mainnet.helius-rpc.com/?api-key=your_key
  ```

### 7.4 Emergency Stop & Operator Interventions
In the event of an anomalous market cascade or unexpected behavior, trigger the emergency stop:
```bash
# Via API using configured API_AUTH_TOKEN:
curl -X POST http://localhost:8000/api/controls/emergency-stop \
  -H "Authorization: Bearer <API_AUTH_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Extreme market volatility spike", "cancel_proposals": true}'
```
This action:
1. Immediately halts all trade proposal evaluation.
2. Rejects pending proposals.
3. Closes all open paper positions under `emergency_stop` rationale.
4. Latches the system until explicitly reset via `/api/controls/reset-emergency-stop`.
