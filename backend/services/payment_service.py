"""
Finance Controller — Payment Service
====================================

Queries and operations on Payment records.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from backend.models.payment import Payment
from backend.models.invoice import Invoice
from backend.models.settlement import Settlement
from backend.models.refund import Refund


class PaymentService:
    """Service for managing payment data access and queries."""

    def __init__(self, db_session: Session):
        self.session = db_session

    def list_payments(
        self,
        skip: int = 0,
        limit: int = 50,
        scenario_type: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch paginated payments with optional filtering."""
        stmt = select(Payment)
        count_stmt = select(func.count(Payment.id))

        if scenario_type:
            stmt = stmt.where(Payment.scenario_type == scenario_type)
            count_stmt = count_stmt.where(Payment.scenario_type == scenario_type)

        if search:
            like_term = f"%{search}%"
            filter_or = or_(
                Payment.razorpay_payment_id.ilike(like_term),
                Payment.payer_name.ilike(like_term),
                Payment.payer_email.ilike(like_term),
            )
            stmt = stmt.where(filter_or)
            count_stmt = count_stmt.where(filter_or)

        total = self.session.execute(count_stmt).scalar() or 0
        items = self.session.scalars(
            stmt.order_by(Payment.payment_date.desc()).offset(skip).limit(limit)
        ).all()

        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "items": [
                {
                    "id": p.id,
                    "razorpay_payment_id": p.razorpay_payment_id,
                    "amount": float(p.amount),
                    "currency": p.currency,
                    "status": p.status,
                    "method": p.method,
                    "payer_name": p.payer_name,
                    "payment_date": str(p.payment_date),
                    "scenario_type": p.scenario_type,
                    "invoice_id": p.invoice_id,
                    "customer_id": p.customer_id,
                }
                for p in items
            ],
        }

    def get_payment_detail(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Get full payment details with linked invoice, settlement, and refunds."""
        stmt = select(Payment).where(
            or_(Payment.id == payment_id, Payment.razorpay_payment_id == payment_id)
        )
        pay = self.session.scalars(stmt).first()
        if not pay:
            return None

        # Linked invoice
        inv = self.session.get(Invoice, pay.invoice_id) if pay.invoice_id else None

        # Linked settlement
        stl = self.session.scalars(
            select(Settlement).where(Settlement.payment_id == pay.id)
        ).first()

        # Linked refunds
        refunds = self.session.scalars(
            select(Refund).where(Refund.payment_id == pay.id)
        ).all()

        return {
            "id": pay.id,
            "razorpay_payment_id": pay.razorpay_payment_id,
            "amount": float(pay.amount),
            "fee": float(pay.fee),
            "tax": float(pay.tax),
            "currency": pay.currency,
            "status": pay.status,
            "method": pay.method,
            "payer_name": pay.payer_name,
            "payer_email": pay.payer_email,
            "payment_date": str(pay.payment_date),
            "scenario_type": pay.scenario_type,
            "order_id": pay.order_id,
            "invoice": {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "amount": float(inv.amount),
                "status": inv.status,
            } if inv else None,
            "settlement": {
                "id": stl.id,
                "razorpay_settlement_id": stl.razorpay_settlement_id,
                "gross_amount": float(stl.gross_amount),
                "fee": float(stl.fee),
                "tax": float(stl.tax),
                "net_amount": float(stl.net_amount),
                "settlement_date": str(stl.settlement_date),
            } if stl else None,
            "refunds": [
                {
                    "id": r.id,
                    "razorpay_refund_id": r.razorpay_refund_id,
                    "amount": float(r.amount),
                    "reason": r.reason,
                    "refund_date": str(r.refund_date),
                }
                for r in refunds
            ],
        }
