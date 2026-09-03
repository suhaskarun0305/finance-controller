"""
Finance Controller — Candidate Generator Unit Tests
===================================================

Tests candidate surfacing for clean matches, split/partial payments,
near-duplicate name variants, and date drift edge cases.
"""

import sys
import unittest
from datetime import datetime, date, timedelta
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
from backend.models.refund import Refund
from backend.reconciliation.candidate_generator import CandidateGenerator


class TestCandidateGenerator(unittest.TestCase):

    def setUp(self):
        """Set up in-memory database and seed test edge cases."""
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        # Seed Merchant
        self.cust = Customer(
            id="cust_acme_100",
            name="Acme Technologies Pvt Ltd",
            display_name="Acme Tech Pvt. Ltd.",
            email="billing@acme.in",
        )
        self.session.add(self.cust)

        # 1. Clean Match Invoice
        self.inv_clean = Invoice(
            id="inv_clean_1",
            invoice_number="INV-2025-00101",
            customer_id=self.cust.id,
            amount=10000.00,
            currency="INR",
            issue_date=date(2025, 2, 1),
        )
        self.session.add(self.inv_clean)

        # 2. Split Payment Invoice (Total: 20,000 INR)
        self.inv_split = Invoice(
            id="inv_split_1",
            invoice_number="INV-2025-00102",
            customer_id=self.cust.id,
            amount=20000.00,
            currency="INR",
            issue_date=date(2025, 2, 5),
        )
        self.session.add(self.inv_split)

        # 3. Near-Duplicate Name Invoice
        self.cust2 = Customer(
            id="cust_cloud_200",
            name="CloudServe Solutions Pvt Ltd",
            display_name="CloudServe",
        )
        self.session.add(self.cust2)

        self.inv_name_mismatch = Invoice(
            id="inv_name_1",
            invoice_number="INV-2025-00103",
            customer_id=self.cust2.id,
            amount=15000.00,
            currency="INR",
            issue_date=date(2025, 2, 10),
        )
        self.session.add(self.inv_name_mismatch)

        self.session.commit()
        self.generator = CandidateGenerator(self.session)

    def tearDown(self):
        self.session.close()

    def test_clean_match_candidate_surfacing(self):
        """Exact amount and matching customer_id must rank as top invoice candidate."""
        pay = Payment(
            id="pay_clean_1",
            razorpay_payment_id="pay_rzp_clean_1",
            invoice_id=self.inv_clean.id,
            customer_id=self.cust.id,
            amount=10000.00,
            currency="INR",
            payment_date=datetime(2025, 2, 2, 10, 0),
            payer_name="Acme Technologies Pvt Ltd",
        )
        self.session.add(pay)
        self.session.commit()

        candidates = self.generator.generate_candidates(pay)
        self.assertGreaterEqual(candidates.total_candidates, 1)

        top_candidate = candidates.invoices[0]
        self.assertEqual(top_candidate.invoice.id, self.inv_clean.id)
        self.assertGreaterEqual(top_candidate.composite_score, 0.90)

    def test_split_payment_candidate_surfacing(self):
        """Installment payment (7,000 INR) must surface partial match candidate for 20,000 INR invoice."""
        pay_installment = Payment(
            id="pay_split_part1",
            razorpay_payment_id="pay_rzp_split_1",
            customer_id=self.cust.id,
            amount=7000.00,  # Part payment against 20,000 invoice
            currency="INR",
            payment_date=datetime(2025, 2, 6, 11, 0),
            payer_name="Acme Technologies",
        )
        self.session.add(pay_installment)
        self.session.commit()

        candidates = self.generator.generate_candidates(pay_installment)

        # Confirm inv_split is surfaced as a candidate
        surfaced_inv_ids = [c.invoice.id for c in candidates.invoices]
        self.assertIn(self.inv_split.id, surfaced_inv_ids)

        # Locate candidate object for inv_split
        split_cand = next(c for c in candidates.invoices if c.invoice.id == self.inv_split.id)
        self.assertEqual(split_cand.match_type, "partial_payment")

    def test_near_duplicate_name_candidate_surfacing(self):
        """Payer name variant ('Cloud Serve Solutions') must match invoice for 'CloudServe Solutions Pvt Ltd'."""
        pay_variant = Payment(
            id="pay_name_variant",
            razorpay_payment_id="pay_rzp_variant_1",
            customer_id=self.cust2.id,
            amount=15000.00,
            currency="INR",
            payment_date=datetime(2025, 2, 11, 14, 0),
            payer_name="Cloud Serve Solutions Co.",  # Variant spelling
        )
        self.session.add(pay_variant)
        self.session.commit()

        candidates = self.generator.generate_candidates(pay_variant)
        self.assertGreaterEqual(len(candidates.invoices), 1)

        name_cand = candidates.invoices[0]
        self.assertEqual(name_cand.invoice.id, self.inv_name_mismatch.id)
        self.assertGreater(name_cand.name_score, 0.70)

    def test_date_drift_settlement_surfacing(self):
        """Delayed settlement (10 days after payment) must be surfaced under expanded date window."""
        pay = Payment(
            id="pay_drift_1",
            razorpay_payment_id="pay_rzp_drift_1",
            amount=5000.00,
            currency="INR",
            payment_date=datetime(2025, 2, 1, 10, 0),
        )
        self.session.add(pay)

        stl_drifted = Settlement(
            id="stl_drift_1",
            razorpay_settlement_id="setl_rzp_drift_1",
            payment_id=pay.id,
            gross_amount=5000.00,
            fee=100.00,
            tax=18.00,
            net_amount=4882.00,
            settlement_date=date(2025, 2, 11),  # 10 days drift
        )
        self.session.add(stl_drifted)
        self.session.commit()

        candidates = self.generator.generate_candidates(pay)
        self.assertEqual(len(candidates.settlements), 1)

        stl_cand = candidates.settlements[0]
        self.assertEqual(stl_cand.settlement.id, stl_drifted.id)
        self.assertEqual(stl_cand.match_type, "date_drift")


if __name__ == "__main__":
    unittest.main()
