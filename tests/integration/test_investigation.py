"""
Finance Controller — Integration Tests for Stage 2 AI Investigation & Review
============================================================================
"""

import sys
import unittest
from datetime import datetime, date
from pathlib import Path
from sqlalchemy import create_engine, select
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
from backend.models.audit import AuditLog
from backend.models.reconciliation import ReconciliationRecord
from backend.agents.investigator import InvestigatorAgent
from backend.services.exception_service import ExceptionService
from backend.services.audit_service import AuditService


class TestInvestigationIntegration(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        self.cust = Customer(id="c_001", name="Acme Technologies Pvt Ltd", display_name="Acme Tech")
        self.session.add(self.cust)

        # 1. Name mismatch payment
        self.inv = Invoice(
            id="inv_001", customer_id="c_001", invoice_number="INV-2025-001",
            amount=8000.0, issue_date=date(2025, 3, 1), status="paid",
        )
        self.pay = Payment(
            id="pay_001", razorpay_payment_id="rzp_001", invoice_id="inv_001", customer_id="c_001",
            amount=8000.0, status="captured", payer_name="ACME TECHNOLOGIES PVT LTD",
            payment_date=datetime(2025, 3, 1), scenario_type="name_mismatch",
        )
        self.stl = Settlement(
            id="stl_001", razorpay_settlement_id="set_001", payment_id="pay_001",
            gross_amount=8000.0, fee=160.0, tax=28.8, net_amount=7811.2, settlement_date=date(2025, 3, 3),
        )

        self.session.add_all([self.inv, self.pay, self.stl])
        self.session.commit()

        self.investigator = InvestigatorAgent(self.session)
        self.exception_service = ExceptionService(self.session)
        self.audit_service = AuditService(self.session)

    def test_ai_investigation_resolves_name_mismatch(self):
        rec = self.investigator.investigate_payment(self.pay)
        self.assertEqual(rec.match_status, "RESOLVED_AFTER_INVESTIGATION")
        self.assertEqual(rec.stage, 2)
        self.assertEqual(rec.match_method, "AI_INVESTIGATION")

        # Verify audit logs created
        logs = self.session.scalars(
            select(AuditLog).where(AuditLog.entity_id == rec.id)
        ).all()
        actions = {l.action for l in logs}
        self.assertIn("AI_INVESTIGATION", actions)
        self.assertIn("EVIDENCE_VALIDATION", actions)
        self.assertIn("CONFIDENCE_ROUTING", actions)

    def test_human_review_override_workflow(self):
        # Create a case requiring review
        rec = ReconciliationRecord(
            id="rec_review_1",
            payment_id=self.pay.id,
            match_status="NEEDS_HUMAN_REVIEW",
            stage=2,
            payment_amount=8000.0,
        )
        self.session.add(rec)
        self.session.commit()

        # Submit specialist override
        res = self.exception_service.decide_review(
            reconciliation_id=rec.id,
            action="OVERRIDE",
            override_verdict="MATCHED",
            rationale="Verified bank UTR manually via customer statement.",
            reviewer_id="lead-specialist",
        )

        self.assertEqual(res["new_status"], "MATCHED")
        self.assertEqual(res["resolution_method"], "HUMAN_OVERRIDE")

        # Confirm audit entry was recorded
        audit_entry = self.session.get(AuditLog, res["audit_id"])
        self.assertIsNotNone(audit_entry)
        self.assertEqual(audit_entry.action, "HUMAN_REVIEW")
        self.assertIn("lead-specialist", audit_entry.actor)


if __name__ == "__main__":
    unittest.main()
