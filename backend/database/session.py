"""
Finance Controller — Database Session Management
=================================================

Provides:

1. ``SessionLocal`` — a **session factory** (``sessionmaker``) bound to the
   engine.  Calling ``SessionLocal()`` returns a new ``Session`` instance.

2. ``get_db()`` — a **generator / dependency** designed for FastAPI's
   dependency-injection system.  It yields a session, then guarantees
   cleanup (close) when the request is finished — even if an exception
   occurs.

Usage in a FastAPI route (future steps)
---------------------------------------
::

    from fastapi import Depends
    from sqlalchemy.orm import Session
    from backend.database.session import get_db

    @router.get("/items")
    def list_items(db: Session = Depends(get_db)):
        return db.execute(text("SELECT 1")).scalar()
"""

from typing import Generator

from sqlalchemy.orm import Session, sessionmaker

from backend.database.connection import engine

# ---------------------------------------------------------------------------
# Session factory — produces new Session objects bound to our engine
# ---------------------------------------------------------------------------
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,   # explicit commits required
    autoflush=False,    # prevents unexpected flushes before queries
    expire_on_commit=False,  # keeps ORM objects usable after commit
)

# ---------------------------------------------------------------------------
# FastAPI-compatible dependency
# ---------------------------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """
    Yield a database session for the lifetime of a single request.

    The ``finally`` block ensures the session is closed even when the
    request handler raises an unhandled exception.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
