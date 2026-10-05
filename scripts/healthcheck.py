import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select, text

from app.config.settings import get_settings
from app.database.models import MarketObservation, Signal
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
            "recent_1h_successes": 0,
            "recent_1h_failures": 0,
        },
        "issues": [],
    }

    # 1. Check PostgreSQL
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

    except Exception as e:
        status["database"]["ok"] = False
        status["status"] = "unhealthy"
        status["issues"].append(f"Database error: {str(e)}")

    # 2. Check Solana RPC
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
        status["status"] = "degraded"
        status["issues"].append(f"Solana RPC error: {str(e)}")

    return status


async def main() -> None:
    status = await run_healthcheck()

    if "--json" in sys.argv:
        print(json.dumps(status, indent=2))
    else:
        print("=" * 80)
        print("MECO SYSTEM HEALTHCHECK")
        print("=" * 80)
        print(f"Overall Status:   {status['status'].upper()}")
        print(
            f"Database:         {'OK' if status['database']['ok'] else 'FAIL'} ({status['database']['latency_ms']}ms)"
        )
        print(
            f"Solana RPC:       {'OK' if status['solana_rpc']['ok'] else 'FAIL'} ({status['solana_rpc']['latency_ms']}ms)"
        )
        print(
            f"Total Signals:    {status['signals']['total_count']} (Latest: #{status['signals']['latest_signal_id']}, {status['signals']['minutes_since_latest']}m ago)"
        )
        print(
            f"Total Obs:        {status['observations']['total_count']} (Latest: {status['observations']['latest_observation_time']})"
        )
        if status["issues"]:
            print("Issues:")
            for issue in status["issues"]:
                print(f"  - {issue}")
        print("=" * 80)

    if status["status"] == "unhealthy":
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
