import asyncio
import json
import sys
import time
from datetime import datetime, timezone

from sqlalchemy import func, select, text

from app.api.state import system_state
from app.config.settings import get_settings
from app.database.models import (
    EnrichmentTask,
    MarketObservation,
    PaperPositionRecord,
    Signal,
    Token,
    TokenDecisionRecord,
    TokenInvestigation,
)
from app.database.session import SessionLocal
from solana.rpc.async_api import AsyncClient


async def run_healthcheck() -> dict:
    status = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "healthy",
        "database": {"ok": False, "latency_ms": 0.0},
        "solana_rpc": {"ok": False, "latency_ms": 0.0},
        "signals": {
            "total_count": 0,
            "latest_signal_id": None,
            "latest_signal_time": None,
            "minutes_since_latest": None,
        },
        "observations": {
            "total_count": 0,
            "latest_observation_time": None,
        },
        "intelligence": {
            "total_tokens": 0,
            "pending_enrichment_tasks": 0,
            "investigations_count": 0,
        },
        "decisions": {
            "total_decisions": 0,
        },
        "paper_trading": {
            "open_positions": 0,
            "emergency_stop_active": False,
        },
        "issues": [],
    }

    # 1. Check PostgreSQL Connectivity and Counts
    db_start = time.perf_counter()
    try:
        async with SessionLocal() as s:
            await s.execute(text("SELECT 1"))
            status["database"]["latency_ms"] = round(
                (time.perf_counter() - db_start) * 1000, 2
            )
            status["database"]["ok"] = True

            # Latest signal info
            sig_res = await s.execute(
                select(Signal.id, Signal.message_created_at)
                .order_by(Signal.id.desc())
                .limit(1)
            )
            latest_sig = sig_res.first()
            sig_count = await s.scalar(select(func.count(Signal.id)))

            status["signals"]["total_count"] = sig_count or 0
            if latest_sig:
                status["signals"]["latest_signal_id"] = latest_sig[0]
                status["signals"]["latest_signal_time"] = (
                    latest_sig[1].isoformat() if latest_sig[1] else None
                )
                if latest_sig[1]:
                    elapsed_min = (
                        datetime.now(timezone.utc) - latest_sig[1]
                    ).total_seconds() / 60.0
                    status["signals"]["minutes_since_latest"] = round(
                        elapsed_min, 1
                    )

            # Latest observation info
            obs_count = await s.scalar(select(func.count(MarketObservation.id)))
            status["observations"]["total_count"] = obs_count or 0

            latest_obs_time = await s.scalar(
                select(func.max(MarketObservation.observed_at))
            )
            status["observations"]["latest_observation_time"] = (
                latest_obs_time.isoformat() if latest_obs_time else None
            )

            # Token & Intelligence Stats
            try:
                tokens_count = await s.scalar(select(func.count(Token.id)))
                status["intelligence"]["total_tokens"] = tokens_count or 0

                pending_tasks = await s.scalar(
                    select(func.count(EnrichmentTask.id)).where(EnrichmentTask.status == "pending")
                )
                status["intelligence"]["pending_enrichment_tasks"] = pending_tasks or 0

                inv_count = await s.scalar(select(func.count(TokenInvestigation.id)))
                status["intelligence"]["investigations_count"] = inv_count or 0

                dec_count = await s.scalar(select(func.count(TokenDecisionRecord.id)))
                status["decisions"]["total_decisions"] = dec_count or 0

                open_pos = await s.scalar(
                    select(func.count(PaperPositionRecord.id)).where(
                        PaperPositionRecord.status.in_(["open", "partially_exited"])
                    )
                )
                status["paper_trading"]["open_positions"] = open_pos or 0
            except Exception:
                # In dev/mock without full tables yet
                pass

    except Exception as e:
        status["database"]["ok"] = False
        status["status"] = "unhealthy"
        status["issues"].append(f"Database error: {str(e)}")

    # 2. Check Gateway Safety Status
    emergency_on = system_state.paper_engine.risk_gateway.is_emergency_stop_active
    status["paper_trading"]["emergency_stop_active"] = emergency_on
    if emergency_on:
        status["status"] = "degraded"
        status["issues"].append("Emergency Stop Kill Switch is currently engaged.")

    # 3. Check Solana RPC
    rpc_start = time.perf_counter()
    try:
        settings = get_settings()
        async with AsyncClient(settings.solana_rpc_url) as client:
            resp = await client.get_slot()
            status["solana_rpc"]["latency_ms"] = round(
                (time.perf_counter() - rpc_start) * 1000, 2
            )
            status["solana_rpc"]["ok"] = resp.value is not None
            status["solana_rpc"]["current_slot"] = resp.value
    except Exception as e:
        status["solana_rpc"]["ok"] = False
        if status["status"] == "healthy":
            status["status"] = "degraded"
        status["issues"].append(f"Solana RPC error: {str(e)}")

    return status


async def main() -> None:
    status = await run_healthcheck()

    if "--json" in sys.argv:
        print(json.dumps(status, indent=2))
    else:
        print("=" * 80)
        print("MECO SYSTEM HEALTHCHECK (PHASE 9 PRODUCTION READY)")
        print("=" * 80)
        print(f"Overall Status:        {status['status'].upper()}")
        print(
            f"Database:              {'OK' if status['database']['ok'] else 'FAIL'} ({status['database']['latency_ms']}ms)"
        )
        print(
            f"Solana RPC:            {'OK' if status['solana_rpc']['ok'] else 'FAIL'} ({status['solana_rpc']['latency_ms']}ms)"
        )
        print(
            f"Total Signals:         {status['signals']['total_count']} (Latest: #{status['signals']['latest_signal_id']}, {status['signals']['minutes_since_latest']}m ago)"
        )
        print(
            f"Total Observations:    {status['observations']['total_count']} (Latest: {status['observations']['latest_observation_time']})"
        )
        print(
            f"Canonical Tokens:      {status['intelligence']['total_tokens']} (Pending Enrichment: {status['intelligence']['pending_enrichment_tasks']})"
        )
        print(
            f"Specialist Invs:       {status['intelligence']['investigations_count']}"
        )
        print(
            f"Decisions Generated:   {status['decisions']['total_decisions']}"
        )
        print(
            f"Open Paper Positions:  {status['paper_trading']['open_positions']} (Emergency Stop: {'ACTIVE' if status['paper_trading']['emergency_stop_active'] else 'INACTIVE'})"
        )
        if status["issues"]:
            print("Issues / Warnings:")
            for issue in status["issues"]:
                print(f"  - {issue}")
        print("=" * 80)

    if status["status"] == "unhealthy":
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
