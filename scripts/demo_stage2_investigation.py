"""
Finance Controller — Stage 2 Investigation Demonstration Script
================================================================

Runs Stage 2 AI Investigation on sample unresolved payment records,
displaying retrieved evidence packages, proposed candidate causes, and supporting
evidence citations.

Usage (from project root):
    python scripts/demo_stage2_investigation.py
"""

import sys
import io
import json
from pathlib import Path
from sqlalchemy import select

# ---------------------------------------------------------------------------
# Force UTF-8 on Windows
# ---------------------------------------------------------------------------
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.database.session import SessionLocal
from backend.models.payment import Payment
from backend.reconciliation.matcher import Stage1Matcher
from backend.agents.investigator import InvestigatorAgent
from backend.services.evidence_service import EvidenceService


def main() -> None:
    print("=" * 80)
    print("  Finance Controller -- Stage 2 AI Agent Investigation Demo")
    print("=" * 80)
    print()

    session = SessionLocal()
    try:
        # 1. Run Stage 1 to ensure records exist
        matcher = Stage1Matcher(session)
        records = matcher.process_all_payments()

        agent = InvestigatorAgent(session)
        evidence_service = EvidenceService(session)

        # 2. Pick sample payments across unresolved scenarios
        scenarios_to_demo = ["name_mismatch", "date_drift", "chargeback", "missing_invoice", "duplicate_transaction"]
        demo_payments = []

        for scen in scenarios_to_demo:
            p = session.scalars(select(Payment).where(Payment.scenario_type == scen)).first()
            if p:
                demo_payments.append(p)

        print(f"Selected {len(demo_payments)} sample unresolved payment records for Stage 2 demonstration.\n")

        for idx, pay in enumerate(demo_payments, 1):
            print("-" * 80)
            print(f"[{idx}] Investigating Payment: {pay.razorpay_payment_id}")
            print(f"    Scenario Type : {pay.scenario_type}")
            print(f"    Amount        : {pay.amount} {pay.currency}")
            print(f"    Payer Name    : {pay.payer_name}")
            print(f"    Payment Date  : {pay.payment_date}")
            print("-" * 80)

            # Collect Evidence Package
            evidence = evidence_service.collect_evidence(pay)
            print("  [SCOPED READ-ONLY EVIDENCE RETRIEVED]")
            print(f"    - Candidate Invoices    : {len(evidence.candidate_invoices)} records")
            print(f"    - Candidate Settlements : {len(evidence.candidate_settlements)} records")
            print(f"    - Refund/Dispute Records: {len(evidence.refund_records)} records")
            print(f"    - Fee Schedule          : {evidence.fee_schedule.get('description')[:55]}...")
            print(f"    - Prior Resolutions     : {len(evidence.prior_human_resolutions)} records")
            print()

            # Run Investigation
            res = agent.investigate_unresolved_payment(pay)

            print("  [CANDIDATE EXPLANATION PROPOSED]")
            print(f"    - Candidate Cause     : {res.candidate_cause.upper()}")
            print(f"    - Confidence Score    : {res.confidence}")
            print(f"    - Evidence Citations  : {res.evidence_citations}")
            print(f"    - Explanation         : {res.explanation}")
            print()

        print("=" * 80)
        print("  Stage 2 Investigation Demo Complete!")
        print("=" * 80)

    finally:
        session.close()


if __name__ == "__main__":
    main()
