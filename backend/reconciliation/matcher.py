"""
Finance Controller — Stage 1 Deterministic Matcher
===================================================

Runs fast, rule-based deterministic matching on incoming candidate sets.
Outputs verdicts (MATCHED, PARTIALLY_MATCHED, UNMATCHED) and persists
ReconciliationRecord entries into the database.

No AI/LLM calls are made in Stage 1. Unresolved cases are cleanly marked
as UNMATCHED (stage=1) to be passed through to Stage 2 AI Investigation.
"""

import time
from typing import List, Sequence
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.payment import Payment
from backend.models.reconciliation import ReconciliationRecord
from backend.reconciliation.candidate_generator import CandidateGenerator, CandidateSet
from backend.reconciliation.rules import (
    RuleResult,
    check_exact_match,
    check_fee_deduction,
    check_refund_match,
    check_many_to_one_sum,
    check_partial_payment,
)


class Stage1Matcher:
    """Stage 1 Deterministic Reconciliation Matcher."""

    def __init__(self, db_session: Session, date_window_days: int = 5):
        self.session = db_session
        self.candidate_generator = CandidateGenerator(db_session, date_window_days=date_window_days)

    def process_payment(self, payment: Payment) -> ReconciliationRecord:
        """Process a single payment transaction through Stage 1 deterministic rules."""
        start_time = time.perf_counter()

        # 1. Generate candidates
        candidate_set: CandidateSet = self.candidate_generator.generate_candidates(payment)

        # 2. Run rules sequentially
        rules_to_evaluate = [
            check_exact_match,
            check_fee_deduction,
            check_refund_match,
            check_many_to_one_sum,
            check_partial_payment,
        ]

        decision_result: Optional[RuleResult] = None

        for rule_fn in rules_to_evaluate:
            res: RuleResult = rule_fn(candidate_set)
            if res.matched:
                decision_result = res
                break

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        # 3. Formulate ReconciliationRecord persistence payload
        if decision_result and decision_result.matched:
            status = decision_result.verdict
            score = decision_result.confidence
            method = decision_result.method
            inv_id = decision_result.invoice_id
            stl_id = decision_result.settlement_id
            discrepancy = decision_result.discrepancy
            notes = decision_result.notes
        else:
            status = "UNMATCHED"
            score = 0.0
            method = "stage1_unresolved"
            inv_id = candidate_set.invoices[0].invoice.id if candidate_set.invoices else payment.invoice_id
            stl_id = candidate_set.settlements[0].settlement.id if candidate_set.settlements else None
            discrepancy = float(payment.amount)
            notes = "Unresolved in Stage 1 deterministic matching; queued for Stage 2 AI investigation."

        # Obtain settlement_amount if candidate exists
        stl_amount = float(candidate_set.settlements[0].settlement.net_amount) if candidate_set.settlements else None
        inv_amount = float(candidate_set.invoices[0].invoice.amount) if candidate_set.invoices else None

        rec_record = ReconciliationRecord(
            payment_id=payment.id,
            invoice_id=inv_id,
            settlement_id=stl_id,
            match_status=status,
            match_score=score,
            match_method=method,
            stage=1,
            processing_time_ms=elapsed_ms,
            payment_amount=float(payment.amount),
            invoice_amount=inv_amount,
            settlement_amount=stl_amount,
            discrepancy=discrepancy,
            notes=notes,
            scenario_type=payment.scenario_type,
        )

        self.session.add(rec_record)
        self.session.commit()
        return rec_record

    def process_all_payments(self) -> List[ReconciliationRecord]:
        """Process all payment records in database through Stage 1."""
        payments: Sequence[Payment] = self.session.scalars(select(Payment)).all()
        results: List[ReconciliationRecord] = []

        for p in payments:
            rec = self.process_payment(p)
            results.append(rec)

        return results
