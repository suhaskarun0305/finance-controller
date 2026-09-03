"""
Finance Controller — Evidence Service Module
============================================

Provides scoped, read-only evidence retrieval for Stage 2 AI Investigation.
Retrieves candidate sets, fee schedules, refund records, and prior human resolutions
for unresolved payment transactions.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session, joinedload

from backend.models.payment import Payment
from backend.models.invoice import Invoice
from backend.models.settlement import Settlement
from backend.models.refund import Refund
from backend.models.customer import Customer
from backend.reconciliation.candidate_generator import CandidateGenerator, CandidateSet
from backend.reconciliation.normalizer import normalize_name


@dataclass
class EvidencePackage:
    payment_id: str
    razorpay_payment_id: str
    amount: float
    currency: str
    payer_name: Optional[str]
    payer_email: Optional[str]
    payment_date: str
    scenario_type: Optional[str]

    # Scoped evidence collections
    candidate_invoices: List[Dict[str, Any]] = field(default_factory=list)
    candidate_settlements: List[Dict[str, Any]] = field(default_factory=list)
    refund_records: List[Dict[str, Any]] = field(default_factory=list)
    fee_schedule: Dict[str, Any] = field(default_factory=dict)
    prior_human_resolutions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EvidenceService:
    """Read-only evidence retrieval service for AI Agent investigation."""

    def __init__(self, db_session: Session):
        self.session = db_session
        self.candidate_generator = CandidateGenerator(db_session, date_window_days=15)

    def collect_evidence(self, payment: Payment) -> EvidencePackage:
        """Collect all relevant evidence records for an unresolved payment."""

        # 1. Base payment details
        pay_date_str = str(payment.payment_date)

        pkg = EvidencePackage(
            payment_id=payment.id,
            razorpay_payment_id=payment.razorpay_payment_id,
            amount=float(payment.amount),
            currency=payment.currency,
            payer_name=payment.payer_name,
            payer_email=payment.payer_email,
            payment_date=pay_date_str,
            scenario_type=payment.scenario_type,
        )

        # 2. Candidate set (invoices, settlements, refunds)
        candidate_set: CandidateSet = self.candidate_generator.generate_candidates(payment)

        for inv_c in candidate_set.invoices:
            inv = inv_c.invoice
            cust_name = inv.customer.name if inv.customer else "Unknown Merchant"
            pkg.candidate_invoices.append(
                {
                    "invoice_id": inv.id,
                    "invoice_number": inv.invoice_number,
                    "customer_id": inv.customer_id,
                    "customer_name": cust_name,
                    "amount": float(inv.amount),
                    "currency": inv.currency,
                    "status": inv.status,
                    "issue_date": str(inv.issue_date),
                    "match_type": inv_c.match_type,
                    "composite_score": inv_c.composite_score,
                    "name_score": inv_c.name_score,
                }
            )

        for stl_c in candidate_set.settlements:
            stl = stl_c.settlement
            pkg.candidate_settlements.append(
                {
                    "settlement_id": stl.id,
                    "razorpay_settlement_id": stl.razorpay_settlement_id,
                    "gross_amount": float(stl.gross_amount),
                    "fee": float(stl.fee),
                    "tax": float(stl.tax),
                    "net_amount": float(stl.net_amount),
                    "settlement_date": str(stl.settlement_date),
                    "utr": stl.utr,
                    "match_type": stl_c.match_type,
                    "composite_score": stl_c.composite_score,
                }
            )

        # 3. Refund & Chargeback Records
        for rfnd_c in candidate_set.refunds:
            rfnd = rfnd_c.refund
            pkg.refund_records.append(
                {
                    "refund_id": rfnd.id,
                    "razorpay_refund_id": rfnd.razorpay_refund_id,
                    "amount": float(rfnd.amount),
                    "refund_type": rfnd.refund_type,
                    "reason": rfnd.reason,
                    "refund_date": str(rfnd.refund_date),
                }
            )

        # 4. Standard Fee Schedule Metadata
        pkg.fee_schedule = {
            "standard_rate_pct": 2.0,
            "gst_on_fee_pct": 18.0,
            "elevated_rate_pct": 3.5,
            "description": "Razorpay Standard Merchant Fee Schedule (2.0% base + 18% GST; 3.5% elevated international/cards).",
        }

        # 5. Prior Human Resolutions (Stub for future feedback wiring)
        pkg.prior_human_resolutions = []

        return pkg
