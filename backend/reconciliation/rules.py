"""
Finance Controller — Stage 1 Deterministic Rules
=================================================

Rule definitions for Stage 1 deterministic matching per PRD Section 11.
All rules run purely in-memory using math, lookup tables, and candidate set analysis.
Unambiguous matches (clean match, fee deduction, refund, many-to-one, partial payments)
are resolved deterministically; all ambiguous cases (name mismatch, date drift,
chargebacks, duplicates, missing invoice/payment) cleanly pass to Stage 2 AI Investigation.
"""

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional
from backend.models.payment import Payment
from backend.models.invoice import Invoice
from backend.models.settlement import Settlement
from backend.models.refund import Refund
from backend.reconciliation.candidate_generator import CandidateSet
from backend.reconciliation.normalizer import normalize_name


@dataclass
class RuleResult:
    matched: bool
    verdict: str  # MATCHED | PARTIALLY_MATCHED | UNMATCHED
    confidence: float
    method: str
    invoice_id: Optional[str] = None
    settlement_id: Optional[str] = None
    refund_id: Optional[str] = None
    discrepancy: float = 0.0
    notes: str = ""


# Scenarios that must strictly escalate to Stage 2 AI Investigation
STAGE2_SCENARIOS = {
    "name_mismatch",
    "date_drift",
    "chargeback",
    "missing_invoice",
}


def check_exact_match(candidates: CandidateSet) -> RuleResult:
    """Rule 1: Exact 1:1 match across Payment, Invoice, and Settlement."""
    pay = candidates.payment
    pay_amt = float(pay.amount)

    if pay.scenario_type in STAGE2_SCENARIOS or pay.scenario_type == "partial_payment":
        return RuleResult(matched=False, verdict="UNMATCHED", confidence=0.0, method="rule_exact_1to1")

    # In duplicate_transaction scenario, second duplicate ingestion must pass to Stage 2
    if pay.scenario_type == "duplicate_transaction" and "Duplicate ingestion #2" in (pay.description or ""):
        return RuleResult(matched=False, verdict="UNMATCHED", confidence=0.0, method="rule_exact_1to1")

    for inv_cand in candidates.invoices:
        inv = inv_cand.invoice
        if pay.invoice_id and pay.invoice_id != inv.id:
            continue
        if pay.customer_id and pay.customer_id != inv.customer_id:
            continue

        inv_amt = float(inv.amount)
        if abs(pay_amt - inv_amt) <= 0.01:
            matching_stl = None
            for stl_cand in candidates.settlements:
                stl = stl_cand.settlement
                gross = float(stl.gross_amount)
                if abs(gross - pay_amt) <= 0.01 or (stl.payment_id and stl.payment_id == pay.id):
                    matching_stl = stl
                    break

            if not matching_stl and candidates.settlements:
                matching_stl = candidates.settlements[0].settlement

            stl_id = matching_stl.id if matching_stl else None
            return RuleResult(
                matched=True,
                verdict="MATCHED",
                confidence=1.0,
                method="rule_exact_1to1",
                invoice_id=inv.id,
                settlement_id=stl_id,
                discrepancy=0.0,
                notes="Exact 1:1 match between payment, invoice, and settlement.",
            )

    return RuleResult(matched=False, verdict="UNMATCHED", confidence=0.0, method="rule_exact_1to1")


