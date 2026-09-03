"""
Finance Controller — Audit Service
===================================

Provides append-only, immutable audit logging across all pipeline stages:
CANDIDATE_GEN, DETERMINISTIC_CHECK, AI_INVESTIGATION, EVIDENCE_VALIDATION,
CONFIDENCE_ROUTING, HUMAN_REVIEW (PRD Section 15).
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from backend.models.audit import AuditLog


class AuditService:
    """Service for managing immutable audit trail records."""

    def __init__(self, db_session: Session):
        self.session = db_session

    def record_step(
        self,
        reconciliation_id: str,
        step: str,
        actor: str,
        input_snapshot: Dict[str, Any],
        output_snapshot: Dict[str, Any],
        evidence_refs: Optional[List[str]] = None,
        exception_id: Optional[str] = None,
    ) -> AuditLog:
        """
        Record an immutable audit step.

        Parameters:
          - reconciliation_id: Entity ID associated with reconciliation
          - step: CANDIDATE_GEN | DETERMINISTIC_CHECK | AI_INVESTIGATION | EVIDENCE_VALIDATION | CONFIDENCE_ROUTING | HUMAN_REVIEW
          - actor: 'system:candidate-gen' | 'system:deterministic-engine' | 'system:ai-investigator' | 'user:<id>'
          - input_snapshot: Dict capturing inputs to this stage
          - output_snapshot: Dict capturing outputs/decisions from this stage
          - evidence_refs: Optional list of cited evidence IDs
        """
        payload = {
            "step": step,
            "reconciliation_id": reconciliation_id,
            "exception_id": exception_id,
            "actor": actor,
            "input_snapshot": input_snapshot,
            "output_snapshot": output_snapshot,
            "evidence_refs": evidence_refs or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        entry = AuditLog(
            id=str(uuid.uuid4()),
            entity_type="reconciliation",
            entity_id=reconciliation_id,
            action=step,
            actor=actor,
            details=json.dumps(payload, default=str),
        )

        self.session.add(entry)
        self.session.flush()
        return entry

    def get_timeline(self, reconciliation_id: str) -> List[Dict[str, Any]]:
        """Retrieve chronological audit timeline for a reconciliation case."""
        stmt = (
            select(AuditLog)
            .where(AuditLog.entity_id == reconciliation_id)
            .order_by(AuditLog.created_at.asc())
        )
        logs = self.session.scalars(stmt).all()

        timeline = []
        for log in logs:
            try:
                parsed = json.loads(log.details) if log.details else {}
            except Exception:
                parsed = {}

            step_name = parsed.get("step") or log.action
            timeline.append({
                "audit_id": log.id,
                "step": step_name,
                "actor": log.actor,
                "created_at": str(log.created_at),
                "summary": self._generate_step_summary(step_name, parsed.get("output_snapshot", {})),
                "input_snapshot": parsed.get("input_snapshot", {}),
                "output_snapshot": parsed.get("output_snapshot", {}),
                "evidence_refs": parsed.get("evidence_refs", []),
            })

        return timeline

    def _generate_step_summary(self, step: str, output: Dict[str, Any]) -> str:
        """Helper to generate human-readable step summary for the UI."""
        if step == "CANDIDATE_GEN":
            count = output.get("candidates_count", 0)
            return f"{count} candidate records surfaced."
        elif step == "DETERMINISTIC_CHECK":
            status = output.get("status", "UNKNOWN")
            rule = output.get("rule_matched")
            if rule:
                return f"Matched deterministically via Rule {rule}."
            return f"Status: {status} — Escalated to AI Investigation."
        elif step == "AI_INVESTIGATION":
            verdict = output.get("verdict", "")
            reason = output.get("reason", "")
            conf = output.get("confidence", 0.0)
            return f"AI Verdict: {verdict} ({reason}, conf: {conf:.2f})."
        elif step == "EVIDENCE_VALIDATION":
            passed = output.get("passed", False)
            return "All 6 validation checks passed." if passed else f"Validation failed: {output.get('downgrade_reason', '')}"
        elif step == "CONFIDENCE_ROUTING":
            route = output.get("route", "")
            final_status = output.get("final_status", "")
            return f"Routed to {route} -> Final Status: {final_status}."
        elif step == "HUMAN_REVIEW":
            action = output.get("action", "")
            reviewer = output.get("reviewer_id", "Specialist")
            return f"Specialist action: {action} by {reviewer}."
        return f"Completed {step}."
