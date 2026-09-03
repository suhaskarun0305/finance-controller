"""
Finance Controller — Exception Record Model
============================================

Records exceptions raised during reconciliation that require
investigation (by a human or the AI investigator agent).
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class ExceptionRecord(Base):
    __tablename__ = "exception_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    reconciliation_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    payment_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    invoice_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    exception_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # amount_mismatch | missing_invoice | missing_payment | duplicate | date_drift
    severity: Mapped[str] = mapped_column(
        String(20), default="medium", nullable=False
    )  # low | medium | high | critical
    status: Mapped[str] = mapped_column(
        String(30), default="open", nullable=False
    )  # open | investigating | resolved | dismissed

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    scenario_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<ExceptionRecord(id={self.id!r}, type={self.exception_type!r}, "
            f"status={self.status!r})>"
        )
