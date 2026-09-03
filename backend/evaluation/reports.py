"""
Finance Controller — Evaluation Reports Formatter
=================================================

Formats evaluation metrics into JSON reports and human-readable summary tables.
"""

import json
from pathlib import Path
from backend.evaluation.metrics import EvaluationMetrics


def save_json_report(metrics: EvaluationMetrics, output_path: Path | str) -> str:
    """Save evaluation metrics as JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    report_data = metrics.to_dict()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
    return str(path.resolve())


def format_summary_table(metrics: EvaluationMetrics) -> str:
    """Generate a clean human-readable summary table formatted for terminal output."""
    lines = []
    lines.append("=" * 75)
    lines.append("  FINANCE CONTROLLER -- RECONCILIATION EVALUATION BENCHMARK")
    lines.append("=" * 75)
    lines.append("")

    lines.append(f"  Total Evaluated Ground Truth Cases : {metrics.total_evaluated_cases}")
    lines.append(f"  Correct Verdicts                  : {metrics.correct_verdicts}")
    lines.append(f"  Incorrect Verdicts                : {metrics.incorrect_verdicts}")
    lines.append("")

    lines.append("-" * 75)
    lines.append("  KEY PERFORMANCE METRICS (PRD Target Benchmarks)")
    lines.append("-" * 75)
    lines.append(f"  Match Accuracy           : {metrics.match_accuracy_pct:>6.2f}%")
    lines.append(f"  Precision                : {metrics.precision_pct:>6.2f}%")
    lines.append(f"  Recall                   : {metrics.recall_pct:>6.2f}%")
    lines.append(f"  Auto-resolution Rate     : {metrics.auto_resolution_rate_pct:>6.2f}%")
    lines.append(f"  Exception Rate           : {metrics.exception_rate_pct:>6.2f}%")
    lines.append(f"  False-Positive Rate      : {metrics.false_positive_rate_pct:>6.2f}%")
    lines.append(f"  Unresolved Case Count    : {metrics.unresolved_exception_count:>6}")
    lines.append("")

    lines.append("-" * 75)
    lines.append("  STAGE THROUGHPUT PERFORMANCE (REPORTED SEPARATELY)")
    lines.append("-" * 75)
    s1 = metrics.stage1_metrics
    s2 = metrics.stage2_metrics
    lines.append(f"  Stage 1 (Deterministic)   : {s1.throughput_records_per_sec:>8.2f} rec/sec  ({s1.processed_count} records processed)")
    lines.append(f"  Stage 2 (AI Investigation): {s2.throughput_records_per_sec:>8.2f} rec/sec  ({s2.processed_count} records processed)")
    lines.append("")

    lines.append("-" * 75)
    lines.append("  CONFUSION MATRIX")
    lines.append("-" * 75)
    lines.append(f"  True Positives  (TP)     : {metrics.true_positives:>6}")
    lines.append(f"  False Positives (FP)     : {metrics.false_positives:>6}")
    lines.append(f"  True Negatives  (TN)     : {metrics.true_negatives:>6}")
    lines.append(f"  False Negatives (FN)     : {metrics.false_negatives:>6}")
    lines.append("")

    if metrics.scenario_breakdown:
        lines.append("-" * 75)
        lines.append("  ACCURACY BREAKDOWN BY SCENARIO TYPE")
        lines.append("-" * 75)
        lines.append(f"  {'Scenario Type':<26} {'Total':>6} {'Correct':>8} {'Accuracy':>10}")
        lines.append("  " + "-" * 54)
        for scen, s in sorted(metrics.scenario_breakdown.items()):
            lines.append(
                f"  {scen:<26} {s['total']:>6} {s['correct']:>8} {s['accuracy_pct']:>9.2f}%"
            )
        lines.append("  " + "-" * 54)

    lines.append("")
    lines.append("=" * 75)
    return "\n".join(lines)
