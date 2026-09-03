"""
Finance Controller — Reconciliation API Router
===============================================

Handles candidate generation and deterministic/batch reconciliation runs (PRD Section 16).
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.models.payment import Payment
from backend.models.reconciliation import ReconciliationRecord
from backend.reconciliation.candidate_generator import CandidateGenerator
from backend.reconciliation.matcher import Stage1Matcher
from backend.agents.investigator import InvestigatorAgent
from backend.schemas.reconciliation import (
    ReconciliationRunRequest,
    ReconciliationRunResponse,
    CandidateListResponse,
    CandidateItem,
    ReconciliationListResponse,
    ReconciliationRecordItem,
)
from backend.schemas.investigation import (
    InvestigatorRunRequest,
    InvestigatorRunResponse,
)

router = APIRouter(tags=["Reconciliation"])


@router.post("/reconciliation/run", response_model=ReconciliationRunResponse)
def run_reconciliation(
    req: ReconciliationRunRequest,
    db: Session = Depends(get_db),
):
    """
    Execute deterministic reconciliation for a specific payment or run batch pass.
    """
    matcher = Stage1Matcher(db)

    if req.payment_id:
        payment = db.get(Payment, req.payment_id)
        if not payment:
            payment = db.scalars(
                select(Payment).where(Payment.razorpay_payment_id == req.payment_id)
            ).first()
        if not payment:
            raise HTTPException(status_code=404, detail=f"Payment {req.payment_id} not found.")

        rec = matcher.process_payment(payment)
        return ReconciliationRunResponse(
            reconciliation_id=rec.id,
            payment_id=payment.id,
            status=rec.match_status,
            resolution_method=rec.match_method or "DETERMINISTIC",
            rule_matched=1 if rec.match_status == "MATCHED" else None,
            settlement_id=rec.settlement_id,
            notes=rec.notes,
            processed_count=1,
        )

    # Batch run
    records = matcher.process_all_payments()
    return ReconciliationRunResponse(
        status="BATCH_COMPLETED",
        resolution_method="DETERMINISTIC",
        processed_count=len(records),
        notes=f"Processed {len(records)} payments through Stage 1 deterministic engine.",
    )


@router.get("/reconciliation/records", response_model=ReconciliationListResponse)
def list_reconciliation_records(
    status: Optional[str] = Query(None, description="Filter by status"),
    stage: Optional[int] = Query(None, description="Filter by stage 1 or 2"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List historical reconciliation records."""
    stmt = select(ReconciliationRecord)
    if status:
        stmt = stmt.where(ReconciliationRecord.match_status == status)
    if stage:
        stmt = stmt.where(ReconciliationRecord.stage == stage)

    stmt = stmt.order_by(ReconciliationRecord.created_at.desc()).limit(limit)
    items = db.scalars(stmt).all()

    return ReconciliationListResponse(
        total=len(items),
        items=[ReconciliationRecordItem.model_validate(r) for r in items],
    )


@router.get("/candidates/{payment_id}", response_model=CandidateListResponse)
def get_candidates(
    payment_id: str,
    db: Session = Depends(get_db),
):
    """
    Get top candidate settlements and invoices for a payment per PRD Section 10 & 16.
    """
    payment = db.get(Payment, payment_id)
    if not payment:
        payment = db.scalars(
            select(Payment).where(Payment.razorpay_payment_id == payment_id)
        ).first()
    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found.")

    gen = CandidateGenerator(db)
    cand_set = gen.generate_candidates(payment)

    candidates = []
    for sc in cand_set.settlements:
        stl = sc.settlement
        candidates.append(
            CandidateItem(
                settlement_id=stl.id,
                net_amount=float(stl.net_amount),
                gross_amount=float(stl.gross_amount),
                settled_at=str(stl.settlement_date),
                source=sc.match_type.upper(),
                score=sc.composite_score,
                notes=sc.notes,
            )
        )

    return CandidateListResponse(
        payment_id=payment.id,
        candidates=candidates,
    )


@router.post("/investigator/run", response_model=InvestigatorRunResponse)
def run_investigator(
    req: InvestigatorRunRequest,
    db: Session = Depends(get_db),
):
    """
    Trigger Stage 2 AI Investigation on an unresolved case per PRD Section 12 & 16.
    """
    investigator = InvestigatorAgent(db)

    payment = None
    if req.payment_id:
        payment = db.get(Payment, req.payment_id)
    elif req.reconciliation_id:
        rec = db.get(ReconciliationRecord, req.reconciliation_id)
        if rec and rec.payment_id:
            payment = db.get(Payment, rec.payment_id)

    if not payment:
        raise HTTPException(status_code=404, detail="Payment for investigation not found.")

    rec = investigator.investigate_payment(payment)

    return InvestigatorRunResponse(
        reconciliation_id=rec.id,
        verdict=rec.match_status,
        reason=rec.scenario_type or "INVESTIGATION_COMPLETE",
        confidence=rec.match_score or 0.95,
        evidence_ids=[rec.settlement_id] if rec.settlement_id else [],
        validation_passed=True,
        final_status=rec.match_status,
        explanation=rec.notes,
    )
