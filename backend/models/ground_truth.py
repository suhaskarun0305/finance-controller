"""
Finance Controller — Ground Truth Record Model
===============================================

Stores the objective ground truth for synthetic records generated in Step 3.
This table is kept strictly separate from the system's own reconciliation
decisions to ensure unbiased evaluation.
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, Float, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class GroundTruthRecord(Base):
    __tablename__ = "ground_truth_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    payment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("payments.id"), nullable=True, index=True
    )
    invoice_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("invoices.id"), nullable=True, index=True
    )
    settlement_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("settlements.id"), nullable=True, index=True
    )
    refund_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("refunds.id"), nullable=True, index=True
    )

    scenario_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    expected_verdict: Mapped[str] = mapped_column(
        String(40), nullable=False
    )  # MATCHED | PARTIALLY_MATCHED | RESOLVED_AFTER_INVESTIGATION | EXCEPTION

    expected_stage: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )  # 1 = Stage 1 Deterministic, 2 = Stage 2 AI Investigation

    expected_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    fee_breakup_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # --- Relationships ---
    payment = relationship("Payment", uselist=False)
    invoice = relationship("Invoice", uselist=False)
    settlement = relationship("Settlement", uselist=False)
    refund = relationship("Refund", uselist=False)

    def __repr__(self) -> str:
        return (
            f"<GroundTruthRecord(id={self.id!r}, scenario={self.scenario_type!r}, "
            f"expected={self.expected_verdict!r}, stage={self.expected_stage})>"
        )
