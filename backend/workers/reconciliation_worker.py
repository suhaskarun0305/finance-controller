"""
Finance Controller — Background Reconciliation Worker
=====================================================

Worker process for scheduled or event-driven asynchronous reconciliation passes.
Polls for unprocessed payments and dispatches them through Stage 1 deterministic
rules and Stage 2 AI investigation.
"""

import time
import logging
from sqlalchemy import select
from backend.database.session import SessionLocal
from backend.models.payment import Payment
from backend.models.reconciliation import ReconciliationRecord
from backend.reconciliation.matcher import Stage1Matcher
from backend.agents.investigator import InvestigatorAgent

logger = logging.getLogger("reconciliation_worker")
logging.basicConfig(level=logging.INFO)


class ReconciliationWorker:
    """Processes unreconciled payments in configurable batch sizes."""

    def __init__(self, batch_size: int = 50):
        self.batch_size = batch_size

    def run_cycle(self) -> dict:
        """Run a single cycle of 2-stage reconciliation."""
        session = SessionLocal()
        try:
            matcher = Stage1Matcher(session)
            investigator = InvestigatorAgent(session)

            # 1. Identify unreconciled payments
            subquery = select(ReconciliationRecord.payment_id).where(ReconciliationRecord.payment_id.isnot(None))
            stmt = (
                select(Payment)
                .where(Payment.id.notin_(subquery))
                .limit(self.batch_size)
            )
            payments = session.scalars(stmt).all()

            if not payments:
                logger.info("Worker idle: no unassigned payments.")
                return {"stage1_processed": 0, "stage2_processed": 0}

            logger.info(f"Processing batch of {len(payments)} payments in Stage 1...")
            unresolved = []
            for p in payments:
                rec = matcher.process_payment(p)
                if rec.match_status == "UNMATCHED":
                    unresolved.append(p)

            logger.info(f"Stage 1 completed. {len(unresolved)} cases escalating to Stage 2...")
            s2_count = 0
            for p in unresolved:
                investigator.investigate_payment(p)
                s2_count += 1

            logger.info(f"Cycle finished. Stage 1: {len(payments)}, Stage 2: {s2_count}")
            return {"stage1_processed": len(payments), "stage2_processed": s2_count}
        finally:
            session.close()


def run_forever(interval_seconds: int = 60):
    worker = ReconciliationWorker()
    logger.info("Reconciliation worker started.")
    while True:
        try:
            worker.run_cycle()
        except Exception as e:
            logger.error(f"Worker cycle error: {e}", exc_info=True)
        time.sleep(interval_seconds)


if __name__ == "__main__":
    run_forever()
