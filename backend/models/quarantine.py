"""
Finance Controller — Quarantine Record Model
============================================

Stores malformed or incomplete records that fail ingestion validation.
Quarantining prevents invalid data from crashing the ingestion pipeline or
corrupting database tables.
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class QuarantineRecord(Base):
    __tablename__ = "quarantine_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    record_type: Mapped[str] = mapped_column(String(50), nullable=False)  # payment | invoice | settlement
    raw_payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    quarantine_reason: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str] = mapped_column(String(50), nullable=False, default="MALFORMED_RECORD")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<QuarantineRecord(id={self.id!r}, type={self.record_type!r}, "
            f"code={self.error_code!r})>"
        )
