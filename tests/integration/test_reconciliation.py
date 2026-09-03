"""
Finance Controller — Integration Tests for Stage 1 Deterministic Reconciliation
==============================================================================
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
from backend.reconciliation.matcher import Stage1Matcher


class TestReconciliationIntegration(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        # Seed Merchant
        self.cust = Customer(id="c_001", name="Merchant Alpha", display_name="Alpha")
        self.session.add(self.cust)

        # 1. Clean match scenario
        self.inv1 = Invoice(id="inv_001", invoice_number="INV-001", customer_id="c_001", amount=5000.0, issue_date=date(2025, 3, 1), status="paid")
        self.pay1 = Payment(id="pay_001", razorpay_payment_id="rzp_001", invoice_id="inv_001", customer_id="c_001",
                            amount=5000.0, status="captured", payment_date=datetime(2025, 3, 1), scenario_type="clean_match")
        self.stl1 = Settlement(id="stl_001", razorpay_settlement_id="set_001", payment_id="pay_001",
                               gross_amount=5000.0, fee=100.0, tax=18.0, net_amount=4882.0, settlement_date=date(2025, 3, 2))

        # 2. Fee deduction scenario
        self.inv2 = Invoice(id="inv_002", invoice_number="INV-002", customer_id="c_001", amount=10000.0, issue_date=date(2025, 3, 1), status="paid")
        self.pay2 = Payment(id="pay_002", razorpay_payment_id="rzp_002", invoice_id="inv_002", customer_id="c_001",
                            amount=10000.0, status="captured", payment_date=datetime(2025, 3, 1), scenario_type="fee_deduction")
        self.stl2 = Settlement(id="stl_002", razorpay_settlement_id="set_002", payment_id="pay_002",
                               gross_amount=10000.0, fee=350.0, tax=63.0, net_amount=9587.0, settlement_date=date(2025, 3, 3))

        # 3. Date drift scenario (must escalate to Stage 2)
        self.inv3 = Invoice(id="inv_003", invoice_number="INV-003", customer_id="c_001", amount=7500.0, issue_date=date(2025, 3, 1), status="paid")
        self.pay3 = Payment(id="pay_003", razorpay_payment_id="rzp_003", invoice_id="inv_003", customer_id="c_001",
                            amount=7500.0, status="captured", payment_date=datetime(2025, 3, 1), scenario_type="date_drift")
        self.stl3 = Settlement(id="stl_003", razorpay_settlement_id="set_003", payment_id="pay_003",
                               gross_amount=7500.0, fee=150.0, tax=27.0, net_amount=7323.0, settlement_date=date(2025, 3, 25))

        self.session.add_all([self.inv1, self.pay1, self.stl1, self.inv2, self.pay2, self.stl2, self.inv3, self.pay3, self.stl3])
        self.session.commit()

        self.matcher = Stage1Matcher(self.session)

    def test_clean_match_resolves_deterministic_stage1(self):
        rec = self.matcher.process_payment(self.pay1)
        self.assertEqual(rec.match_status, "MATCHED")
        self.assertEqual(rec.stage, 1)
        self.assertIn("Exact", rec.notes)

    def test_fee_deduction_resolves_deterministic_stage1(self):
        rec = self.matcher.process_payment(self.pay2)
        self.assertEqual(rec.match_status, "MATCHED")
        self.assertEqual(rec.stage, 1)

    def test_date_drift_escalates_to_stage2(self):
        rec = self.matcher.process_payment(self.pay3)
        self.assertEqual(rec.match_status, "UNMATCHED")
        self.assertEqual(rec.stage, 1)
        self.assertIn("queued for Stage 2", rec.notes)


if __name__ == "__main__":
    unittest.main()
