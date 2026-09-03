"""
Finance Controller — Application Entry-point
=============================================

FastAPI application exposing Track 04 Payment and Settlement Reconciliation APIs,
AI Exception Investigation, Human Review Handoff, and interactive Dashboard UI.
"""

from pathlib import Path
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.api.reconciliation import router as reconciliation_router
from backend.api.exceptions import router as exceptions_router
from backend.api.metrics import router as metrics_router
from backend.api.payments import router as payments_router
from backend.api.settlements import router as settlements_router

# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI Finance Controller — Track 04",
    description="Payment + Settlement Reconciliation with AI-Powered Exception Investigation",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Mount API Routers (under /api/v1)
# ---------------------------------------------------------------------------
app.include_router(reconciliation_router, prefix="/api/v1")
app.include_router(exceptions_router, prefix="/api/v1")
app.include_router(metrics_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(settlements_router, prefix="/api/v1")

# ---------------------------------------------------------------------------
# Mount Static Files & Dashboard UI
# ---------------------------------------------------------------------------
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
@app.get("/dashboard")
def serve_dashboard():
    """Serve the interactive financial controller dashboard."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"status": "ok", "service": "finance-controller", "dashboard": "unavailable"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    """
    Database health check.
    Returns 200 if the database is reachable.
    """
    result = db.execute(text("SELECT 1")).scalar()
    return {"status": "healthy", "database": "connected", "result": result}
