"""
Finance Controller — Settlement Service
=======================================

Queries and operations on Settlement records.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from backend.models.settlement import Settlement
from backend.models.payment import Payment


class SettlementService:
    """Service for managing settlement data access and queries."""

    def __init__(self, db_session: Session):
        self.session = db_session

    def list_settlements(
        self,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch paginated settlements with optional search."""
        stmt = select(Settlement)
        count_stmt = select(func.count(Settlement.id))

        if search:
            like_term = f"%{search}%"
            filter_or = or_(
                Settlement.razorpay_settlement_id.ilike(like_term),
                Settlement.utr.ilike(like_term),
            )
            stmt = stmt.where(filter_or)
            count_stmt = count_stmt.where(filter_or)

        total = self.session.execute(count_stmt).scalar() or 0
        items = self.session.scalars(
            stmt.order_by(Settlement.settlement_date.desc()).offset(skip).limit(limit)
        ).all()

        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "items": [
                {
                    "id": s.id,
                    "razorpay_settlement_id": s.razorpay_settlement_id,
                    "gross_amount": float(s.gross_amount),
                    "fee": float(s.fee),
                    "tax": float(s.tax),
                    "net_amount": float(s.net_amount),
                    "currency": s.currency,
                    "status": s.status,
                    "utr": s.utr,
                    "settlement_date": str(s.settlement_date),
                    "payment_id": s.payment_id,
                }
                for s in items
            ],
        }

    def get_settlement_detail(self, settlement_id: str) -> Optional[Dict[str, Any]]:
        """Get settlement details with linked payment if matched."""
        stmt = select(Settlement).where(
            or_(Settlement.id == settlement_id, Settlement.razorpay_settlement_id == settlement_id)
        )
        stl = self.session.scalars(stmt).first()
        if not stl:
            return None

        pay = self.session.get(Payment, stl.payment_id) if stl.payment_id else None

        return {
            "id": stl.id,
            "razorpay_settlement_id": stl.razorpay_settlement_id,
            "gross_amount": float(stl.gross_amount),
            "fee": float(stl.fee),
            "tax": float(stl.tax),
            "net_amount": float(stl.net_amount),
            "currency": stl.currency,
            "status": stl.status,
            "utr": stl.utr,
            "settlement_date": str(stl.settlement_date),
            "payment_id": stl.payment_id,
            "payment": {
                "id": pay.id,
                "razorpay_payment_id": pay.razorpay_payment_id,
                "amount": float(pay.amount),
                "payer_name": pay.payer_name,
            } if pay else None,
        }
