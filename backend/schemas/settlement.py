"""
Finance Controller — Settlement API Schemas
===========================================

Pydantic schemas for Settlement endpoints.
"""

from datetime import date
from typing import List, Optional
from pydantic import BaseModel


class SettlementBase(BaseModel):
    razorpay_settlement_id: str
    gross_amount: float
    fee: float = 0.0
    tax: float = 0.0
    net_amount: float
    currency: str = "INR"
    status: str = "processed"
    utr: Optional[str] = None
    settlement_date: date


class SettlementItem(SettlementBase):
    id: str
    payment_id: Optional[str] = None

    class Config:
        from_attributes = True


class SettlementListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[SettlementItem]


class SettlementDetailResponse(SettlementItem):
    payment: Optional[dict] = None
