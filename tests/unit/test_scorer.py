"""
Finance Controller — Unit Tests for Candidate Scorer
====================================================
"""

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.reconciliation.scorer import (
    score_amount_proximity,
    score_date_proximity,
    calculate_composite_score,
)


class TestScorer(unittest.TestCase):

    def test_exact_amount_score(self):
        score = score_amount_proximity(1000.0, 1000.0)
        self.assertEqual(score, 1.0)

    def test_amount_within_tolerance(self):
        # 1000 vs 980 with 5% tolerance (max delta 50) -> delta 20 -> 1 - 20/50 = 0.60
        score = score_amount_proximity(1000.0, 980.0, tolerance_pct=0.05)
        self.assertAlmostEqual(score, 0.60, places=2)

    def test_amount_beyond_tolerance(self):
        score = score_amount_proximity(1000.0, 800.0, tolerance_pct=0.05)
        self.assertEqual(score, 0.0)

    def test_date_proximity_same_day(self):
        d = date(2025, 3, 1)
        score = score_date_proximity(d, d)
        self.assertEqual(score, 1.0)

    def test_date_proximity_within_window(self):
        d1 = date(2025, 3, 1)
        d2 = d1 + timedelta(days=3)
        score = score_date_proximity(d1, d2, max_window_days=15)
        self.assertAlmostEqual(score, 0.80, places=2)

    def test_date_proximity_beyond_window(self):
        d1 = date(2025, 3, 1)
        d2 = d1 + timedelta(days=20)
        score = score_date_proximity(d1, d2, max_window_days=15)
        self.assertEqual(score, 0.0)

    def test_composite_score(self):
        score = calculate_composite_score(amount_score=1.0, date_score=1.0, name_score=1.0)
        self.assertEqual(score, 1.0)

        # Weighted calculation: 0.5*0.8 + 0.3*0.6 + 0.2*1.0 = 0.40 + 0.18 + 0.20 = 0.78
        score = calculate_composite_score(amount_score=0.8, date_score=0.6, name_score=1.0)
        self.assertAlmostEqual(score, 0.78, places=2)


if __name__ == "__main__":
    unittest.main()
