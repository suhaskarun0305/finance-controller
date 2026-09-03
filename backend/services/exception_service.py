"""
Finance Controller — Exception & Human Review Service
=====================================================

Manages exception records, the human review queue, and reviewer actions
(ACCEPT, OVERRIDE, REQUEST_MORE_EVIDENCE) per PRD Section 14.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from backend.models.exception import ExceptionRecord
from backend.models.reconciliation import ReconciliationRecord
from backend.models.payment import Payment
from backend.services.audit_service import AuditService


class ExceptionService:
    """Service for handling exceptions and human review workflows."""

    def __init__(self, db_session: Session):
        self.session = db_session
        self.audit_service = AuditService(db_session)

    def create_exception(
        self,
        reconciliation_id: str,
        payment_id: str,
        exception_type: str,
        severity: str = "medium",
        description: Optional[str] = None,
        scenario_type: Optional[str] = None,
        invoice_id: Optional[str] = None,
    ) -> ExceptionRecord:
        """Create a new exception record."""
        exc = ExceptionRecord(
            id=str(uuid.uuid4()),
            reconciliation_id=reconciliation_id,
            payment_id=payment_id,
            invoice_id=invoice_id,
            exception_type=exception_type,
            severity=severity,
            status="open",
            description=description,
            scenario_type=scenario_type,
        )
        self.session.add(exc)
        self.session.flush()
        return exc

    def get_review_queue(self) -> List[Dict[str, Any]]:
        """
        Fetch all cases needing human review, sorted by amount at risk (desc)
        and creation time (asc) per PRD Section 14.3.
        """
        stmt = (
            select(ReconciliationRecord, Payment)
            .join(Payment, ReconciliationRecord.payment_id == Payment.id, isouter=True)
            .where(ReconciliationRecord.match_status.in_(["NEEDS_HUMAN_REVIEW", "UNMATCHED"]))
            .order_by(Payment.amount.desc())
        )
        rows = self.session.execute(stmt).all()

        queue = []
        for rec, pay in rows:
            amount = float(pay.amount) if pay else float(rec.payment_amount or 0.0)
            pay_ref = pay.razorpay_payment_id if pay else "N/A"
            payer = pay.payer_name if pay else "N/A"

            # Find exception record if any
            exc = self.session.scalars(
                select(ExceptionRecord).where(ExceptionRecord.reconciliation_id == rec.id)
            ).first()

            queue.append({
                "reconciliation_id": rec.id,
                "payment_id": rec.payment_id,
                "razorpay_payment_id": pay_ref,
                "payer_name": payer,
                "amount_at_risk": amount,
                "currency": pay.currency if pay else "INR",
                "confidence": rec.match_score or 0.0,
                "reason_code": exc.exception_type if exc else (rec.scenario_type or "UNRESOLVED"),
                "status": rec.match_status,
                "created_at": str(rec.created_at),
                "notes": rec.notes,
            })

        return queue

    def list_exceptions(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List exception records with optional status filter."""
        stmt = select(ExceptionRecord, Payment).join(
            Payment, ExceptionRecord.payment_id == Payment.id, isouter=True
        )
        if status:
            stmt = stmt.where(ExceptionRecord.status == status)

        stmt = stmt.order_by(ExceptionRecord.created_at.desc())
        rows = self.session.execute(stmt).all()

        results = []
        for exc, pay in rows:
            results.append({
                "id": exc.id,
                "reconciliation_id": exc.reconciliation_id,
                "payment_id": exc.payment_id,
                "razorpay_payment_id": pay.razorpay_payment_id if pay else "N/A",
                "amount": float(pay.amount) if pay else None,
                "currency": pay.currency if pay else "INR",
                "exception_type": exc.exception_type,
                "severity": exc.severity,
                "status": exc.status,
                "description": exc.description,
                "created_at": str(exc.created_at),
                "resolved_at": str(exc.resolved_at) if exc.resolved_at else None,
            })
        return results

    def decide_review(
        self,
        reconciliation_id: str,
        action: str,
        override_verdict: Optional[str] = None,
        rationale: Optional[str] = None,
        reviewer_id: str = "specialist-1",
    ) -> Dict[str, Any]:
        """
        Process human specialist decision per PRD Section 14.4:
          - action: ACCEPT | OVERRIDE | REQUEST_MORE_EVIDENCE
          - override_verdict: MATCHED | EXCEPTION | null
          - rationale: required if action != ACCEPT
        """
        action = action.upper()
        if action != "ACCEPT" and not rationale:
            raise ValueError("Rationale is required for OVERRIDE or REQUEST_MORE_EVIDENCE actions.")

        rec = self.session.get(ReconciliationRecord, reconciliation_id)
        if not rec:
            raise ValueError(f"Reconciliation record {reconciliation_id} not found.")

        old_status = rec.match_status
        new_status = old_status

        if action == "ACCEPT":
            # Accept proposed verdict
            new_status = "RESOLVED_AFTER_INVESTIGATION"
            rec.match_status = new_status
            rec.match_method = "HUMAN_ACCEPTED"
            rec.notes = f"Accepted by {reviewer_id}. {rec.notes or ''}".strip()
        elif action == "OVERRIDE":
            verdict = (override_verdict or "MATCHED").upper()
            new_status = verdict
            rec.match_status = new_status
            rec.match_method = "HUMAN_OVERRIDE"
            rec.notes = f"Overridden by {reviewer_id} to {verdict}. Rationale: {rationale}"
        elif action == "REQUEST_MORE_EVIDENCE":
            new_status = "NEEDS_HUMAN_REVIEW"
            rec.notes = f"More evidence requested by {reviewer_id}: {rationale}"

        # Resolve related exception record
        exc = self.session.scalars(
            select(ExceptionRecord).where(ExceptionRecord.reconciliation_id == reconciliation_id)
        ).first()
        if exc:
            if action in ("ACCEPT", "OVERRIDE"):
                exc.status = "resolved"
                exc.resolved_at = datetime.now(timezone.utc)
                exc.resolution = f"Resolved via {action}: {rationale or 'Accepted'}"

        # Write immutable audit entry
        audit_log = self.audit_service.record_step(
            reconciliation_id=reconciliation_id,
            step="HUMAN_REVIEW",
            actor=f"user:{reviewer_id}",
            input_snapshot={
                "previous_status": old_status,
                "action": action,
                "override_verdict": override_verdict,
                "rationale": rationale,
            },
            output_snapshot={
                "new_status": new_status,
                "resolution_method": rec.match_method,
            },
            evidence_refs=[],
            exception_id=exc.id if exc else None,
        )

        self.session.commit()

        return {
            "reconciliation_id": reconciliation_id,
            "new_status": new_status,
            "resolution_method": rec.match_method,
            "audit_id": audit_log.id,
        }
