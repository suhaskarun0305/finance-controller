"""
Finance Controller — Refund Model
==================================

Represents a refund or chargeback on a payment.
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Numeric, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    razorpay_refund_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    payment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payments.id"), nullable=False, index=True
    )

    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="processed", nullable=False
    )  # created | processed | failed
    refund_type: Mapped[str] = mapped_column(
        String(30), default="refund", nullable=False
    )  # refund | chargeback

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    refund_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    scenario_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # --- Relationships ---
    payment = relationship("Payment", back_populates="refunds")

    def __repr__(self) -> str:
        return (
            f"<Refund(id={self.id!r}, payment_id={self.payment_id!r}, "
            f"amount={self.amount}, type={self.refund_type!r})>"
        )
