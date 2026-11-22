"""
Resource Audit & Profiling Tool for Meco (Phase 9).
Pure standard-library Linux implementation without external psutil dependency.
Measures:
- Resident memory (RSS) and Virtual memory (VMS) via /proc/self/status and getrusage.
- CPU information and system memory via /proc/meminfo.
- PostgreSQL database size, active connections, and table storage breakdown.
- Connection counts and pool utilization limits.
- Background concurrency boundaries and queue backlog.
- Solana RPC and network event latency.
"""
import asyncio
import json
import os
import resource
import sys
import time
from datetime import datetime, timezone

from solana.rpc.async_api import AsyncClient
from sqlalchemy import text

from app.config.settings import get_settings
from app.database.session import SessionLocal


def get_linux_proc_status() -> dict:
    """Parses /proc/self/status for accurate memory metrics."""
    res = {"rss_mb": 0.0, "vms_mb": 0.0, "threads": 1}
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    res["rss_mb"] = round(float(parts[1]) / 1024, 2)
                elif line.startswith("VmSize:"):
                    parts = line.split()
                    res["vms_mb"] = round(float(parts[1]) / 1024, 2)
                elif line.startswith("Threads:"):
                    parts = line.split()
                    res["threads"] = int(parts[1])
    except Exception:
        # Fallback to getrusage (kilobytes on Linux)
        ru = resource.getrusage(resource.RUSAGE_SELF)
        res["rss_mb"] = round(ru.ru_maxrss / 1024, 2)
        res["vms_mb"] = res["rss_mb"]
    return res


def get_linux_meminfo() -> dict:
    """Parses /proc/meminfo for system-wide RAM metrics."""
    res = {"total_ram_mb": 0.0, "available_ram_mb": 0.0, "ram_used_pct": 0.0}
    try:
        mem_total = 0.0
        mem_avail = 0.0
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    mem_total = float(line.split()[1]) / 1024
                elif line.startswith("MemAvailable:"):
                    mem_avail = float(line.split()[1]) / 1024
        res["total_ram_mb"] = round(mem_total, 2)
        res["available_ram_mb"] = round(mem_avail, 2)
        if mem_total > 0:
            used_pct = ((mem_total - mem_avail) / mem_total) * 100
            res["ram_used_pct"] = round(used_pct, 1)
    except Exception:
        pass
    return res


async def audit_resources() -> dict:
    proc_info = get_linux_proc_status()
    sys_mem = get_linux_meminfo()
    cpu_count = os.cpu_count() or 1

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "process": {
            "pid": os.getpid(),
            "rss_mb": proc_info["rss_mb"],
            "vms_mb": proc_info["vms_mb"],
            "num_threads": proc_info["threads"],
        },
        "system": {
            "total_ram_mb": sys_mem["total_ram_mb"],
            "available_ram_mb": sys_mem["available_ram_mb"],
            "ram_used_pct": sys_mem["ram_used_pct"],
            "cpu_count": cpu_count,
        },
        "database": {
            "connected": False,
            "db_size_human": "N/A",
            "active_connections": 0,
            "table_sizes": [],
            "configured_pool_size": 10,
            "configured_max_overflow": 5,
        },
        "concurrency_limits": {
            "enrichment_max_concurrency": 5,
            "in_memory_log_buffer_cap": 200,
            "db_pool_ceiling": 15,
        },
        "network_latencies_ms": {
            "database_query": 0.0,
            "solana_rpc_slot": 0.0,
        },
    }

    settings = get_settings()
    report["database"]["configured_pool_size"] = settings.db_pool_size
    report["database"]["configured_max_overflow"] = settings.db_max_overflow
    report["concurrency_limits"]["db_pool_ceiling"] = settings.db_pool_size + settings.db_max_overflow

    # 1. Audit Database Metrics
    db_t0 = time.perf_counter()
    try:
        async with SessionLocal() as s:
            await s.execute(text("SELECT 1"))
            report["network_latencies_ms"]["database_query"] = round(
                (time.perf_counter() - db_t0) * 1000, 2
            )
            report["database"]["connected"] = True

            # Database total size
            size_res = await s.execute(
                text("SELECT pg_size_pretty(pg_database_size(current_database()));")
            )
            report["database"]["db_size_human"] = size_res.scalar() or "Unknown"

            # Active connections
            conn_res = await s.execute(
                text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database();")
            )
            report["database"]["active_connections"] = conn_res.scalar() or 0

            # Largest tables breakdown
            tables_query = text("""
                SELECT relname AS table_name,
                       pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
                       c.reltuples::bigint AS estimated_rows
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind = 'r'
                ORDER BY pg_total_relation_size(c.oid) DESC
                LIMIT 10;
            """)
            tbl_res = await s.execute(tables_query)
            for row in tbl_res.all():
                report["database"]["table_sizes"].append({
                    "table": row[0],
                    "size": row[1],
                    "rows": max(0, row[2]),
                })
    except Exception as exc:
        report["database"]["error"] = str(exc)

    # 2. Audit Solana RPC Latency
    rpc_t0 = time.perf_counter()
    try:
        async with AsyncClient(settings.solana_rpc_url) as client:
            resp = await client.get_slot()
            report["network_latencies_ms"]["solana_rpc_slot"] = round(
                (time.perf_counter() - rpc_t0) * 1000, 2
            )
            report["network_latencies_ms"]["slot"] = resp.value
    except Exception as exc:
        report["network_latencies_ms"]["rpc_error"] = str(exc)

    return report


async def main() -> None:
    data = await audit_resources()
    if "--json" in sys.argv:
        print(json.dumps(data, indent=2))
        return

    print("=" * 80)
    print("MECO RESOURCE UTILIZATION & OPERATIONAL CAPACITY AUDIT")
    print("=" * 80)
    proc = data["process"]
    sys_info = data["system"]
    print(f"Process Resident Memory (RSS):  {proc['rss_mb']} MB (Virtual: {proc['vms_mb']} MB)")
    print(f"System RAM Utilization:        {sys_info['available_ram_mb']} MB available / {sys_info['total_ram_mb']} MB total ({sys_info['ram_used_pct']}%)")
    print(f"Process Threads:               {proc['num_threads']} threads (CPU cores: {sys_info['cpu_count']})")
    print("-" * 80)
    db = data["database"]
    print(f"PostgreSQL Database Size:      {db.get('db_size_human', 'N/A')}")
    print(f"Active DB Connections:         {db.get('active_connections', 0)} (Pool cap: {data['concurrency_limits']['db_pool_ceiling']})")
    print("Top Tables Storage Footprint:")
    for t in db.get("table_sizes", []):
        print(f"  - {t['table']:<32} {t['size']:>10} (~{t['rows']:,} rows)")
    print("-" * 80)
    limits = data["concurrency_limits"]
    print(f"Enrichment Concurrency Limit:  {limits['enrichment_max_concurrency']} workers")
    print(f"In-Memory Telemetry Ring Cap:  {limits['in_memory_log_buffer_cap']} events")
    print("-" * 80)
    lats = data["network_latencies_ms"]
    print(f"PostgreSQL Query Latency:      {lats.get('database_query', 0)} ms")
    print(f"Solana RPC Slot Latency:       {lats.get('solana_rpc_slot', 0)} ms (Slot: {lats.get('slot', 'N/A')})")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
