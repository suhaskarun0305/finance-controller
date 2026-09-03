"""
Finance Controller — Invoice Model
====================================

Represents an invoice issued by a merchant.
An invoice may have zero, one, or many associated payments.
"""

import uuid
from datetime import datetime, date

from sqlalchemy import String, DateTime, Date, Numeric, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    invoice_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False, index=True
    )

    fingerprint: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )  # SHA-256 fingerprint for deduplication

    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False
    )  # pending | paid | partial | overdue | cancelled
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

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
    customer = relationship("Customer", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Invoice(id={self.id!r}, number={self.invoice_number!r}, amount={self.amount})>"
