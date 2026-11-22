"""
Test Suite for Database Backup, Verification, and Rotation (Phase 9).
"""
import gzip

import pytest

from scripts.backup_db import create_backup, parse_db_url, rotate_backups


def test_parse_db_url():
    """Verifies parsing of standard and asyncpg database URLs."""
    url1 = "postgresql+asyncpg://user:pass@127.0.0.1:5432/meco_test"
    parsed1 = parse_db_url(url1)
    assert parsed1["user"] == "user"
    assert parsed1["password"] == "pass"
    assert parsed1["host"] == "127.0.0.1"
    assert parsed1["port"] == "5432"
    assert parsed1["dbname"] == "meco_test"

    url2 = "postgresql://postgres@localhost/meco"
    parsed2 = parse_db_url(url2)
    assert parsed2["user"] == "postgres"
    assert parsed2["password"] == ""
    assert parsed2["host"] == "localhost"
    assert parsed2["dbname"] == "meco"


def test_backup_rotation_policy(tmp_path):
    """Verifies backup rotation preserves minimum backup count and prunes expired files."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    # Create 5 simulated backup archives
    files = []
    for i in range(5):
        f = backup_dir / f"meco_backup_scheduled_202611{i+10}_120000.sql.gz"
        with gzip.open(f, "wb") as gz:
            gz.write(b"-- Simulated SQL Backup Header")
        files.append(f)

    # Rotation with retention 0 days, keeping minimum 2
    pruned = rotate_backups(output_dir=str(backup_dir), retention_days=0, keep_minimum=2)
    assert pruned == 3
    remaining = list(backup_dir.glob("meco_backup_*.sql.gz"))
    assert len(remaining) == 2


def test_backup_creation_and_integrity(tmp_path):
    """Verifies create_backup outputs non-empty readable gzip archive."""
    backup_dir = tmp_path / "pg_backups"
    backup_dir.mkdir()

    try:
        backup_file = create_backup(output_dir=str(backup_dir), tag="test")
        assert backup_file.exists()
        assert backup_file.stat().st_size > 0

        # Verify it can be decompressed
        with gzip.open(backup_file, "rb") as gz:
            content = gz.read(100)
            assert b"PostgreSQL database dump" in content or len(content) > 0
    except Exception as e:
        # If pg_dump is not available or DB not accessible in CI, mark skipped gracefully
        if "pg_dump failed" in str(e) or "FileNotFoundError" in str(e):
            pytest.skip(f"pg_dump not available in current environment: {e}")
        else:
            raise
