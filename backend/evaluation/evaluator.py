"""
Finance Controller — Reconciliation Evaluator
==============================================

Evaluates system decisions (ReconciliationRecord) against objective ground truth
(GroundTruthRecord) without allowing the system to grade itself.
"""

from typing import Sequence
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.ground_truth import GroundTruthRecord
from backend.models.reconciliation import ReconciliationRecord
from backend.evaluation.metrics import EvaluationMetrics, StageMetrics, wilson_ci


class Evaluator:
    """Evaluates reconciliation results against ground truth."""

    RESOLVED_VERDICTS = {"MATCHED", "PARTIALLY_MATCHED", "RESOLVED_AFTER_INVESTIGATION"}

    def __init__(self, db_session: Session):
        self.session = db_session

    def evaluate(self) -> EvaluationMetrics:
        """Run complete evaluation against ground truth stored in database."""
        # 1. Fetch ground truth records
        gt_records: Sequence[GroundTruthRecord] = self.session.scalars(
            select(GroundTruthRecord)
        ).all()

        # 2. Fetch system reconciliation records
        rec_records: Sequence[ReconciliationRecord] = self.session.scalars(
            select(ReconciliationRecord)
        ).all()

        # Map system decisions by payment_id and invoice_id
        system_map_by_pay: dict[str, ReconciliationRecord] = {
            r.payment_id: r for r in rec_records if r.payment_id
        }
        system_map_by_inv: dict[str, ReconciliationRecord] = {
            r.invoice_id: r for r in rec_records if r.invoice_id
        }

        metrics = EvaluationMetrics()
        metrics.total_evaluated_cases = len(gt_records)

        if not gt_records:
            return metrics

        # Stage throughput tracking
        s1_time_ms = 0.0
        s1_count = 0
        s2_time_ms = 0.0
        s2_count = 0

        for r in rec_records:
            if r.stage == 1:
                s1_count += 1
                s1_time_ms += (r.processing_time_ms or 0.0)
            elif r.stage == 2:
                s2_count += 1
                s2_time_ms += (r.processing_time_ms or 0.0)

        metrics.stage1_metrics = StageMetrics(
            stage=1,
            stage_name="Stage 1 (Deterministic)",
            processed_count=s1_count,
            total_time_ms=s1_time_ms,
        )
        metrics.stage1_metrics.calculate_throughput()

        metrics.stage2_metrics = StageMetrics(
            stage=2,
            stage_name="Stage 2 (AI Investigation)",
            processed_count=s2_count,
            total_time_ms=s2_time_ms,
        )
        metrics.stage2_metrics.calculate_throughput()

        # Per-scenario stats builder
        scenario_stats: dict[str, dict[str, int]] = {}

        for gt in gt_records:
            scen = gt.scenario_type
            if scen not in scenario_stats:
                scenario_stats[scen] = {
                    "total": 0, "correct": 0, "predicted_resolved": 0,
                    "expected_resolved": 0, "tp": 0, "fp": 0, "tn": 0, "fn": 0,
                }
            scenario_stats[scen]["total"] += 1

            # Match system decision to ground truth
            sys_rec = None
            if gt.payment_id and gt.payment_id in system_map_by_pay:
                sys_rec = system_map_by_pay[gt.payment_id]
            elif gt.invoice_id and gt.invoice_id in system_map_by_inv:
                sys_rec = system_map_by_inv[gt.invoice_id]

            # Actual system verdict (if no decision recorded, default to UNMATCHED / EXCEPTION)
            predicted_verdict = sys_rec.match_status.upper() if sys_rec else "EXCEPTION"
            expected_verdict = gt.expected_verdict.upper()

            is_expected_resolved = expected_verdict in self.RESOLVED_VERDICTS
            is_predicted_resolved = predicted_verdict in self.RESOLVED_VERDICTS

            if is_expected_resolved:
                scenario_stats[scen]["expected_resolved"] += 1
            if is_predicted_resolved:
                scenario_stats[scen]["predicted_resolved"] += 1

            # Correct verdict check
            if predicted_verdict == expected_verdict:
                metrics.correct_verdicts += 1
                scenario_stats[scen]["correct"] += 1
            else:
                metrics.incorrect_verdicts += 1

            # Confusion matrix
            if is_predicted_resolved and is_expected_resolved:
                metrics.true_positives += 1
                scenario_stats[scen]["tp"] += 1
            elif is_predicted_resolved and not is_expected_resolved:
                metrics.false_positives += 1
                scenario_stats[scen]["fp"] += 1
            elif not is_predicted_resolved and not is_expected_resolved:
                metrics.true_negatives += 1
                scenario_stats[scen]["tn"] += 1
            elif not is_predicted_resolved and is_expected_resolved:
                metrics.false_negatives += 1
                scenario_stats[scen]["fn"] += 1

            # Auto-resolved vs Exception counters
            if is_predicted_resolved:
                metrics.auto_resolved_count += 1
            else:
                metrics.unresolved_exception_count += 1

        total = metrics.total_evaluated_cases

        # Rates & Percentages
        metrics.match_accuracy_pct = round((metrics.correct_verdicts / total) * 100.0, 2)
        metrics.match_accuracy_ci_95 = wilson_ci(metrics.correct_verdicts, total)
        metrics.auto_resolution_rate_pct = round((metrics.auto_resolved_count / total) * 100.0, 2)
        metrics.exception_rate_pct = round((metrics.unresolved_exception_count / total) * 100.0, 2)

        # Precision, Recall, FPR
        tp_fp = metrics.true_positives + metrics.false_positives
        metrics.precision_pct = round((metrics.true_positives / tp_fp) * 100.0, 2) if tp_fp > 0 else 0.0

        tp_fn = metrics.true_positives + metrics.false_negatives
        metrics.recall_pct = round((metrics.true_positives / tp_fn) * 100.0, 2) if tp_fn > 0 else 0.0

        fp_tn = metrics.false_positives + metrics.true_negatives
        metrics.false_positive_rate_pct = round((metrics.false_positives / fp_tn) * 100.0, 2) if fp_tn > 0 else 0.0

        # Build final scenario breakdown dictionary
        for scen, s in scenario_stats.items():
            scen_total = s["total"]
            scen_acc = round((s["correct"] / scen_total) * 100.0, 2) if scen_total > 0 else 0.0
            metrics.scenario_breakdown[scen] = {
                "total": scen_total,
                "correct": s["correct"],
                "accuracy_pct": scen_acc,
                "predicted_resolved": s["predicted_resolved"],
                "tp": s["tp"], "fp": s["fp"], "tn": s["tn"], "fn": s["fn"],
            }

        return metrics
