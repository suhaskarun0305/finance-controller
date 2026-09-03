"""
Finance Controller — Run Evaluation Benchmark Script
=====================================================

Runs the evaluation harness against system decisions in the database,
comparing them with the objective ground truth records.

Usage (from project root):
    python scripts/run_benchmark.py

Outputs:
  - Prints human-readable summary table to stdout
  - Saves detailed JSON report to `data/generated/evaluation_report.json`
"""

import sys
import io
from pathlib import Path

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
from backend.evaluation import Evaluator, save_json_report, format_summary_table


def main() -> None:
    session = SessionLocal()
    try:
        evaluator = Evaluator(session)
        metrics = evaluator.evaluate()

        # Print human-readable summary table
        table_output = format_summary_table(metrics)
        print(table_output)

        # Save JSON report
        json_path = Path(_project_root) / "data" / "generated" / "evaluation_report.json"
        saved_file = save_json_report(metrics, json_path)
        print(f"  Saved JSON report to: {saved_file}")
        print("=" * 75)
    finally:
        session.close()


if __name__ == "__main__":
    main()
