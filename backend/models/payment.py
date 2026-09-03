"""
Finance Controller — Payment (Transaction) Model
=================================================

Represents a payment transaction processed via Razorpay.
Links to an invoice (nullable — for "missing invoice" edge cases).
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Numeric, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    razorpay_payment_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    order_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    invoice_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("invoices.id"), nullable=True, index=True
    )
    customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=True, index=True
    )

    fingerprint: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )  # SHA-256 fingerprint for deduplication

    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # upi | card | netbanking | wallet | bank_transfer
    status: Mapped[str] = mapped_column(
        String(30), default="captured", nullable=False
    )  # authorized | captured | failed | refunded

    fee: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    tax: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)

    payer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    payment_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
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
    invoice = relationship("Invoice", back_populates="payments")
    customer = relationship("Customer", back_populates="payments")
    settlement = relationship("Settlement", back_populates="payment", uselist=False)
    refunds = relationship("Refund", back_populates="payment", lazy="dynamic")

    def __repr__(self) -> str:
        return (
            f"<Payment(id={self.id!r}, rzp_id={self.razorpay_payment_id!r}, "
            f"amount={self.amount}, status={self.status!r})>"
        )
