"""
Finance Controller — Benchmark Runner Module
=============================================

Provides a programmatic interface for running evaluation benchmarks
against ground truth. Used by scripts/run_benchmark.py and the
dashboard API endpoint for on-demand benchmark recalculation.
"""

from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from backend.evaluation.evaluator import Evaluator
from backend.evaluation.metrics import EvaluationMetrics
from backend.evaluation.reports import format_summary_table, save_json_report


def run_benchmark(
    db_session: Session,
    output_path: Optional[Path] = None,
    print_summary: bool = True,
) -> EvaluationMetrics:
    """
    Execute evaluation benchmark against ground truth.

    Args:
        db_session: Active SQLAlchemy session with reconciliation and ground truth data.
        output_path: Optional path for JSON report output. Defaults to data/generated/.
        print_summary: Whether to print formatted summary table to stdout.

    Returns:
        EvaluationMetrics with complete benchmark results.
    """
    evaluator = Evaluator(db_session)
    metrics = evaluator.evaluate()

    if print_summary:
        print(format_summary_table(metrics))

    if output_path:
        save_json_report(metrics, output_path)

    return metrics


def run_benchmark_from_session(db_session: Session) -> dict:
    """
    Lightweight benchmark runner returning a dictionary.
    Used by the dashboard API endpoint for on-demand recalculation.
    """
    evaluator = Evaluator(db_session)
    metrics = evaluator.evaluate()
    return metrics.to_dict()
