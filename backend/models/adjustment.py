"""
Finance Controller — Adjustment Model
=======================================

Represents manual adjustments or fee corrections applied to a payment
or settlement.
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Numeric, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class Adjustment(Base):
    __tablename__ = "adjustments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    payment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("payments.id"), nullable=True, index=True
    )
    settlement_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("settlements.id"), nullable=True, index=True
    )

    adjustment_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # fee_correction | manual_credit | manual_debit
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    scenario_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Adjustment(id={self.id!r}, type={self.adjustment_type!r}, amount={self.amount})>"
