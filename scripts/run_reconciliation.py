"""
Finance Controller — Run Full Two-Stage Reconciliation Pipeline
===============================================================

Executes Stage 1 (Deterministic Rules) followed by Stage 2 (AI Investigation Agent)
across all payment transactions, then evaluates final benchmark metrics against Ground Truth.

Usage (from project root):
    python scripts/run_reconciliation.py
"""

import sys
import io
import time
from pathlib import Path
from sqlalchemy import delete, select

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
from backend.models.reconciliation import ReconciliationRecord
from backend.reconciliation.matcher import Stage1Matcher
from backend.agents.investigator import InvestigatorAgent
from backend.evaluation import Evaluator, save_json_report, format_summary_table


def main() -> None:
    print("=" * 75)
    print("  Finance Controller -- Full 2-Stage Reconciliation Pipeline")
    print("=" * 75)
    print()

    session = SessionLocal()
    try:
        # 1. Reset previous reconciliation records
        print("[1/4] Resetting previous reconciliation decisions ...")
        session.execute(delete(ReconciliationRecord))
        session.commit()
        print("      Done.\n")

        # 2. Stage 1: Deterministic Matcher
        print("[2/4] Executing Stage 1 (Deterministic Rules) ...")
        t1_start = time.perf_counter()

        stage1_matcher = Stage1Matcher(session)
        stage1_records = stage1_matcher.process_all_payments()

        t1_elapsed = time.perf_counter() - t1_start
        s1_throughput = len(stage1_records) / t1_elapsed if t1_elapsed > 0 else 0.0

        s1_matched = sum(1 for r in stage1_records if r.match_status == "MATCHED")
        s1_partial = sum(1 for r in stage1_records if r.match_status == "PARTIALLY_MATCHED")
        s1_unmatched = [r for r in stage1_records if r.match_status == "UNMATCHED"]

        print(f"      Processed {len(stage1_records)} payments in {t1_elapsed:.2f} seconds ({s1_throughput:.2f} rec/sec).")
        print(f"      - MATCHED           : {s1_matched:>4}")
        print(f"      - PARTIALLY_MATCHED : {s1_partial:>4}")
        print(f"      - UNMATCHED         : {len(s1_unmatched):>4} (Passed to Stage 2)\n")

        # 3. Stage 2: AI Investigator Agent
        print("[3/4] Executing Stage 2 (AI Investigator Agent) on unresolved cases ...")
        t2_start = time.perf_counter()

        investigator = InvestigatorAgent(session)
        stage2_records = []

        unresolved_payments = session.scalars(
            select(Payment).where(Payment.id.in_([r.payment_id for r in s1_unmatched]))
        ).all()

        for p in unresolved_payments:
            rec = investigator.investigate_payment(p)
            stage2_records.append(rec)

        t2_elapsed = time.perf_counter() - t2_start
        s2_throughput = len(stage2_records) / t2_elapsed if t2_elapsed > 0 else 0.0

        s2_resolved = sum(1 for r in stage2_records if r.match_status == "RESOLVED_AFTER_INVESTIGATION")
        s2_exceptions = sum(1 for r in stage2_records if r.match_status == "EXCEPTION")

        print(f"      Investigated {len(stage2_records)} cases in {t2_elapsed:.2f} seconds ({s2_throughput:.2f} rec/sec).")
        print(f"      - RESOLVED_AFTER_INVESTIGATION : {s2_resolved:>4}")
        print(f"      - EXCEPTION                     : {s2_exceptions:>4}\n")

        # 4. Evaluation Benchmark Harness
        print("[4/4] Running Evaluation Benchmark Harness against final 2-stage decisions ...")
        print()

        evaluator = Evaluator(session)
        metrics = evaluator.evaluate()

        # Update throughput metrics explicitly in metric report
        metrics.stage1_metrics.processed_count = len(stage1_records)
        metrics.stage1_metrics.total_time_ms = t1_elapsed * 1000.0
        metrics.stage1_metrics.calculate_throughput()

        metrics.stage2_metrics.processed_count = len(stage2_records)
        metrics.stage2_metrics.total_time_ms = t2_elapsed * 1000.0
        metrics.stage2_metrics.calculate_throughput()

        # Print summary table
        print(format_summary_table(metrics))

        # Save JSON report
        json_path = Path(_project_root) / "data" / "generated" / "evaluation_report.json"
        saved_file = save_json_report(metrics, json_path)

        print(f"  Saved final evaluation report to: {saved_file}")
        print("=" * 75)

    finally:
        session.close()


if __name__ == "__main__":
    main()
