"""
Finance Controller — Reconciliation Candidate Scorer
=====================================================

Provides scoring functions for ranking candidates based on amount proximity,
date proximity, and counterparty similarity.
"""

from datetime import datetime, date
from typing import Optional


def score_amount_proximity(
    amount_a: float,
    amount_b: float,
    tolerance_pct: float = 0.05,
) -> float:
    """
    Score amount similarity between 0.0 and 1.0.
    Exact match returns 1.0; delta beyond tolerance returns 0.0.
    """
    if amount_a <= 0 or amount_b <= 0:
        return 0.0
    delta = abs(amount_a - amount_b)
    if delta == 0:
        return 1.0

    max_delta = max(amount_a, amount_b) * tolerance_pct
    if max_delta == 0:
        return 0.0

    ratio = 1.0 - (delta / max_delta)
    return max(0.0, min(1.0, round(ratio, 4)))


def score_date_proximity(
    date_a: date | datetime,
    date_b: date | datetime,
    max_window_days: int = 15,
) -> float:
    """
    Score date closeness between 0.0 and 1.0.
    Same-day returns 1.0; difference beyond max_window_days returns 0.0.
    """
    d_a = date_a.date() if isinstance(date_a, datetime) else date_a
    d_b = date_b.date() if isinstance(date_b, datetime) else date_b

    days_diff = abs((d_a - d_b).days)
    if days_diff == 0:
        return 1.0
    if days_diff >= max_window_days:
        return 0.0

    score = 1.0 - (days_diff / max_window_days)
    return max(0.0, min(1.0, round(score, 4)))


def calculate_composite_score(
    amount_score: float,
    date_score: float,
    name_score: float = 1.0,
    weights: Optional[dict[str, float]] = None,
) -> float:
    """
    Calculate weighted composite score from component scores.
    Default weights: amount=0.5, date=0.3, name=0.2.
    """
    w = weights or {"amount": 0.50, "date": 0.30, "name": 0.20}
    total_w = sum(w.values())

    composite = (
        amount_score * w.get("amount", 0.5)
        + date_score * w.get("date", 0.3)
        + name_score * w.get("name", 0.2)
    ) / total_w

    return max(0.0, min(1.0, round(composite, 4)))
