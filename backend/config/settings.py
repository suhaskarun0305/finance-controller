"""
Finance Controller — Application Settings
==========================================

Loads configuration from environment variables (via .env file).
All database credentials are read from the environment — nothing is hardcoded.
"""

import os
import re
from pathlib import Path
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load .env from the project root (two levels up from this file)
# ---------------------------------------------------------------------------
_project_root = Path(__file__).resolve().parent.parent.parent
_env_path = _project_root / ".env"
load_dotenv(dotenv_path=_env_path)

# ---------------------------------------------------------------------------
# Database Settings
# ---------------------------------------------------------------------------
# Priority:
#   1. DATABASE_URL from .env / environment variable  (Neon, PostgreSQL, etc.)
#   2. Fallback: local SQLite file  (no external DB required)
# ---------------------------------------------------------------------------
_SQLITE_FALLBACK = "sqlite:///./finance_controller.db"
_raw_url: str = os.getenv("DATABASE_URL", _SQLITE_FALLBACK)

# ---------------------------------------------------------------------------
# Normalize the PostgreSQL URL for psycopg2-binary compatibility:
#
# 1. Ensure the scheme is ``postgresql+psycopg2://`` so SQLAlchemy 2.x
#    uses the psycopg2-binary driver (the only PG driver in requirements).
#    Bare ``postgresql://`` or ``postgres://`` would resolve to the *new*
#    psycopg (v3) driver which is NOT installed.
#
# 2. Strip the ``channel_binding`` query parameter.  Neon's connection
#    pooler may append ``channel_binding=require`` which is a libpq /
#    psycopg3 feature.  psycopg2 does NOT recognise it and the parameter
#    causes the SSL handshake to hang indefinitely during pool_pre_ping.
# ---------------------------------------------------------------------------
if _raw_url.startswith(("postgresql://", "postgres://")):
    # Fix scheme → explicit psycopg2 driver
    _raw_url = re.sub(r"^postgres(ql)?://", "postgresql+psycopg2://", _raw_url)

    # Remove channel_binding from the query string (psycopg2-incompatible)
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    _parsed = urlparse(_raw_url)
    _params = parse_qs(_parsed.query)
    _params.pop("channel_binding", None)
    _clean_query = urlencode(_params, doseq=True)
    _raw_url = urlunparse(_parsed._replace(query=_clean_query))

DATABASE_URL: str = _raw_url

# Connection-pool tuning (safe defaults for local development)
DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
DB_ECHO_SQL: bool = os.getenv("DB_ECHO_SQL", "false").lower() in ("true", "1", "yes")


def get_safe_database_url() -> str:
    """Return DATABASE_URL with the password masked for safe logging."""
    # Matches   scheme://user:PASSWORD@host...
    return re.sub(r"(?<=:)[^:@]+(?=@)", "********", DATABASE_URL)

