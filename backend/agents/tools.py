"""
Finance Controller — Stage 2 AI Agent Investigation Tools
==========================================================

Specialized domain tools and standard PRD Section 12.2 read-only tools used by
the AI Investigator Agent to resolve complex financial reconciliation exceptions.
"""

from dataclasses import dataclass
from datetime import datetime, date, timedelta
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session

from backend.models.customer import Customer
from backend.models.invoice import Invoice
from backend.models.payment import Payment
from backend.models.settlement import Settlement
from backend.models.refund import Refund
from backend.models.adjustment import Adjustment
from backend.reconciliation.normalizer import normalize_name


@dataclass
class InvestigationToolResult:
    tool_name: str
    success: bool
    confidence: float
    data: Dict[str, Any]
    reasoning: str


# =============================================================================
# PRD Section 12.2 Standard Read-Only Tools
# =============================================================================

class ReconciliationTools:
    """
    Standard read-only tools specified in Track 04 PRD Section 12.2.
    All operations are read-only and scoped to the active database session.
    """

    def __init__(self, db_session: Session):
        self.session = db_session

    def get_payment(self, payment_id: str) -> Dict[str, Any]:
        """Fetch full payment record by ID (UUID or Razorpay payment ID)."""
        stmt = select(Payment).where(
            or_(Payment.id == payment_id, Payment.razorpay_payment_id == payment_id)
        )
        pay = self.session.scalars(stmt).first()
        if not pay:
            return {"error_code": "NOT_FOUND", "message": f"Payment {payment_id} not found."}

        return {
            "id": pay.id,
            "razorpay_payment_id": pay.razorpay_payment_id,
            "amount": float(pay.amount),
            "currency": pay.currency,
            "paid_at": str(pay.payment_date),
            "order_ref": pay.order_id or pay.reference_number,
            "customer_id": pay.customer_id,
            "status": pay.status,
            "payer_name": pay.payer_name,
            "scenario_type": pay.scenario_type,
        }

    def get_settlement(self, settlement_id: str) -> Dict[str, Any]:
        """Fetch full settlement record by ID."""
        stmt = select(Settlement).where(
            or_(Settlement.id == settlement_id, Settlement.razorpay_settlement_id == settlement_id)
        )
        stl = self.session.scalars(stmt).first()
        if not stl:
            return {"error_code": "NOT_FOUND", "message": f"Settlement {settlement_id} not found."}

        return {
            "id": stl.id,
            "razorpay_settlement_id": stl.razorpay_settlement_id,
            "gross_amount": float(stl.gross_amount),
            "fee_amount": float(stl.fee),
            "tax_amount": float(stl.tax),
            "net_amount": float(stl.net_amount),
            "currency": stl.currency,
            "settled_at": str(stl.settlement_date),
            "settlement_ref": stl.utr or stl.razorpay_settlement_id,
            "status": stl.status,
            "payment_id": stl.payment_id,
        }

    def get_refunds(self, payment_id: str) -> List[Dict[str, Any]]:
        """List refunds for a payment."""
        stmt = select(Refund).where(Refund.payment_id == payment_id)
        refunds = self.session.scalars(stmt).all()
        return [
            {
                "id": r.id,
                "razorpay_refund_id": r.razorpay_refund_id,
                "amount": float(r.amount),
                "refunded_at": str(r.refund_date),
                "reason": r.reason,
                "payment_id": r.payment_id,
            }
            for r in refunds
        ]

    def get_adjustments(self, payment_id: str) -> List[Dict[str, Any]]:
        """List adjustments for a payment."""
        stmt = select(Adjustment).where(Adjustment.payment_id == payment_id)
        adjustments = self.session.scalars(stmt).all()
        return [
            {
                "id": a.id,
                "amount": float(a.amount),
                "adjustment_type": a.adjustment_type,
                "reason": a.reason,
                "created_at": str(a.created_at),
                "payment_id": a.payment_id,
            }
            for a in adjustments
        ]

    def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Fetch invoice linked to a payment."""
        stmt = select(Invoice).where(
            or_(Invoice.id == invoice_id, Invoice.invoice_number == invoice_id)
        )
        inv = self.session.scalars(stmt).first()
        if not inv:
            return {"error_code": "NOT_FOUND", "message": f"Invoice {invoice_id} not found."}

        return {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "amount": float(inv.amount),
            "currency": inv.currency,
            "status": inv.status,
            "customer_id": inv.customer_id,
            "issue_date": str(inv.issue_date),
        }

    def search_related_transactions(
        self,
        anchor_payment_id: str,
        amount_tolerance_pct: float = 0.05,
        date_window_days: int = 15,
    ) -> List[Dict[str, Any]]:
        """
        Search settlements and payments within a date/amount window near an anchor payment.
        Capped at 25 rows per PRD Section 12.2.
        """
        pay = self.session.get(Payment, anchor_payment_id)
        if not pay:
            return []

        pay_amt = float(pay.amount)
        min_amt = pay_amt * (1 - amount_tolerance_pct)
        max_amt = pay_amt * (1 + amount_tolerance_pct)

        pay_dt = pay.payment_date.date() if isinstance(pay.payment_date, datetime) else pay.payment_date
        start_d = pay_dt - timedelta(days=5)
        end_d = pay_dt + timedelta(days=date_window_days)

        results: List[Dict[str, Any]] = []

        # 1. Nearby settlements
        stl_stmt = select(Settlement).where(
            and_(
                Settlement.settlement_date >= start_d,
                Settlement.settlement_date <= end_d,
                Settlement.gross_amount >= min_amt,
                Settlement.gross_amount <= max_amt,
            )
        ).limit(15)
        for s in self.session.scalars(stl_stmt).all():
            results.append({
                "id": s.id,
                "type": "settlement",
                "amount": float(s.net_amount),
                "gross_amount": float(s.gross_amount),
                "date": str(s.settlement_date),
                "ref": s.razorpay_settlement_id,
            })

        # 2. Similar payments
        pay_stmt = select(Payment).where(
            and_(
                Payment.id != anchor_payment_id,
                Payment.payment_date >= datetime.combine(start_d, datetime.min.time()),
                Payment.payment_date <= datetime.combine(end_d, datetime.max.time()),
                Payment.amount >= min_amt,
                Payment.amount <= max_amt,
            )
        ).limit(10)
        for p in self.session.scalars(pay_stmt).all():
            results.append({
                "id": p.id,
                "type": "payment",
                "amount": float(p.amount),
                "date": str(p.payment_date),
                "ref": p.razorpay_payment_id,
            })

        return results[:25]

    def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """
        Fetch customer identity fields relevant to mismatch checks.
        Strictly redacts email and PII per PRD Section 19.3.
        """
        cust = self.session.get(Customer, customer_id)
        if not cust:
            return {"error_code": "NOT_FOUND", "message": f"Customer {customer_id} not found."}

        return {
            "id": cust.id,
            "external_ref": cust.id,
            "name": cust.name,
            "display_name": cust.display_name,
        }

    def list_evidence_by_ids(self, evidence_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Batch-fetch normalized evidence objects by ID.
        Resolves settlements, refunds, invoices, and payments.
        """
        evidence_list: List[Dict[str, Any]] = []
        for eid in evidence_ids:
            if not eid:
                continue

            # Check Settlement
            stl = self.session.get(Settlement, eid)
            if not stl:
                stl = self.session.scalars(
                    select(Settlement).where(Settlement.razorpay_settlement_id == eid)
                ).first()
            if stl:
                evidence_list.append({
                    "evidence_id": eid,
                    "type": "settlement",
                    "payload": {
                        "id": stl.id,
                        "payment_id": stl.payment_id,
                        "gross_amount": float(stl.gross_amount),
                        "fee_amount": float(stl.fee),
                        "tax_amount": float(stl.tax),
                        "net_amount": float(stl.net_amount),
                        "settled_at": str(stl.settlement_date),
                        "settlement_ref": stl.razorpay_settlement_id,
                    },
                })
                continue

            # Check Refund
            rfnd = self.session.get(Refund, eid)
            if not rfnd:
                rfnd = self.session.scalars(
                    select(Refund).where(Refund.razorpay_refund_id == eid)
                ).first()
            if rfnd:
                evidence_list.append({
                    "evidence_id": eid,
                    "type": "refund",
                    "payload": {
                        "id": rfnd.id,
                        "payment_id": rfnd.payment_id,
                        "amount": float(rfnd.amount),
                        "reason": rfnd.reason,
                        "refunded_at": str(rfnd.refund_date),
                    },
                })
                continue

            # Check Invoice
            inv = self.session.get(Invoice, eid)
            if not inv:
                inv = self.session.scalars(
                    select(Invoice).where(Invoice.invoice_number == eid)
                ).first()
            if inv:
                evidence_list.append({
                    "evidence_id": eid,
                    "type": "invoice",
                    "payload": {
                        "id": inv.id,
                        "amount": float(inv.amount),
                        "invoice_number": inv.invoice_number,
                        "customer_id": inv.customer_id,
                        "issue_date": str(inv.issue_date),
                    },
                })
                continue

            # Check Payment
            pay = self.session.get(Payment, eid)
            if not pay:
                pay = self.session.scalars(
                    select(Payment).where(Payment.razorpay_payment_id == eid)
                ).first()
            if pay:
                evidence_list.append({
                    "evidence_id": eid,
                    "type": "payment",
                    "payload": {
                        "id": pay.id,
                        "amount": float(pay.amount),
                        "razorpay_payment_id": pay.razorpay_payment_id,
                        "payment_date": str(pay.payment_date),
                    },
                })

        return evidence_list


