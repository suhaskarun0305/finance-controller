"""
Finance Controller — Exception & Review API Schemas
===================================================

Pydantic schemas for Exceptions and Human Review Workflows per PRD Section 14.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ReviewDecisionRequest(BaseModel):
    action: str  # ACCEPT | OVERRIDE | REQUEST_MORE_EVIDENCE
    override_verdict: Optional[str] = None  # MATCHED | EXCEPTION | null
    rationale: Optional[str] = None
    reviewer_id: str = "specialist-1"


class ReviewDecisionResponse(BaseModel):
    reconciliation_id: str
    new_status: str
    resolution_method: str
    audit_id: str


class ReviewQueueItem(BaseModel):
    reconciliation_id: str
    payment_id: Optional[str] = None
    razorpay_payment_id: str
    payer_name: Optional[str] = None
    amount_at_risk: float
    currency: str = "INR"
    confidence: float
    reason_code: str
    status: str
    created_at: str
    notes: Optional[str] = None


class ExceptionItem(BaseModel):
    id: str
    reconciliation_id: Optional[str] = None
    payment_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    amount: Optional[float] = None
    currency: str = "INR"
    exception_type: str
    severity: str
    status: str
    description: Optional[str] = None
    created_at: str
    resolved_at: Optional[str] = None


class ExceptionListResponse(BaseModel):
    total: int
    items: List[ExceptionItem]
