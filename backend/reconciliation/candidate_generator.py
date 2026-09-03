"""
Finance Controller — Candidate Generator Module
===============================================

Generates plausible match candidates (Invoices, Settlements, Refunds) for a given
Payment transaction prior to final reconciliation scoring and decision making.

Key design principles:
  - Permissive candidate generation (high recall) using indexed SQL queries.
  - Amount proximity (exact match, fee deduction tolerance, partial payment band).
  - Date window filtering (configurable ±5 to ±15 days).
  - Normalized counterparty name similarity.
  - Support for many-to-one / split payments.
  - Composite candidate score ranking for downstream rule matching and AI agent evaluation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import List, Optional
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session, joinedload

from backend.models.payment import Payment
from backend.models.invoice import Invoice
from backend.models.settlement import Settlement
from backend.models.refund import Refund
from backend.reconciliation.normalizer import normalize_name


@dataclass
class InvoiceCandidate:
    invoice: Invoice
    composite_score: float
    amount_score: float
    date_score: float
    name_score: float
    match_type: str  # exact_amount | fee_deduction | partial_payment | fuzzy_name | direct_link
    notes: str


@dataclass
class SettlementCandidate:
    settlement: Settlement
    composite_score: float
    amount_score: float
    date_score: float
    match_type: str  # exact_gross | net_after_fee | date_drift | direct_link
    notes: str


@dataclass
class RefundCandidate:
    refund: Refund
    composite_score: float
    amount_score: float
    date_score: float
    match_type: str  # full_refund | chargeback | direct_link
    notes: str


@dataclass
class CandidateSet:
    payment: Payment
    invoices: List[InvoiceCandidate] = field(default_factory=list)
    settlements: List[SettlementCandidate] = field(default_factory=list)
    refunds: List[RefundCandidate] = field(default_factory=list)

    @property
    def total_candidates(self) -> int:
        return len(self.invoices) + len(self.settlements) + len(self.refunds)


class CandidateGenerator:
    """Indexed candidate generator for financial reconciliation."""

    def __init__(
        self,
        db_session: Session,
        date_window_days: int = 5,
        max_date_drift_days: int = 15,
        fee_tolerance_pct: float = 0.05,
    ):
        self.session = db_session
        self.date_window_days = date_window_days
        self.max_date_drift_days = max_date_drift_days
        self.fee_tolerance_pct = fee_tolerance_pct

    def generate_candidates(self, payment: Payment) -> CandidateSet:
        """Find all plausible invoice, settlement, and refund candidates for a payment."""
        candidate_set = CandidateSet(payment=payment)

        # 1. Generate Invoice Candidates
        candidate_set.invoices = self._find_invoice_candidates(payment)

        # 2. Generate Settlement Candidates
        candidate_set.settlements = self._find_settlement_candidates(payment)

        # 3. Generate Refund Candidates
        candidate_set.refunds = self._find_refund_candidates(payment)

        return candidate_set

    def _find_invoice_candidates(self, payment: Payment) -> List[InvoiceCandidate]:
        """Find candidate invoices using indexed query filters."""
        pay_date = payment.payment_date.date() if isinstance(payment.payment_date, datetime) else payment.payment_date
        start_date = pay_date - timedelta(days=self.max_date_drift_days)
        end_date = pay_date + timedelta(days=self.max_date_drift_days)

        pay_amt = float(payment.amount)
        min_amt = pay_amt * (1.0 - self.fee_tolerance_pct)
        max_amt = pay_amt * 10.0

        stmt = (
            select(Invoice)
            .options(joinedload(Invoice.customer))
            .where(
                and_(
                    Invoice.issue_date >= start_date,
                    Invoice.issue_date <= end_date,
                    or_(
                        Invoice.id == payment.invoice_id if payment.invoice_id else False,
                        Invoice.customer_id == payment.customer_id if payment.customer_id else False,
                        and_(Invoice.amount >= min_amt, Invoice.amount <= max_amt),
                    ),
                )
            )
        )
        invoices = self.session.scalars(stmt).unique().all()

        candidates: List[InvoiceCandidate] = []
        norm_payer = normalize_name(payment.payer_name)

        for inv in invoices:
            inv_amt = float(inv.amount)
            is_direct = payment.invoice_id == inv.id or (payment.customer_id and payment.customer_id == inv.customer_id)

            if abs(inv_amt - pay_amt) < 0.01:
                amount_score = 1.0
                match_type = "direct_link" if is_direct else "exact_amount"
                notes = "Exact amount match"
            elif inv_amt > pay_amt and abs((inv_amt - pay_amt) / inv_amt) < 0.9:
                amount_score = 0.85
                match_type = "partial_payment"
                notes = f"Payment ({pay_amt}) is partial contribution to invoice ({inv_amt})"
            elif abs(inv_amt - pay_amt) / pay_amt <= self.fee_tolerance_pct:
                amount_score = 0.90
                match_type = "fee_deduction"
                notes = f"Amount difference within fee tolerance band ({self.fee_tolerance_pct * 100}%)"
            else:
                amount_score = 0.50
                match_type = "amount_proximity"
                notes = "Broad amount proximity candidate"

            inv_date = inv.issue_date
            days_diff = abs((pay_date - inv_date).days)
            date_score = max(0.0, 1.0 - (days_diff / self.max_date_drift_days))

            name_score = 0.0
            if is_direct:
                name_score = 1.0
            elif inv.customer:
                norm_cust_name = normalize_name(inv.customer.name)
                norm_disp_name = normalize_name(inv.customer.display_name) if inv.customer.display_name else ""

                s1 = SequenceMatcher(None, norm_payer, norm_cust_name).ratio() if norm_payer and norm_cust_name else 0.0
                s2 = SequenceMatcher(None, norm_payer, norm_disp_name).ratio() if norm_payer and norm_disp_name else 0.0
                name_score = max(s1, s2)

                if name_score >= 0.70 and match_type == "amount_proximity":
                    match_type = "fuzzy_name"

            composite_score = round(
                (0.45 * amount_score) + (0.35 * date_score) + (0.20 * name_score), 4
            )

            if composite_score >= 0.35 or is_direct:
                candidates.append(
                    InvoiceCandidate(
                        invoice=inv,
                        composite_score=composite_score,
                        amount_score=round(amount_score, 4),
                        date_score=round(date_score, 4),
                        name_score=round(name_score, 4),
                        match_type=match_type,
                        notes=notes,
                    )
                )

        candidates.sort(key=lambda c: c.composite_score, reverse=True)
        return candidates

    def _find_settlement_candidates(self, payment: Payment) -> List[SettlementCandidate]:
        """Find candidate settlements for a payment."""
        pay_date = payment.payment_date.date() if isinstance(payment.payment_date, datetime) else payment.payment_date
        start_date = pay_date - timedelta(days=2)
        end_date = pay_date + timedelta(days=self.max_date_drift_days)

        pay_amt = float(payment.amount)
        min_gross = pay_amt * 0.85
        max_gross = pay_amt * 1.15

        stmt = select(Settlement).where(
            and_(
                Settlement.settlement_date >= start_date,
                Settlement.settlement_date <= end_date,
                or_(
                    Settlement.payment_id == payment.id,
                    and_(Settlement.gross_amount >= min_gross, Settlement.gross_amount <= max_gross),
                ),
            )
        )
        settlements = self.session.scalars(stmt).all()
        candidates: List[SettlementCandidate] = []

        for stl in settlements:
            gross = float(stl.gross_amount)
            net = float(stl.net_amount)
            fee = float(stl.fee)

            is_direct = stl.payment_id == payment.id
            stl_date = stl.settlement_date
            days_diff = abs((stl_date - pay_date).days)
            date_score = max(0.0, 1.0 - (days_diff / self.max_date_drift_days))

            if days_diff > 4:
                match_type = "date_drift"
                amount_score = 0.90 if (abs(gross - pay_amt) < 0.01 or is_direct) else 0.60
                notes = f"Settlement with {days_diff} days date drift beyond standard 2-day window"
            elif is_direct:
                match_type = "direct_link"
                amount_score = 1.0
                notes = "Direct payment_id link"
            elif abs(gross - pay_amt) < 0.01:
                amount_score = 1.0
                match_type = "exact_gross"
                notes = "Exact gross amount match"
            elif abs(net - (pay_amt - fee)) < 0.50 or abs(gross - pay_amt) / pay_amt <= 0.05:
                amount_score = 0.90
                match_type = "net_after_fee"
                notes = f"Gross/Net match with fee ({fee})"
            else:
                amount_score = 0.60
                match_type = "amount_proximity"
                notes = "Settlement amount proximity candidate"

            composite_score = round((0.60 * amount_score) + (0.40 * date_score), 4)

            if composite_score >= 0.40 or is_direct:
                candidates.append(
                    SettlementCandidate(
                        settlement=stl,
                        composite_score=composite_score,
                        amount_score=round(amount_score, 4),
                        date_score=round(date_score, 4),
                        match_type=match_type,
                        notes=notes,
                    )
                )

        candidates.sort(key=lambda c: c.composite_score, reverse=True)
        return candidates

    def _find_refund_candidates(self, payment: Payment) -> List[RefundCandidate]:
        """Find candidate refunds for a payment."""
        stmt = select(Refund).where(Refund.payment_id == payment.id)
        refunds = self.session.scalars(stmt).all()
        candidates: List[RefundCandidate] = []

        for rfnd in refunds:
            pay_amt = float(payment.amount)
            rfnd_amt = float(rfnd.amount)

            amount_score = 1.0 if abs(pay_amt - rfnd_amt) < 0.01 else 0.8
            date_score = 1.0
            match_type = "full_refund" if rfnd.refund_type == "refund" else "chargeback"

            candidates.append(
                RefundCandidate(
                    refund=rfnd,
                    composite_score=1.0,
                    amount_score=amount_score,
                    date_score=date_score,
                    match_type=match_type,
                    notes=f"Linked {match_type} record",
                )
            )

        return candidates
