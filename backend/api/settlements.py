"""
Finance Controller — Settlements API Router
===========================================

Endpoints for browsing and searching Settlements.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.services.settlement_service import SettlementService
from backend.schemas.settlement import SettlementListResponse, SettlementDetailResponse

router = APIRouter(tags=["Settlements"])


@router.get("/settlements", response_model=SettlementListResponse)
def list_settlements(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None, description="Search by ID, UTR"),
    db: Session = Depends(get_db),
):
    """List paginated settlement records."""
    service = SettlementService(db)
    res = service.list_settlements(skip=skip, limit=limit, search=search)
    return SettlementListResponse(**res)


@router.get("/settlements/{settlement_id}", response_model=SettlementDetailResponse)
def get_settlement(
    settlement_id: str,
    db: Session = Depends(get_db),
):
    """Get settlement details with linked payment if matched."""
    service = SettlementService(db)
    detail = service.get_settlement_detail(settlement_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Settlement {settlement_id} not found.")
    return SettlementDetailResponse(**detail)
