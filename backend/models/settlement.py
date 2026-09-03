"""
Finance Controller — Settlement Model
======================================

Represents a settlement record — money transferred from Razorpay to a
merchant's bank account.  The settlement amount is usually the payment
amount minus processing fees (gross vs. net).
"""

import uuid
from datetime import datetime, date

from sqlalchemy import String, DateTime, Date, Numeric, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    razorpay_settlement_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    payment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("payments.id"), nullable=True, index=True
    )

    fingerprint: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )  # SHA-256 fingerprint for deduplication

    gross_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    fee: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    tax: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    net_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    status: Mapped[str] = mapped_column(
        String(30), default="processed", nullable=False
    )  # created | processed | failed
    utr: Mapped[str | None] = mapped_column(String(100), nullable=True)

    settlement_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scenario_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # --- Relationships ---
    payment = relationship("Payment", back_populates="settlement")

    def __repr__(self) -> str:
        return (
            f"<Settlement(id={self.id!r}, rzp_id={self.razorpay_settlement_id!r}, "
            f"net={self.net_amount})>"
        )