# =============================================================================
# Specialized Domain Investigation Tools
# =============================================================================

class FuzzyNameTool:
    """Tool 1: Resolves merchant and counterparty name spelling variants."""

    def __init__(self, db_session: Session):
        self.session = db_session

    def run(self, payer_name: str, target_customer_id: Optional[str] = None) -> InvestigationToolResult:
        norm_payer = normalize_name(payer_name)
        if not norm_payer:
            return InvestigationToolResult(
                tool_name="FuzzyNameTool",
                success=False,
                confidence=0.0,
                data={},
                reasoning="Empty payer name provided for fuzzy lookup.",
            )

        customers = self.session.scalars(select(Customer)).all()
        best_match: Optional[Customer] = None
        best_ratio = 0.0

        for cust in customers:
            n1 = normalize_name(cust.name)
            n2 = normalize_name(cust.display_name) if cust.display_name else ""

            r1 = SequenceMatcher(None, norm_payer, n1).ratio() if n1 else 0.0
            r2 = SequenceMatcher(None, norm_payer, n2).ratio() if n2 else 0.0
            max_r = max(r1, r2)

            if max_r > best_ratio:
                best_ratio = max_r
                best_match = cust

        if best_match and best_ratio >= 0.65:
            return InvestigationToolResult(
                tool_name="FuzzyNameTool",
                success=True,
                confidence=round(best_ratio, 4),
                data={
                    "customer_id": best_match.id,
                    "customer_name": best_match.name,
                    "matched_variant": payer_name,
                    "similarity_ratio": round(best_ratio, 4),
                },
                reasoning=f"Resolved name '{payer_name}' to merchant '{best_match.name}' with {round(best_ratio * 100, 1)}% fuzzy similarity.",
            )

        return InvestigationToolResult(
            tool_name="FuzzyNameTool",
            success=False,
            confidence=0.0,
            data={},
            reasoning=f"No matching merchant found for name '{payer_name}'. Best ratio: {round(best_ratio, 2)}.",
        )


