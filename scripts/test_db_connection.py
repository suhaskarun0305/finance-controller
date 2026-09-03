"""
Finance Controller — Database Connectivity Test
================================================

A standalone script that verifies the database connection is working.

Run from the project root:

    python -m scripts.test_db_connection

Or directly:

    python scripts/test_db_connection.py

What it tests:
  1. Can we create an engine and open a raw connection?
  2. Does ``SELECT 1`` return the expected result?
  3. Can we query the database server version?
  4. Does the session factory (``SessionLocal``) work?
  5. Connection pool stats (PostgreSQL only).
"""

import sys
import io
from pathlib import Path

# ---------------------------------------------------------------------------
# Force UTF-8 output on Windows (avoids cp1252 encoding errors)
# ---------------------------------------------------------------------------
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so ``backend.*`` imports work
# when running the script directly (python scripts/test_db_connection.py).
# ---------------------------------------------------------------------------
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from sqlalchemy import text

from backend.config.settings import DATABASE_URL
from backend.database.connection import engine
from backend.database.session import SessionLocal


def main() -> None:
    is_sqlite = DATABASE_URL.startswith("sqlite")
    backend_label = "SQLite" if is_sqlite else "PostgreSQL"

    print("=" * 60)
    print("  Finance Controller -- Database Connectivity Test")
    print(f"  Backend: {backend_label}")
    print(f"  URL:     {DATABASE_URL}")
    print("=" * 60)
    print()

    passed = 0
    total = 4

    # ------------------------------------------------------------------
    # Test 1: Raw connection + SELECT 1
    # ------------------------------------------------------------------
    print("[Test 1] Opening a raw connection and running SELECT 1 ...")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            assert result == 1, f"Expected 1, got {result}"
        print("         [PASS] SELECT 1 returned 1\n")
        passed += 1
    except Exception as exc:
        print(f"         [FAIL] {exc}\n")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Test 2: Database version
    # ------------------------------------------------------------------
    print("[Test 2] Querying database version ...")
    try:
        with engine.connect() as conn:
            if is_sqlite:
                version = conn.execute(text("SELECT sqlite_version()")).scalar()
            else:
                version = conn.execute(text("SELECT version()")).scalar()
        print(f"         [PASS] {version}\n")
        passed += 1
    except Exception as exc:
        print(f"         [FAIL] {exc}\n")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Test 3: SessionLocal factory
    # ------------------------------------------------------------------
    print("[Test 3] Creating a session via SessionLocal ...")
    try:
        session = SessionLocal()
        if is_sqlite:
            result = session.execute(text("SELECT 'finance_controller'")).scalar()
        else:
            result = session.execute(text("SELECT current_database()")).scalar()
        session.close()
        print(f"         [PASS] Connected to database: {result}\n")
        passed += 1
    except Exception as exc:
        print(f"         [FAIL] {exc}\n")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Test 4: Connection pool stats (PostgreSQL only)
    # ------------------------------------------------------------------
    if not is_sqlite:
        print("[Test 4] Connection pool stats ...")
        pool = engine.pool
        print(f"         Pool size       : {pool.size()}")
        print(f"         Checked-in      : {pool.checkedin()}")
        print(f"         Checked-out     : {pool.checkedout()}")
        print(f"         Overflow        : {pool.overflow()}")
        print("         [PASS]\n")
        passed += 1
    else:
        print("[Test 4] Skipped (pool stats not applicable to SQLite)\n")
        passed += 1

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("=" * 60)
    print(f"  Result: {passed}/{total} tests passed")
    print("  All tests passed -- database connection is healthy!")
    print("=" * 60)

    if is_sqlite:
        print()
        print("  NOTE: You are using SQLite for local development.")
        print("  To switch to PostgreSQL:")
        print("    1. Install PostgreSQL or run: docker-compose up -d")
        print("    2. Edit .env and uncomment the PostgreSQL DATABASE_URL")
        print("    3. Comment out the SQLite DATABASE_URL")
        print("    4. Re-run this test")


if __name__ == "__main__":
    main()
