"""
Finance Controller — Stage 2 Agent Output Validator & Evidence Gater
====================================================================

Implements PRD Section 12.3 schema validation, Section 13 Evidence Validation
(6-point deterministic checklist), and Section 14 Confidence Routing.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.payment import Payment
from backend.models.reconciliation import ReconciliationRecord


VALID_CANDIDATE_CAUSES = {
    "fee",
    "partial_payment",
    "refund",
    "duplicate",
    "timing_mismatch",
    "name_mismatch",
    "no_sufficient_evidence_found",
    "tax",
    "adjustment",
    "multiple_settlements",
    "unknown",
}

VALID_VERDICTS = {
    "RESOLVED_AFTER_INVESTIGATION",
    "NEEDS_HUMAN_REVIEW",
    "EXCEPTION",
    "MATCHED",
}


@dataclass
class CandidateExplanationPayload:
    candidate_cause: str
    explanation: str
    evidence_citations: List[str] = field(default_factory=list)
    confidence: float = 0.0
    linked_invoice_id: Optional[str] = None
    linked_settlement_id: Optional[str] = None
    linked_refund_id: Optional[str] = None
    discrepancy: float = 0.0
    verdict: str = "NEEDS_HUMAN_REVIEW"
    reason: str = "UNKNOWN"


@dataclass
class ValidationCheck:
    check_name: str  # EXISTENCE | OWNERSHIP | AMOUNT_MATH | TEMPORAL | IDEMPOTENCE | CHECKSUM
    passed: bool
    details: str


@dataclass
class EvidenceValidationResult:
    passed: bool
    checks: List[ValidationCheck] = field(default_factory=list)
    downgrade_reason: Optional[str] = None


def validate_agent_explanation(data: Dict[str, Any]) -> CandidateExplanationPayload:
    """
    Validate and parse structured candidate explanation payload.
    Supports both PRD Section 12.3 JSON schema and existing pipeline structures.
    """
    if not isinstance(data, dict):
        raise ValueError("Agent output payload must be a dictionary.")

    # 1. Parse verdict
    raw_verdict = str(data.get("verdict", "")).upper().strip()
    verdict = raw_verdict if raw_verdict in VALID_VERDICTS else "NEEDS_HUMAN_REVIEW"

    # 2. Parse reason / candidate_cause
    raw_cause = data.get("reason") or data.get("candidate_cause") or "no_sufficient_evidence_found"
    cause = str(raw_cause).lower().strip()
    if cause not in VALID_CANDIDATE_CAUSES:
        cause = "no_sufficient_evidence_found"

    # 3. Parse explanation
    explanation = data.get("explanation") or data.get("reasoning")
    if not explanation or not isinstance(explanation, str):
        explanation = "No detailed explanation provided."

    # 4. Parse evidence citations / IDs
    raw_citations = data.get("evidence_ids") or data.get("evidence_citations") or []
    if isinstance(raw_citations, list):
        citations = [str(c) for c in raw_citations if c]
    elif isinstance(raw_citations, str):
        citations = [raw_citations]
    else:
        citations = []

    # If cause is not no_sufficient_evidence_found / unknown, require citation
    if cause not in ("no_sufficient_evidence_found", "unknown") and not citations:
        cause = "no_sufficient_evidence_found"
        verdict = "NEEDS_HUMAN_REVIEW"
        explanation = f"Proposed cause '{raw_cause}' rejected: No supporting evidence records cited."

    # 5. Parse confidence
    raw_conf = data.get("confidence", 0.0)
    try:
        confidence = float(raw_conf)
        confidence = max(0.0, min(1.0, confidence))
    except (ValueError, TypeError):
        confidence = 0.0

    return CandidateExplanationPayload(
        candidate_cause=cause,
        explanation=explanation,
        evidence_citations=citations,
        confidence=confidence,
        linked_invoice_id=data.get("linked_invoice_id") or data.get("invoice_id"),
        linked_settlement_id=data.get("linked_settlement_id") or data.get("settlement_id"),
        linked_refund_id=data.get("linked_refund_id") or data.get("refund_id"),
        discrepancy=float(data.get("discrepancy", 0.0)),
        verdict=verdict,
        reason=cause.upper(),
    )


class EvidenceGater:
    """
    Implements PRD Section 13 Evidence Validation & Gating.
    Executes the 6-point independent deterministic checklist:
      1. EXISTENCE
      2. OWNERSHIP
      3. AMOUNT_MATH
      4. TEMPORAL
      5. IDEMPOTENCE
      6. CHECKSUM
    """

    def __init__(self, db_session: Session, amount_tolerance: float = 1.00):
        self.session = db_session
        self.amount_tolerance = amount_tolerance

    def validate(
        self,
        verdict_payload: CandidateExplanationPayload,
        payment: Payment,
        evidence_records: List[Dict[str, Any]],
    ) -> EvidenceValidationResult:
        checks: List[ValidationCheck] = []

        # Check 1: EXISTENCE
        # Every cited ID must resolve to a real evidence object
        cited_ids = set(verdict_payload.evidence_citations)
        resolved_ids = {e.get("evidence_id") for e in evidence_records if e.get("evidence_id")}
        missing_ids = cited_ids - resolved_ids
        # Also allow matching by internal payload IDs
        for e in evidence_records:
            p = e.get("payload", {})
            if p.get("id"):
                resolved_ids.add(str(p.get("id")))
            if p.get("razorpay_settlement_id"):
                resolved_ids.add(str(p.get("razorpay_settlement_id")))
            if p.get("razorpay_refund_id"):
                resolved_ids.add(str(p.get("razorpay_refund_id")))
            if p.get("invoice_number"):
                resolved_ids.add(str(p.get("invoice_number")))

        missing_ids = cited_ids - resolved_ids
        existence_passed = len(missing_ids) == 0 and len(evidence_records) > 0 if cited_ids else False
        if not cited_ids and verdict_payload.candidate_cause in ("no_sufficient_evidence_found", "unknown"):
            # If no evidence cited for unknown/unresolved, existence check passes vacuously
            existence_passed = True

        checks.append(
            ValidationCheck(
                check_name="EXISTENCE",
                passed=existence_passed,
                details="All cited evidence IDs resolved." if existence_passed else f"Missing evidence IDs: {missing_ids}",
            )
        )

        # Check 2: OWNERSHIP
        # Any evidence referencing payment_id must match the payment under investigation
        ownership_passed = True
        foreign_refs = []
        for e in evidence_records:
            p = e.get("payload", {})
            e_pay_id = p.get("payment_id")
            if e_pay_id and e_pay_id != payment.id and e_pay_id != payment.razorpay_payment_id:
                ownership_passed = False
                foreign_refs.append(f"{e.get('evidence_id')}(belongs to {e_pay_id})")

        checks.append(
            ValidationCheck(
                check_name="OWNERSHIP",
                passed=ownership_passed,
                details="All evidence ownership verified." if ownership_passed else f"Foreign ownership: {foreign_refs}",
            )
        )

        # Check 3: AMOUNT_MATH
        # Arithmetic implied by reason holds within tolerance
        math_passed = True
        math_details = "Arithmetic validated."
        pay_amt = float(payment.amount)

        cause = verdict_payload.candidate_cause
        if cause == "fee":
            stls = [e["payload"] for e in evidence_records if e.get("type") == "settlement"]
            if stls:
                stl = stls[0]
                expected_net = pay_amt - stl.get("fee_amount", 0.0) - stl.get("tax_amount", 0.0)
                actual_net = stl.get("net_amount", 0.0)
                if abs(expected_net - actual_net) > self.amount_tolerance:
                    math_passed = False
                    math_details = f"Fee arithmetic delta {abs(expected_net - actual_net):.2f} exceeds tolerance {self.amount_tolerance}"
            else:
                math_passed = False
                math_details = "No settlement record found to verify fee math."
        elif cause == "refund":
            rfnds = [e["payload"] for e in evidence_records if e.get("type") == "refund"]
            if rfnds:
                tot_refund = sum(r.get("amount", 0.0) for r in rfnds)
                stls = [e["payload"] for e in evidence_records if e.get("type") == "settlement"]
                if stls:
                    stl = stls[0]
                    expected_net = pay_amt - tot_refund
                    actual_net = stl.get("net_amount", 0.0)
                    if abs(expected_net - actual_net) > self.amount_tolerance:
                        math_passed = False
                        math_details = f"Refund arithmetic delta {abs(expected_net - actual_net):.2f} exceeds tolerance"
            else:
                math_passed = False
                math_details = "No refund record found to verify refund math."

        checks.append(
            ValidationCheck(check_name="AMOUNT_MATH", passed=math_passed, details=math_details)
        )

        # Check 4: TEMPORAL
        # Timestamps must fall within expected bounds
        temporal_passed = True
        temp_details = "Timestamps within bounds."
        pay_date = payment.payment_date.date() if isinstance(payment.payment_date, datetime) else payment.payment_date

        for e in evidence_records:
            p = e.get("payload", {})
            dt_str = p.get("settled_at") or p.get("refunded_at") or p.get("issue_date")
            if dt_str:
                try:
                    ev_dt = datetime.fromisoformat(dt_str.replace("Z", "")).date()
                    # Settlement/Refund shouldn't precede payment by more than 45 days
                    if (pay_date - ev_dt).days > 45:
                        temporal_passed = False
                        temp_details = f"Evidence {e.get('evidence_id')} dated {ev_dt} precedes payment date {pay_date} by >45 days."
                        break
                except Exception:
                    pass

        checks.append(
            ValidationCheck(check_name="TEMPORAL", passed=temporal_passed, details=temp_details)
        )

        # Check 5: IDEMPOTENCE
        # Settlement/refund not already consumed by another existing MATCHED reconciliation
        idempotence_passed = True
        consumed_refs = []
        for e in evidence_records:
            if e.get("type") == "settlement":
                stl_id = e.get("payload", {}).get("id")
                if stl_id:
                    existing = self.session.scalars(
                        select(ReconciliationRecord).where(
                            ReconciliationRecord.settlement_id == stl_id,
                            ReconciliationRecord.payment_id != payment.id,
                            ReconciliationRecord.match_status.in_(["MATCHED", "RESOLVED_AFTER_INVESTIGATION"]),
                        )
                    ).first()
                    if existing:
                        idempotence_passed = False
                        consumed_refs.append(f"Settlement {stl_id} already consumed by payment {existing.payment_id}")

        checks.append(
            ValidationCheck(
                check_name="IDEMPOTENCE",
                passed=idempotence_passed,
                details="Evidence not previously consumed." if idempotence_passed else f"Consumed: {consumed_refs}",
            )
        )

        # Check 6: CHECKSUM
        # Referenced evidence amount explains the transaction delta
        checksum_passed = True
        cs_details = "Delta verified by evidence."
        stls = [e["payload"] for e in evidence_records if e.get("type") == "settlement"]
        if stls:
            stl = stls[0]
            net_amt = stl.get("net_amount", 0.0)
            delta = abs(pay_amt - net_amt)
            if delta > 0.01:
                # Sum of fee, tax, refunds, adjustments
                fee = stl.get("fee_amount", 0.0)
                tax = stl.get("tax_amount", 0.0)
                rfnds = sum(e["payload"].get("amount", 0.0) for e in evidence_records if e.get("type") == "refund")
                explained = fee + tax + rfnds
                if abs(delta - explained) > self.amount_tolerance * 2:
                    checksum_passed = False
                    cs_details = f"Unexplained delta: payment {pay_amt}, net {net_amt}, delta {delta:.2f}, explained {explained:.2f}"

        checks.append(
            ValidationCheck(check_name="CHECKSUM", passed=checksum_passed, details=cs_details)
        )

        all_passed = all(c.passed for c in checks)
        downgrade_reason = None
        if not all_passed:
            failed_names = [c.check_name for c in checks if not c.passed]
            downgrade_reason = f"EVIDENCE_VALIDATION_FAILED: {', '.join(failed_names)}"

        return EvidenceValidationResult(
            passed=all_passed,
            checks=checks,
            downgrade_reason=downgrade_reason,
        )


def apply_confidence_routing(
    confidence: float,
    validation_passed: bool,
    downgrade_reason: Optional[str] = None,
) -> Tuple[str, str, str]:
    """
    Implements PRD Section 14 Confidence Routing.

    Returns: (route, final_status, routing_note)
      - AUTO_RESOLVE: RESOLVED_AFTER_INVESTIGATION
      - HUMAN_REVIEW: NEEDS_HUMAN_REVIEW
      - EXCEPTION: EXCEPTION
    """
    if not validation_passed:
        # Failed evidence gating overrides raw confidence
        if downgrade_reason and "TEMPORAL" in downgrade_reason:
            return "EXCEPTION", "EXCEPTION", downgrade_reason or "Evidence temporal check failed."
        return "HUMAN_REVIEW", "NEEDS_HUMAN_REVIEW", downgrade_reason or "Evidence validation checks failed."

    if confidence >= 0.95:
        return "AUTO_RESOLVE", "RESOLVED_AFTER_INVESTIGATION", "High confidence (>=0.95) with all 6 validation checks passed."
    elif confidence >= 0.70:
        return "HUMAN_REVIEW", "NEEDS_HUMAN_REVIEW", f"Moderate confidence ({confidence:.2f}) routed to human review queue."
    else:
        return "EXCEPTION", "EXCEPTION", f"Low confidence ({confidence:.2f}) held as exception."
