"""
Finance Controller — Database Connection
=========================================

Creates the SQLAlchemy **engine** — the single entry-point that manages a
pool of low-level DBAPI connections to the database.

Supports both PostgreSQL (production / ideathon demo) and SQLite (quick
local development without installing PostgreSQL).

Key design decisions
--------------------
* The engine is created as a module-level singleton so the entire
  application shares one connection pool.
* For PostgreSQL: ``pool_pre_ping=True`` issues a lightweight ``SELECT 1``
  before handing out a connection, transparently recovering from stale
  or dropped connections.
* For SQLite: ``check_same_thread=False`` is required because FastAPI
  serves requests in multiple threads but SQLite only allows usage from
  the thread that created the connection by default.
* Pool size and SQL echo are read from ``backend.config.settings`` which,
  in turn, reads them from environment variables / ``.env``.
"""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from backend.config.settings import (
    DATABASE_URL,
    DB_POOL_SIZE,
    DB_MAX_OVERFLOW,
    DB_ECHO_SQL,
)

# ---------------------------------------------------------------------------
# Build engine kwargs based on the database backend
# ---------------------------------------------------------------------------
_is_sqlite = DATABASE_URL.startswith("sqlite")

_engine_kwargs: dict = {
    "echo": DB_ECHO_SQL,
}

if _is_sqlite:
    # SQLite needs this for multi-threaded FastAPI usage
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL connection-pool settings
    _engine_kwargs.update(
        {
            "pool_size": DB_POOL_SIZE,
            "max_overflow": DB_MAX_OVERFLOW,
            "pool_pre_ping": True,  # auto-recover stale connections
        }
    )

# ---------------------------------------------------------------------------
# SQLAlchemy Engine (module-level singleton)
# ---------------------------------------------------------------------------
engine: Engine = create_engine(DATABASE_URL, **_engine_kwargs)
