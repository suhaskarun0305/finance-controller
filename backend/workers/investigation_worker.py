"""
Finance Controller — Investigation Background Worker
=====================================================

Asynchronous worker for processing Stage 2 AI investigations in the background.
Designed to be invoked from the reconciliation API endpoints for non-blocking
batch processing of unresolved payments.
"""

import time
import logging
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.payment import Payment
from backend.models.reconciliation import ReconciliationRecord
from backend.agents.investigator import InvestigatorAgent

logger = logging.getLogger(__name__)


class InvestigationWorker:
    """
    Background worker for batch Stage 2 AI investigation processing.

    Processes unresolved payments (those with UNMATCHED status from Stage 1)
    through the InvestigatorAgent pipeline: evidence collection, structured
    reasoning, 6-point evidence gating, confidence routing, and audit logging.
    """

    def __init__(self, db_session: Session, api_key: Optional[str] = None):
        self.session = db_session
        self.investigator = InvestigatorAgent(db_session, api_key=api_key)

    def process_unresolved(
        self,
        payment_ids: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[ReconciliationRecord]:
        """
        Process unresolved payments through Stage 2 AI investigation.

        Args:
            payment_ids: Optional list of specific payment IDs to investigate.
                         If None, fetches all UNMATCHED reconciliation records.
            limit: Maximum number of payments to process in this batch.

        Returns:
            List of updated ReconciliationRecord objects.
        """
        start_time = time.perf_counter()
        results: List[ReconciliationRecord] = []

        if payment_ids:
            # Process specific payments
            payments = self.session.scalars(
                select(Payment).where(Payment.id.in_(payment_ids)).limit(limit)
            ).all()
        else:
            # Find all payments with UNMATCHED reconciliation records
            unmatched_payment_ids = self.session.scalars(
                select(ReconciliationRecord.payment_id).where(
                    ReconciliationRecord.match_status == "UNMATCHED"
                ).limit(limit)
            ).all()

            if not unmatched_payment_ids:
                logger.info("No unresolved payments found for investigation.")
                return results

            payments = self.session.scalars(
                select(Payment).where(Payment.id.in_(unmatched_payment_ids))
            ).all()

        logger.info(f"Starting Stage 2 investigation for {len(payments)} payments.")

        for i, payment in enumerate(payments, 1):
            try:
                rec = self.investigator.investigate_payment(payment)
                results.append(rec)
                logger.info(
                    f"[{i}/{len(payments)}] Payment {payment.razorpay_payment_id}: "
                    f"{rec.match_status} (confidence={rec.match_score:.2f})"
                )
            except Exception as e:
                logger.error(
                    f"[{i}/{len(payments)}] Failed to investigate payment "
                    f"{payment.razorpay_payment_id}: {e}"
                )

        elapsed = time.perf_counter() - start_time
        throughput = len(results) / elapsed if elapsed > 0 else 0.0

        logger.info(
            f"Stage 2 investigation complete: {len(results)}/{len(payments)} processed "
            f"in {elapsed:.2f}s ({throughput:.1f} rec/sec)"
        )

        return results

    def process_single(self, payment_id: str) -> Optional[ReconciliationRecord]:
        """
        Investigate a single payment.

        Args:
            payment_id: The payment UUID to investigate.

        Returns:
            Updated ReconciliationRecord, or None if payment not found.
        """
        payment = self.session.get(Payment, payment_id)
        if not payment:
            logger.warning(f"Payment {payment_id} not found.")
            return None

        try:
            return self.investigator.investigate_payment(payment)
        except Exception as e:
            logger.error(f"Investigation failed for {payment_id}: {e}")
            return None
