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


class TestInvestigatorEndpointAndOpenAIFlow(unittest.TestCase):
    """
    End-to-end integration tests for:
    Payment -> Reconciliation (Unresolved) -> Investigator Endpoint -> OpenAI -> Validated Result
    """

    def setUp(self):
        import json
        from unittest.mock import patch, MagicMock
        from fastapi.testclient import TestClient
        from backend.main import app
        from sqlalchemy.pool import StaticPool
        from backend.database.session import get_db
        from backend.reconciliation.matcher import Stage1Matcher

        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.SessionFactory = sessionmaker(bind=self.engine)
        self.session = self.SessionFactory()

        # Seed test entities
        self.cust = Customer(id="c_101", name="Acme India Pvt Ltd", display_name="Acme India")
        self.session.add(self.cust)

        self.inv = Invoice(
            id="inv_101", customer_id="c_101", invoice_number="INV-2025-101",
            amount=15000.0, issue_date=date(2025, 3, 1), status="paid",
        )
        self.pay = Payment(
            id="pay_101", razorpay_payment_id="pay_dc3111edc78c45", invoice_id="inv_101", customer_id="c_101",
            amount=15000.0, status="captured", payer_name="ACME INDIA PRIVATE LIMITED",
            payment_date=datetime(2025, 3, 1), scenario_type="name_mismatch",
        )
        self.stl = Settlement(
            id="stl_101", razorpay_settlement_id="set_101", payment_id="pay_101",
            gross_amount=15000.0, fee=300.0, tax=54.0, net_amount=14646.0, settlement_date=date(2025, 3, 3),
        )

        self.session.add_all([self.inv, self.pay, self.stl])
        self.session.commit()

        # Dependency override for FastAPI TestClient
        def override_get_db():
            db = self.SessionFactory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        from backend.main import app
        app.dependency_overrides.clear()
        self.session.close()

    def test_complete_flow_with_openai_mock(self):
        import json
        from unittest.mock import patch, MagicMock
        from backend.reconciliation.matcher import Stage1Matcher

        # 1. Run Stage 1 to produce unresolved case
        matcher = Stage1Matcher(self.session)
        s1_rec = matcher.process_payment(self.pay)
        self.assertEqual(s1_rec.match_status, "UNMATCHED")

        # 2. Call /api/v1/investigator/run with OpenAI mocked
        mock_openai_content = json.dumps({
            "candidate_cause": "name_mismatch",
            "explanation": "Payer name ACME INDIA PRIVATE LIMITED matches invoice customer Acme India via fuzzy matching.",
            "evidence_citations": ["inv_101", "stl_101"],
            "confidence": 0.98,
            "linked_invoice_id": "inv_101",
            "linked_settlement_id": "stl_101",
        })

        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_completion = MagicMock()
            mock_completion.choices = [
                MagicMock(message=MagicMock(content=mock_openai_content))
            ]
            mock_client.chat.completions.create.return_value = mock_completion

            # Call endpoint with payment_id
            resp = self.client.post(
                "/api/v1/investigator/run",
                json={"payment_id": "pay_dc3111edc78c45"},
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["reconciliation_id"], s1_rec.id)
            self.assertEqual(data["verdict"], "RESOLVED_AFTER_INVESTIGATION")
            self.assertTrue(data["validation_passed"])
            self.assertEqual(data["confidence"], 0.98)
            self.assertIn("inv_101", data["evidence_ids"])

            # Verify OpenAI client was invoked with expected model and schema
            mock_client.chat.completions.create.assert_called_once()
            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            self.assertEqual(call_kwargs["model"], "gpt-4o-mini")
            self.assertEqual(call_kwargs["response_format"], {"type": "json_object"})

    def test_endpoint_contract_with_reconciliation_id(self):
        from backend.reconciliation.matcher import Stage1Matcher
        matcher = Stage1Matcher(self.session)
        s1_rec = matcher.process_payment(self.pay)

        resp = self.client.post(
            "/api/v1/investigator/run",
            json={"reconciliation_id": s1_rec.id},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["reconciliation_id"], s1_rec.id)
        self.assertIn(data["verdict"], ["RESOLVED_AFTER_INVESTIGATION", "NEEDS_HUMAN_REVIEW", "EXCEPTION"])

    def test_endpoint_contract_with_both_ids(self):
        from backend.reconciliation.matcher import Stage1Matcher
        matcher = Stage1Matcher(self.session)
        s1_rec = matcher.process_payment(self.pay)

        resp = self.client.post(
            "/api/v1/investigator/run",
            json={
                "reconciliation_id": s1_rec.id,
                "payment_id": "pay_dc3111edc78c45",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["reconciliation_id"], s1_rec.id)

    def test_endpoint_invalid_ids(self):
        resp = self.client.post("/api/v1/investigator/run", json={"payment_id": "invalid_xyz"})
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.json()["detail"].lower())

        resp2 = self.client.post("/api/v1/investigator/run", json={"reconciliation_id": "invalid_rec_xyz"})
        self.assertEqual(resp2.status_code, 404)
        self.assertIn("not found", resp2.json()["detail"].lower())

        resp3 = self.client.post("/api/v1/investigator/run", json={})
        self.assertEqual(resp3.status_code, 400)


if __name__ == "__main__":
    unittest.main()