class ExpandedDateWindowTool:
    """Tool 2: Searches for delayed settlements/invoices within an expanded ±30-day window."""

    def __init__(self, db_session: Session):
        self.session = db_session

    def run(self, payment: Payment, max_window_days: int = 30) -> InvestigationToolResult:
        pay_date = payment.payment_date.date() if isinstance(payment.payment_date, datetime) else payment.payment_date
        start_date = pay_date - timedelta(days=5)
        end_date = pay_date + timedelta(days=max_window_days)
        pay_amt = float(payment.amount)

        stmt = select(Settlement).where(
            and_(
                Settlement.settlement_date >= start_date,
                Settlement.settlement_date <= end_date,
                or_(
                    Settlement.payment_id == payment.id,
                    and_(
                        Settlement.gross_amount >= pay_amt * 0.95,
                        Settlement.gross_amount <= pay_amt * 1.05,
                    ),
                ),
            )
        )
        settlements = self.session.scalars(stmt).all()

        if settlements:
            best_stl = settlements[0]
            days_drift = abs((best_stl.settlement_date - pay_date).days)
            return InvestigationToolResult(
                tool_name="ExpandedDateWindowTool",
                success=True,
                confidence=0.90,
                data={
                    "settlement_id": best_stl.id,
                    "razorpay_settlement_id": best_stl.razorpay_settlement_id,
                    "settlement_date": str(best_stl.settlement_date),
                    "days_drift": days_drift,
                    "gross_amount": float(best_stl.gross_amount),
                    "net_amount": float(best_stl.net_amount),
                },
                reasoning=f"Located delayed settlement ({best_stl.razorpay_settlement_id}) with {days_drift}-day date drift.",
            )

        return InvestigationToolResult(
            tool_name="ExpandedDateWindowTool",
            success=False,
            confidence=0.0,
            data={},
            reasoning=f"No settlement found for payment within expanded {max_window_days}-day window.",
        )


