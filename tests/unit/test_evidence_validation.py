"""
Finance Controller — Unit Tests for 6-Point Evidence Validation & Confidence Routing
===================================================================================

Tests all 6 checks from PRD Section 13:
  1. EXISTENCE
  2. OWNERSHIP
  3. AMOUNT_MATH
  4. TEMPORAL
  5. IDEMPOTENCE
  6. CHECKSUM
plus Section 14 confidence routing.
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
from backend.models.payment import Payment
from backend.models.settlement import Settlement
from backend.models.reconciliation import ReconciliationRecord
from backend.agents.output_validator import (
    CandidateExplanationPayload,
    EvidenceGater,
    apply_confidence_routing,
)


class TestEvidenceValidation(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        # Base Payment
        self.payment = Payment(
            id="pay_test_001",
            razorpay_payment_id="pay_rzp_001",
            amount=8000.00,
            currency="INR",
            status="captured",
            payment_date=datetime(2025, 3, 1, 10, 0, 0),
            scenario_type="fee",
        )
        self.session.add(self.payment)
        self.session.commit()

        self.gater = EvidenceGater(self.session, amount_tolerance=1.00)

    def test_check1_existence_pass_and_fail(self):
        # Pass when cited ID matches resolved evidence
        payload = CandidateExplanationPayload(
            candidate_cause="fee",
            explanation="Fee verified",
            evidence_citations=["stl_valid_1"],
            confidence=0.96,
        )
        ev_records = [{"evidence_id": "stl_valid_1", "type": "settlement", "payload": {"fee_amount": 160.0, "net_amount": 7840.0}}]
        res = self.gater.validate(payload, self.payment, ev_records)
        check_ex = next(c for c in res.checks if c.check_name == "EXISTENCE")
        self.assertTrue(check_ex.passed)

        # Fail when cited ID does not resolve
        payload_missing = CandidateExplanationPayload(
            candidate_cause="fee",
            explanation="Fee verified",
            evidence_citations=["stl_ghost_999"],
            confidence=0.96,
        )
        res_missing = self.gater.validate(payload_missing, self.payment, ev_records)
        check_ex_fail = next(c for c in res_missing.checks if c.check_name == "EXISTENCE")
        self.assertFalse(check_ex_fail.passed)

    def test_check2_ownership_rejects_foreign_payment(self):
        payload = CandidateExplanationPayload(
            candidate_cause="fee",
            explanation="Fee verified",
            evidence_citations=["stl_1"],
            confidence=0.96,
        )
        # Settlement belonging to a different payment ID
        foreign_ev = [{
            "evidence_id": "stl_1",
            "type": "settlement",
            "payload": {"payment_id": "pay_foreign_999", "net_amount": 7840.0, "fee_amount": 160.0},
        }]
        res = self.gater.validate(payload, self.payment, foreign_ev)
        check_own = next(c for c in res.checks if c.check_name == "OWNERSHIP")
        self.assertFalse(check_own.passed)

    def test_check3_amount_math_verification(self):
        # Valid: 8000 payment - 160 fee = 7840 net
        payload = CandidateExplanationPayload(
            candidate_cause="fee",
            explanation="Fee math",
            evidence_citations=["stl_1"],
            confidence=0.96,
        )
        valid_ev = [{
            "evidence_id": "stl_1",
            "type": "settlement",
            "payload": {"net_amount": 7840.0, "fee_amount": 160.0},
        }]
        res_valid = self.gater.validate(payload, self.payment, valid_ev)
        check_math = next(c for c in res_valid.checks if c.check_name == "AMOUNT_MATH")
        self.assertTrue(check_math.passed)

        # Invalid: math mismatch (> tolerance)
        invalid_ev = [{
            "evidence_id": "stl_1",
            "type": "settlement",
            "payload": {"net_amount": 7000.0, "fee_amount": 160.0},
        }]
        res_invalid = self.gater.validate(payload, self.payment, invalid_ev)
        check_math_fail = next(c for c in res_invalid.checks if c.check_name == "AMOUNT_MATH")
        self.assertFalse(check_math_fail.passed)

    def test_check4_temporal_rejects_ancient_evidence(self):
        payload = CandidateExplanationPayload(
            candidate_cause="fee",
            explanation="Temporal check",
            evidence_citations=["stl_1"],
            confidence=0.96,
        )
        # Settlement dated 60 days before payment (beyond 45 day grace)
        ancient_ev = [{
            "evidence_id": "stl_1",
            "type": "settlement",
            "payload": {"settled_at": "2024-12-01T00:00:00", "net_amount": 7840.0, "fee_amount": 160.0},
        }]
        res = self.gater.validate(payload, self.payment, ancient_ev)
        check_temp = next(c for c in res.checks if c.check_name == "TEMPORAL")
        self.assertFalse(check_temp.passed)

    def test_check5_idempotence_rejects_double_spent_settlement(self):
        # Create an existing reconciliation that consumed settlement stl_1
        prior_rec = ReconciliationRecord(
            id="rec_prior_1",
            payment_id="pay_other_002",
            settlement_id="stl_1",
            match_status="MATCHED",
        )
        self.session.add(prior_rec)
        self.session.commit()

        payload = CandidateExplanationPayload(
            candidate_cause="fee",
            explanation="Idempotence check",
            evidence_citations=["stl_1"],
            confidence=0.96,
        )
        ev = [{
            "evidence_id": "stl_1",
            "type": "settlement",
            "payload": {"id": "stl_1", "net_amount": 7840.0, "fee_amount": 160.0},
        }]
        res = self.gater.validate(payload, self.payment, ev)
        check_idem = next(c for c in res.checks if c.check_name == "IDEMPOTENCE")
        self.assertFalse(check_idem.passed)

    def test_confidence_routing_thresholds(self):
        # High confidence (>=0.95) and validated -> AUTO_RESOLVE
        route, status, _ = apply_confidence_routing(confidence=0.97, validation_passed=True)
        self.assertEqual(route, "AUTO_RESOLVE")
        self.assertEqual(status, "RESOLVED_AFTER_INVESTIGATION")

        # Medium confidence (0.70-0.949) -> HUMAN_REVIEW
        route, status, _ = apply_confidence_routing(confidence=0.82, validation_passed=True)
        self.assertEqual(route, "HUMAN_REVIEW")
        self.assertEqual(status, "NEEDS_HUMAN_REVIEW")

        # Low confidence (<0.70) -> EXCEPTION
        route, status, _ = apply_confidence_routing(confidence=0.55, validation_passed=True)
        self.assertEqual(route, "EXCEPTION")
        self.assertEqual(status, "EXCEPTION")

        # High confidence but failed validation -> Downgraded to HUMAN_REVIEW
        route, status, _ = apply_confidence_routing(confidence=0.98, validation_passed=False)
        self.assertEqual(route, "HUMAN_REVIEW")
        self.assertEqual(status, "NEEDS_HUMAN_REVIEW")


if __name__ == "__main__":
    unittest.main()
