"""
Finance Controller — Application Settings
==========================================

Loads configuration from environment variables (via .env file).
All database credentials are read from the environment — nothing is hardcoded.
"""

import os
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
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/finance_controller",
)

# Connection-pool tuning (safe defaults for local development)
DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
DB_ECHO_SQL: bool = os.getenv("DB_ECHO_SQL", "false").lower() in ("true", "1", "yes")
