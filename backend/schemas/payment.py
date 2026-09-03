"""
Finance Controller — Payment API Schemas
========================================

Pydantic schemas for Payment endpoints.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class PaymentBase(BaseModel):
    razorpay_payment_id: str
    amount: float
    currency: str = "INR"
    status: str = "captured"
    method: Optional[str] = None
    payer_name: Optional[str] = None
    payer_email: Optional[str] = None
    order_id: Optional[str] = None
    payment_date: datetime
    scenario_type: Optional[str] = None


class PaymentItem(PaymentBase):
    id: str
    invoice_id: Optional[str] = None
    customer_id: Optional[str] = None

    class Config:
        from_attributes = True


class PaymentListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[PaymentItem]


class PaymentDetailResponse(PaymentItem):
    fee: float = 0.0
    tax: float = 0.0
    invoice: Optional[dict] = None
    settlement: Optional[dict] = None
    refunds: List[dict] = Field(default_factory=list)
