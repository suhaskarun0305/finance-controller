"""
Finance Controller — Exceptions & Review Queue API Router
=========================================================

Endpoints for exception monitoring and the human review workflow (PRD Section 14).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.services.exception_service import ExceptionService
from backend.schemas.exception import (
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    ReviewQueueItem,
    ExceptionListResponse,
    ExceptionItem,
)

router = APIRouter(tags=["Exceptions & Review"])


@router.get("/review/queue", response_model=List[ReviewQueueItem])
def get_human_review_queue(
    db: Session = Depends(get_db),
):
    """
    Get the human review queue sorted by amount at risk (desc) and age (asc)
    per PRD Section 14.3.
    """
    service = ExceptionService(db)
    queue = service.get_review_queue()
    return [ReviewQueueItem(**item) for item in queue]


@router.post("/review/{reconciliation_id}/decide", response_model=ReviewDecisionResponse)
def decide_human_review(
    reconciliation_id: str,
    req: ReviewDecisionRequest,
    db: Session = Depends(get_db),
):
    """
    Submit specialist action (ACCEPT, OVERRIDE, REQUEST_MORE_EVIDENCE) on a review case
    per PRD Section 14.4.
    """
    service = ExceptionService(db)
    try:
        res = service.decide_review(
            reconciliation_id=reconciliation_id,
            action=req.action,
            override_verdict=req.override_verdict,
            rationale=req.rationale,
            reviewer_id=req.reviewer_id,
        )
        return ReviewDecisionResponse(**res)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.get("/exceptions", response_model=ExceptionListResponse)
def list_exceptions(
    status: Optional[str] = Query(None, description="Filter by open/investigating/resolved/dismissed"),
    db: Session = Depends(get_db),
):
    """List system exception records."""
    service = ExceptionService(db)
    items = service.list_exceptions(status=status)
    return ExceptionListResponse(
        total=len(items),
        items=[ExceptionItem(**i) for i in items],
    )