class ChargebackEvidenceTool:
    """Tool 3: Analyzes chargebacks and card network dispute records."""

    def __init__(self, db_session: Session):
        self.session = db_session

    def run(self, payment: Payment) -> InvestigationToolResult:
        stmt = select(Refund).where(
            and_(Refund.payment_id == payment.id, Refund.refund_type == "chargeback")
        )
        chargebacks = self.session.scalars(stmt).all()

        if chargebacks:
            cb = chargebacks[0]
            return InvestigationToolResult(
                tool_name="ChargebackEvidenceTool",
                success=True,
                confidence=0.95,
                data={
                    "chargeback_id": cb.id,
                    "razorpay_refund_id": cb.razorpay_refund_id,
                    "amount": float(cb.amount),
                    "reason": cb.reason,
                    "refund_date": str(cb.refund_date),
                },
                reasoning=f"Identified active chargeback dispute: {cb.reason} for amount {cb.amount}.",
            )

        return InvestigationToolResult(
            tool_name="ChargebackEvidenceTool",
            success=False,
            confidence=0.0,
            data={},
            reasoning="No chargeback record found for payment.",
        )


class MissingInvoiceTool:
    """Tool 4: Locates or suggests customer/invoice linkage for unmatched payments."""

    def __init__(self, db_session: Session):
        self.session = db_session

    def run(self, payment: Payment) -> InvestigationToolResult:
        if payment.customer_id:
            stmt = select(Invoice).where(
                and_(Invoice.customer_id == payment.customer_id, Invoice.status != "paid")
            )
            invoices = self.session.scalars(stmt).all()
            if invoices:
                best_inv = invoices[0]
                return InvestigationToolResult(
                    tool_name="MissingInvoiceTool",
                    success=True,
                    confidence=0.85,
                    data={
                        "invoice_id": best_inv.id,
                        "invoice_number": best_inv.invoice_number,
                        "customer_id": payment.customer_id,
                        "invoice_amount": float(best_inv.amount),
                    },
                    reasoning=f"Matched payment to open customer invoice {best_inv.invoice_number}.",
                )

        # Name lookup fallback
        norm_payer = normalize_name(payment.payer_name)
        if norm_payer:
            fuzzy_tool = FuzzyNameTool(self.session)
            name_res = fuzzy_tool.run(payment.payer_name)
            if name_res.success:
                cust_id = name_res.data["customer_id"]
                stmt = select(Invoice).where(Invoice.customer_id == cust_id)
                invoices = self.session.scalars(stmt).all()
                if invoices:
                    best_inv = invoices[0]
                    return InvestigationToolResult(
                        tool_name="MissingInvoiceTool",
                        success=True,
                        confidence=0.80,
                        data={
                            "invoice_id": best_inv.id,
                            "invoice_number": best_inv.invoice_number,
                            "customer_id": cust_id,
                            "invoice_amount": float(best_inv.amount),
                        },
                        reasoning=f"Found merchant '{name_res.data['customer_name']}' invoice {best_inv.invoice_number} via fuzzy name match.",
                    )

        return InvestigationToolResult(
            tool_name="MissingInvoiceTool",
            success=False,
            confidence=0.0,
            data={},
            reasoning="Unmatched payment with no corresponding open invoice found.",
        )


class DuplicateDetectorTool:
    """Tool 5: Confirms duplicate transaction ingestions vs legitimate recurring charges."""

    def __init__(self, db_session: Session):
        self.session = db_session

    def run(self, payment: Payment) -> InvestigationToolResult:
        stmt = select(Payment).where(
            and_(
                Payment.razorpay_payment_id == payment.razorpay_payment_id,
                Payment.id != payment.id,
            )
        )
        duplicates = self.session.scalars(stmt).all()

        if duplicates:
            original = duplicates[0]
            return InvestigationToolResult(
                tool_name="DuplicateDetectorTool",
                success=True,
                confidence=1.0,
                data={
                    "original_payment_id": original.id,
                    "duplicate_payment_id": payment.id,
                    "shared_razorpay_id": payment.razorpay_payment_id,
                },
                reasoning=f"Confirmed duplicate ingestion of payment {payment.razorpay_payment_id}. Original payment ID: {original.id}.",
            )

        return InvestigationToolResult(
            tool_name="DuplicateDetectorTool",
            success=False,
            confidence=0.0,
            data={},
            reasoning="No duplicate transaction ingestion detected.",
        )
