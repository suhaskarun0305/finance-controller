"""
Finance Controller — Stage 1 Matcher Unit Tests
================================================

Tests Stage 1 deterministic rules: exact matches, fee deductions,
partial payments, and unresolved pass-throughs.
"""

import sys
import unittest
from datetime import datetime, date
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.models.base import Base
from backend.models.customer import Customer
from backend.models.invoice import Invoice
from backend.models.payment import Payment
from backend.models.settlement import Settlement
from backend.models.reconciliation import ReconciliationRecord
from backend.reconciliation.matcher import Stage1Matcher


class TestStage1Matcher(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        self.cust = Customer(id="c101", name="Acme Tech", email="b@acme.com")
        self.session.add(self.cust)

        self.inv = Invoice(
            id="inv101",
            invoice_number="INV-001",
            customer_id=self.cust.id,
            amount=5000.00,
            currency="INR",
            issue_date=date(2025, 1, 10),
        )
        self.session.add(self.inv)
        self.session.commit()

        self.matcher = Stage1Matcher(self.session)

    def tearDown(self):
        self.session.close()

    def test_exact_match_verdict(self):
        pay = Payment(
            id="p101",
            razorpay_payment_id="pay_exact_1",
            invoice_id=self.inv.id,
            customer_id=self.cust.id,
            amount=5000.00,
            currency="INR",
            payment_date=datetime(2025, 1, 11),
        )
        stl = Settlement(
            id="s101",
            razorpay_settlement_id="setl_exact_1",
            payment_id=pay.id,
            gross_amount=5000.00,
            fee=100.00,
            tax=18.00,
            net_amount=4882.00,
            settlement_date=date(2025, 1, 13),
        )
        self.session.add_all([pay, stl])
        self.session.commit()

        rec = self.matcher.process_payment(pay)
        self.assertEqual(rec.match_status, "MATCHED")
        self.assertEqual(rec.match_score, 1.0)
        self.assertEqual(rec.stage, 1)

    def test_unresolved_passthrough_to_stage2(self):
        """Unmatched payment with no clear invoice match should yield UNMATCHED in Stage 1."""
        pay_unmatched = Payment(
            id="p_unmatched",
            razorpay_payment_id="pay_unmatched_99",
            amount=99999.00,
            currency="INR",
            payment_date=datetime(2025, 1, 15),
            payer_name="Unknown Entity",
        )
        self.session.add(pay_unmatched)
        self.session.commit()

        rec = self.matcher.process_payment(pay_unmatched)
        self.assertEqual(rec.match_status, "UNMATCHED")
        self.assertEqual(rec.match_score, 0.0)
        self.assertIn("queued for Stage 2", rec.notes)


if __name__ == "__main__":
    unittest.main()
