"""
Finance Controller — AI Investigator & Metrics API Schemas
==========================================================

Pydantic schemas for AI Investigator and Dashboard Metrics per PRD Section 16 & 26.8.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class InvestigatorRunRequest(BaseModel):
    reconciliation_id: Optional[str] = None
    payment_id: Optional[str] = None


class InvestigatorRunResponse(BaseModel):
    reconciliation_id: str
    verdict: str
    reason: str
    confidence: float
    evidence_ids: List[str] = Field(default_factory=list)
    validation_passed: bool
    final_status: str
    explanation: Optional[str] = None


class TimelineStep(BaseModel):
    step: str
    summary: str
    actor: Optional[str] = None
    timestamp: Optional[str] = None
    input_snapshot: Optional[Dict[str, Any]] = None
    output_snapshot: Optional[Dict[str, Any]] = None
    evidence_refs: Optional[List[str]] = None


class CaseDetailResponse(BaseModel):
    reconciliation_id: str
    payment: Dict[str, Any]
    timeline: List[TimelineStep] = Field(default_factory=list)
    final_status: str
    notes: Optional[str] = None


class MetricsSummaryResponse(BaseModel):
    deterministic_match_rate: float
    ai_investigation_accuracy: float
    false_positive_rate: float
    false_negative_rate: float
    human_review_queue_rate: float
    throughput_per_min: int
    as_of: str


class MetricCard(BaseModel):
    title: str
    value: str
    target: str
    status: str  # OK | WARN | CRITICAL


class MetricsPanelResponse(BaseModel):
    panels: List[MetricCard]
