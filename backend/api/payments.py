"""
Finance Controller — Payments API Router
========================================

Endpoints for browsing and searching Payments.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.services.payment_service import PaymentService
from backend.schemas.payment import PaymentListResponse, PaymentDetailResponse

router = APIRouter(tags=["Payments"])


@router.get("/payments", response_model=PaymentListResponse)
def list_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    scenario: Optional[str] = Query(None, description="Filter by scenario_type"),
    search: Optional[str] = Query(None, description="Search by ID, name, email"),
    db: Session = Depends(get_db),
):
    """List paginated payment records."""
    service = PaymentService(db)
    res = service.list_payments(skip=skip, limit=limit, scenario_type=scenario, search=search)
    return PaymentListResponse(**res)


@router.get("/payments/{payment_id}", response_model=PaymentDetailResponse)
def get_payment(
    payment_id: str,
    db: Session = Depends(get_db),
):
    """Get detailed payment record with linked invoice, settlement, and refunds."""
    service = PaymentService(db)
    detail = service.get_payment_detail(payment_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found.")
    return PaymentDetailResponse(**detail)
