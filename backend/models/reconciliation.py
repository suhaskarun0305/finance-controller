"""
Finance Controller — Reconciliation Record Model
=================================================

Tracks the result of each reconciliation attempt between payments,
invoices, and settlements.
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Numeric, Text, Float, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class ReconciliationRecord(Base):
    __tablename__ = "reconciliation_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    payment_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    invoice_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    settlement_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    match_status: Mapped[str] = mapped_column(
        String(40), nullable=False
    )  # MATCHED | PARTIALLY_MATCHED | RESOLVED_AFTER_INVESTIGATION | EXCEPTION | UNMATCHED
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_method: Mapped[str | None] = mapped_column(String(50), nullable=True)

    stage: Mapped[int | None] = mapped_column(Integer, default=1, nullable=True)  # 1 or 2
    processing_time_ms: Mapped[float | None] = mapped_column(Float, default=0.0, nullable=True)

    payment_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    invoice_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    settlement_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    discrepancy: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    scenario_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ReconciliationRecord(id={self.id!r}, status={self.match_status!r}, stage={self.stage})>"
