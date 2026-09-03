"""
Finance Controller — Evaluation Accuracy Tests
==============================================

Unit test suite verifying metric calculation and Evaluator logic.
"""

import sys
import unittest
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.evaluation.metrics import EvaluationMetrics, StageMetrics
from backend.evaluation.reports import format_summary_table, save_json_report


class TestEvaluationHarness(unittest.TestCase):

    def test_stage_metrics_throughput(self):
        sm = StageMetrics(stage=1, stage_name="Stage 1 Test", processed_count=100, total_time_ms=500.0)
        sm.calculate_throughput()
        self.assertEqual(sm.throughput_records_per_sec, 200.0)

    def test_evaluation_metrics_defaults(self):
        metrics = EvaluationMetrics(total_evaluated_cases=200, unresolved_exception_count=200)
        self.assertEqual(metrics.auto_resolution_rate_pct, 0.0)
        self.assertEqual(metrics.precision_pct, 0.0)
        self.assertEqual(metrics.recall_pct, 0.0)
        self.assertEqual(metrics.false_positive_rate_pct, 0.0)
        self.assertEqual(metrics.stage1_metrics.throughput_records_per_sec, 0.0)
        self.assertEqual(metrics.stage2_metrics.throughput_records_per_sec, 0.0)

    def test_summary_table_formatting(self):
        metrics = EvaluationMetrics(
            total_evaluated_cases=10,
            correct_verdicts=8,
            incorrect_verdicts=2,
            match_accuracy_pct=80.0,
            auto_resolution_rate_pct=80.0,
            exception_rate_pct=20.0,
        )
        table_str = format_summary_table(metrics)
        self.assertIn("FINANCE CONTROLLER -- RECONCILIATION EVALUATION BENCHMARK", table_str)
        self.assertIn("Match Accuracy           :  80.00%", table_str)


if __name__ == "__main__":
    unittest.main()
