"""
Finance Controller — Evaluation Package
=======================================

Provides ground truth evaluation, benchmarking metrics, and report formatting.
"""

from backend.evaluation.metrics import EvaluationMetrics, StageMetrics
from backend.evaluation.evaluator import Evaluator
from backend.evaluation.reports import save_json_report, format_summary_table

__all__ = [
    "EvaluationMetrics",
    "StageMetrics",
    "Evaluator",
    "save_json_report",
    "format_summary_table",
]
