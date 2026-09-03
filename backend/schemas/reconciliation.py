"""
Finance Controller — Reconciliation API Schemas
================================================

Pydantic schemas for Reconciliation endpoints per PRD Section 16.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ReconciliationRunRequest(BaseModel):
    payment_id: Optional[str] = None
    batch_mode: bool = False
    max_records: Optional[int] = None


class ReconciliationRunResponse(BaseModel):
    reconciliation_id: Optional[str] = None
    payment_id: Optional[str] = None
    status: str
    resolution_method: str
    rule_matched: Optional[int] = None
    settlement_id: Optional[str] = None
    notes: Optional[str] = None
    processed_count: Optional[int] = None


class CandidateItem(BaseModel):
    settlement_id: Optional[str] = None
    invoice_id: Optional[str] = None
    net_amount: Optional[float] = None
    gross_amount: Optional[float] = None
    settled_at: Optional[str] = None
    source: str
    score: float
    notes: Optional[str] = None


class CandidateListResponse(BaseModel):
    payment_id: str
    candidates: List[CandidateItem] = Field(default_factory=list)


class ReconciliationRecordItem(BaseModel):
    id: str
    payment_id: Optional[str] = None
    invoice_id: Optional[str] = None
    settlement_id: Optional[str] = None
    match_status: str
    match_score: Optional[float] = None
    match_method: Optional[str] = None
    stage: Optional[int] = 1
    payment_amount: Optional[float] = None
    settlement_amount: Optional[float] = None
    discrepancy: Optional[float] = None
    notes: Optional[str] = None
    scenario_type: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReconciliationListResponse(BaseModel):
    total: int
    items: List[ReconciliationRecordItem]
