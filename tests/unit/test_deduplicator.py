"""
Finance Controller — Deduplicator & Ingestion Unit Tests
========================================================

Tests exact duplicate re-ingestion, idempotency, audit logging,
and malformed record quarantining.
"""

import sys
import unittest
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.models.base import Base
from backend.models.payment import Payment
from backend.models.quarantine import QuarantineRecord
from backend.models.audit import AuditLog
from backend.reconciliation.deduplicator import DeduplicationPipeline, IngestionStatus


class TestDeduplicator(unittest.TestCase):

    def setUp(self):
        """Create in-memory SQLite database for isolated unit testing."""
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.pipeline = DeduplicationPipeline(self.session)

    def tearDown(self):
        self.session.close()

    def test_exact_duplicate_reingestion(self):
        """Re-ingesting the exact same payment twice must be idempotent and log an audit event."""
        payload = {
            "razorpay_payment_id": "pay_test_dup_12345",
            "amount": 2500.00,
            "currency": "INR",
            "payment_date": "2025-02-10",
            "payer_name": "Test Merchant Pvt Ltd",
        }

        # First ingestion -> SUCCESS
        status1, result1 = self.pipeline.process_record(payload, record_type="payment")
        self.assertEqual(status1, IngestionStatus.INGESTED)
        self.assertIsInstance(result1, Payment)

        # Count Payments in DB -> Should be 1
        payments_count = len(self.session.scalars(select(Payment)).all())
        self.assertEqual(payments_count, 1)

        # Second ingestion of IDENTICAL payload -> DUPLICATE
        status2, result2 = self.pipeline.process_record(payload, record_type="payment")
        self.assertEqual(status2, IngestionStatus.DUPLICATE)

        # Count Payments in DB -> STILL 1 (no duplicate row inserted)
        payments_count_after = len(self.session.scalars(select(Payment)).all())
        self.assertEqual(payments_count_after, 1)

        # Verify duplicate_detected audit log created
        audits = self.session.scalars(select(AuditLog).where(AuditLog.action == "duplicate_detected")).all()
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0].entity_type, "payment")
        self.assertIn("duplicate_detected", audits[0].action)

    def test_malformed_record_quarantine(self):
        """Malformed records (missing amount / unparseable date) must be quarantined, not crash."""
        malformed_payload = {
            "razorpay_payment_id": "pay_bad_999",
            "currency": "INR",
            "payment_date": "invalid-date-format",
            # missing amount
        }

        status, result = self.pipeline.process_record(malformed_payload, record_type="payment")
        self.assertEqual(status, IngestionStatus.QUARANTINED)
        self.assertIsInstance(result, QuarantineRecord)

        # Verify quarantine table has 1 record
        quarantined_records = self.session.scalars(select(QuarantineRecord)).all()
        self.assertEqual(len(quarantined_records), 1)
        self.assertEqual(quarantined_records[0].error_code, "MALFORMED_RECORD")
        self.assertIn("Missing required field: amount", quarantined_records[0].quarantine_reason)

        # Payments table should remain empty
        payments_count = len(self.session.scalars(select(Payment)).all())
        self.assertEqual(payments_count, 0)


if __name__ == "__main__":
    unittest.main()