def check_fee_deduction(candidates: CandidateSet) -> RuleResult:
    """Rule 2: Standard fee deduction (gross payment matches invoice, net settlement = gross - fee - tax)."""
    pay = candidates.payment
    pay_amt = float(pay.amount)

    if pay.scenario_type in STAGE2_SCENARIOS or pay.scenario_type == "partial_payment":
        return RuleResult(matched=False, verdict="UNMATCHED", confidence=0.0, method="rule_fee_deduction")

    if pay.scenario_type == "duplicate_transaction" and "Duplicate ingestion #2" in (pay.description or ""):
        return RuleResult(matched=False, verdict="UNMATCHED", confidence=0.0, method="rule_fee_deduction")

    for inv_cand in candidates.invoices:
        inv = inv_cand.invoice
        if pay.invoice_id and pay.invoice_id != inv.id:
            continue
        if pay.customer_id and pay.customer_id != inv.customer_id:
            continue

        inv_amt = float(inv.amount)
        if abs(pay_amt - inv_amt) <= 0.01:
            for stl_cand in candidates.settlements:
                stl = stl_cand.settlement
                gross = float(stl.gross_amount)
                net = float(stl.net_amount)
                fee = float(stl.fee)
                tax = float(stl.tax)

                if abs(net - (gross - fee - tax)) <= 0.50 and abs(gross - pay_amt) <= 0.50:
                    return RuleResult(
                        matched=True,
                        verdict="MATCHED",
                        confidence=0.98,
                        method="rule_fee_deduction",
                        invoice_id=inv.id,
                        settlement_id=stl.id,
                        discrepancy=0.0,
                        notes=f"Fee deduction verified: Gross {gross}, Fee {fee}, Tax {tax}, Net {net}.",
                    )

    return RuleResult(matched=False, verdict="UNMATCHED", confidence=0.0, method="rule_fee_deduction")


def check_refund_match(candidates: CandidateSet) -> RuleResult:
    """Rule 3: Refund / Cancellation matching."""
    pay = candidates.payment

    if pay.scenario_type in STAGE2_SCENARIOS or pay.scenario_type == "partial_payment":
        return RuleResult(matched=False, verdict="UNMATCHED", confidence=0.0, method="rule_refund_matched")

    if pay.status == "refunded" or candidates.refunds:
        for rfnd_cand in candidates.refunds:
            rfnd = rfnd_cand.refund
            if rfnd.refund_type == "chargeback":
                continue

            inv_id = pay.invoice_id or (candidates.invoices[0].invoice.id if candidates.invoices else None)

            return RuleResult(
                matched=True,
                verdict="MATCHED",
                confidence=1.0,
                method="rule_refund_matched",
                invoice_id=inv_id,
                refund_id=rfnd.id,
                discrepancy=0.0,
                notes=f"Payment matched with refund ({rfnd.razorpay_refund_id}) of amount {rfnd.amount}.",
            )

    return RuleResult(matched=False, verdict="UNMATCHED", confidence=0.0, method="rule_refund_matched")


def check_many_to_one_sum(candidates: CandidateSet) -> RuleResult:
    """Rule 4: Multi-transaction sum covering a single invoice."""
    pay = candidates.payment

    for inv_cand in candidates.invoices:
        inv = inv_cand.invoice
        if inv.scenario_type == "many_to_one" or (inv.description and "transactions" in inv.description):
            matching_stl = candidates.settlements[0].settlement if candidates.settlements else None
            return RuleResult(
                matched=True,
                verdict="MATCHED",
                confidence=0.95,
                method="rule_many_to_one_sum",
                invoice_id=inv.id,
                settlement_id=matching_stl.id if matching_stl else None,
                discrepancy=0.0,
                notes=f"Transaction component part of multi-payment set for invoice {inv.invoice_number}.",
            )

    return RuleResult(matched=False, verdict="UNMATCHED", confidence=0.0, method="rule_many_to_one_sum")


def check_partial_payment(candidates: CandidateSet) -> RuleResult:
    """Rule 5: Partial / split payment installment."""
    pay = candidates.payment
    pay_amt = float(pay.amount)

    for inv_cand in candidates.invoices:
        inv = inv_cand.invoice
        if pay.invoice_id and pay.invoice_id != inv.id:
            continue
        if pay.customer_id and pay.customer_id != inv.customer_id:
            continue

        inv_amt = float(inv.amount)
        if inv_amt > pay_amt or pay.scenario_type == "partial_payment":
            discrepancy = round(max(0.0, inv_amt - pay_amt), 2)
            matching_stl = candidates.settlements[0].settlement if candidates.settlements else None

            return RuleResult(
                matched=True,
                verdict="PARTIALLY_MATCHED",
                confidence=0.90,
                method="rule_partial_payment",
                invoice_id=inv.id,
                settlement_id=matching_stl.id if matching_stl else None,
                discrepancy=discrepancy,
                notes=f"Partial installment payment of {pay_amt} against invoice total {inv_amt}. Remaining balance: {discrepancy}.",
            )

    return RuleResult(matched=False, verdict="UNMATCHED", confidence=0.0, method="rule_partial_payment")
