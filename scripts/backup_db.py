"""
Database Backup & Disaster Recovery Tool for Meco (Phase 9).
Provides safe, timestamped, compressed database backups, integrity verification,
retention rotation (cleaning old archive files, never live database rows),
and tested restoration capabilities.
"""
import argparse
import gzip
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.config.settings import get_settings

logging.basicConfig(
    format="[%(levelname)s %(asctime)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("meco.backup")


def parse_db_url(url: str) -> dict:
    """Parses database connection URL into parameters."""
    clean_url = url.replace("postgresql+asyncpg://", "postgresql://")
    parsed = urlparse(clean_url)
    return {
        "scheme": parsed.scheme,
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "dbname": parsed.path.lstrip("/") or "meco",
    }


def create_backup(
    output_dir: str = "backups",
    tag: str = "scheduled",
) -> Path:
    """
    Creates a compressed, timestamped database dump.
    Returns path to the verified backup file.
    """
    settings = get_settings()
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    db_info = parse_db_url(settings.database_url)

    backup_file = out_path / f"meco_backup_{tag}_{timestamp}.sql.gz"
    logger.info("Initiating database backup for database '%s' -> %s", db_info["dbname"], backup_file)

    env = os.environ.copy()
    if db_info["password"]:
        env["PGPASSWORD"] = db_info["password"]

    pg_dump_cmd = [
        "pg_dump",
        "-h", db_info["host"],
        "-p", db_info["port"],
        "-U", db_info["user"],
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        db_info["dbname"],
    ]

    try:
        # Run pg_dump piped through gzip compression
        proc = subprocess.Popen(pg_dump_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        with gzip.open(backup_file, "wb") as gz_out:
            shutil.copyfileobj(proc.stdout, gz_out)

        _, stderr = proc.communicate()
        if proc.returncode != 0:
            err_msg = stderr.decode().strip()
            if backup_file.exists():
                backup_file.unlink()
            raise RuntimeError(f"pg_dump failed with exit code {proc.returncode}: {err_msg}")

    except FileNotFoundError:
        # If pg_dump binary is missing, attempt fallback via SQL export or handle
        logger.error("pg_dump binary not found in PATH.")
        raise

    # Verify backup integrity
    if not backup_file.exists() or backup_file.stat().st_size == 0:
        raise RuntimeError("Backup verification failed: created backup file is empty or missing.")

    # Test gzip header and decompression
    with gzip.open(backup_file, "rb") as test_gz:
        header = test_gz.read(256)
        if not header:
            raise RuntimeError("Backup verification failed: compressed archive could not be read.")

    file_size_kb = round(backup_file.stat().st_size / 1024, 2)
    logger.info("Backup successfully created and verified: %s (%s KB)", backup_file, file_size_kb)
    return backup_file


def rotate_backups(
    output_dir: str = "backups",
    retention_days: int = 14,
    keep_minimum: int = 3,
) -> int:
    """
    Removes backup files older than retention_days, keeping at least keep_minimum files.
    Never deletes or alters historical database records.
    """
    out_path = Path(output_dir)
    if not out_path.exists():
        return 0

    backups = sorted(out_path.glob("meco_backup_*.sql.gz"), key=lambda p: p.stat().st_mtime)
    if len(backups) <= keep_minimum:
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    pruned = 0

    # Only consider pruning excess files beyond keep_minimum
    candidates = backups[:-keep_minimum]
    for b in candidates:
        mtime = datetime.fromtimestamp(b.stat().st_mtime, timezone.utc)
        if mtime < cutoff:
            logger.info("Pruning expired backup archive: %s (created %s)", b.name, mtime.isoformat())
            b.unlink()
            pruned += 1

    return pruned


def restore_backup(
    backup_file: Path | str,
    target_dbname: str | None = None,
) -> bool:
    """
    Restores a database from a compressed .sql.gz archive file.
    """
    path = Path(backup_file)
    if not path.exists():
        raise FileNotFoundError(f"Backup file '{backup_file}' does not exist.")

    settings = get_settings()
    db_info = parse_db_url(settings.database_url)
    dbname = target_dbname or db_info["dbname"]

    logger.warning("RESTORATION INITIATED: Restoring database '%s' from %s", dbname, path)

    env = os.environ.copy()
    if db_info["password"]:
        env["PGPASSWORD"] = db_info["password"]

    psql_cmd = [
        "psql",
        "-h", db_info["host"],
        "-p", db_info["port"],
        "-U", db_info["user"],
        "-d", dbname,
    ]

    # Decompress and stream into psql
    with gzip.open(path, "rb") as gz_in:
        sql_bytes = gz_in.read()

    proc = subprocess.run(psql_cmd, input=sql_bytes, capture_output=True, env=env, check=False)

    if proc.returncode != 0:
        logger.error("Restore failed: %s", proc.stderr.decode().strip())
        return False

    logger.info("Database restoration completed successfully.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Meco Production Database Backup & Restore Utility")
    parser.add_argument("--create", action="store_true", help="Create a verified timestamped backup")
    parser.add_argument("--restore", type=str, help="Restore database from specified backup file")
    parser.add_argument("--target-db", type=str, help="Target database name for restore (defaults to configured db)")
    parser.add_argument("--rotate", action="store_true", help="Prune old backup archives according to retention policy")
    parser.add_argument("--retention-days", type=int, default=14, help="Retention period in days (default: 14)")
    parser.add_argument("--dir", type=str, default="backups", help="Directory for backup archives (default: backups)")

    args = parser.parse_args()

    if args.create:
        backup = create_backup(output_dir=args.dir)
        print(f"SUCCESS: Backup created at {backup}")
        if args.rotate:
            pruned = rotate_backups(output_dir=args.dir, retention_days=args.retention_days)
            print(f"Rotated {pruned} expired backup archives.")
        sys.exit(0)

    if args.restore:
        ok = restore_backup(args.restore, target_dbname=args.target_db)
        if ok:
            print("SUCCESS: Database restored.")
            sys.exit(0)
        else:
            print("FAILED: Restoration encountered errors.")
            sys.exit(1)

    if args.rotate:
        pruned = rotate_backups(output_dir=args.dir, retention_days=args.retention_days)
        print(f"Rotated {pruned} expired backup archives.")
        sys.exit(0)

    parser.print_help()


if __name__ == "__main__":
    main()
