"""
Finance Controller — Evaluation Metrics Data Structure
======================================================

Defines the evaluation metrics data model and core statistical calculations
including Wilson 95% confidence intervals per PRD Section 17.4.
"""

import math
from dataclasses import dataclass, field, asdict
from typing import Any, Tuple


def wilson_ci(successes: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    """
    Calculate Wilson score interval for binomial proportion (PRD Section 17.4).
    Returns (lower_bound_pct, upper_bound_pct) rounded to 2 decimal places.
    """
    if n <= 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = (z * math.sqrt(max(0.0, (p * (1 - p) + z**2 / (4 * n)) / n))) / denom
    return (
        round(max(0.0, center - margin) * 100.0, 2),
        round(min(1.0, center + margin) * 100.0, 2),
    )


@dataclass
class StageMetrics:
    """Throughput and performance metrics for a specific reconciliation stage."""
    stage: int
    stage_name: str
    processed_count: int = 0
    total_time_ms: float = 0.0
    throughput_records_per_sec: float = 0.0

    def calculate_throughput(self) -> None:
        if self.total_time_ms > 0:
            self.throughput_records_per_sec = round(
                (self.processed_count / (self.total_time_ms / 1000.0)), 2
            )
        else:
            self.throughput_records_per_sec = 0.0


@dataclass
class EvaluationMetrics:
    """Comprehensive evaluation metrics report per PRD Section 17."""
    total_evaluated_cases: int = 0
    correct_verdicts: int = 0
    incorrect_verdicts: int = 0

    # Core performance percentages
    match_accuracy_pct: float = 0.0
    match_accuracy_ci_95: Tuple[float, float] = (0.0, 0.0)
    precision_pct: float = 0.0
    recall_pct: float = 0.0
    auto_resolution_rate_pct: float = 0.0
    exception_rate_pct: float = 0.0
    false_positive_rate_pct: float = 0.0

    # Categorical counts
    auto_resolved_count: int = 0
    unresolved_exception_count: int = 0

    # Confusion matrix components
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0

    # Stage throughputs (SEPARATED)
    stage1_metrics: StageMetrics = field(
        default_factory=lambda: StageMetrics(stage=1, stage_name="Stage 1 (Deterministic)")
    )
    stage2_metrics: StageMetrics = field(
        default_factory=lambda: StageMetrics(stage=2, stage_name="Stage 2 (AI Investigation)")
    )

    # Per-scenario breakdown
    scenario_breakdown: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics object to serializable dictionary."""
        return asdict(self)
