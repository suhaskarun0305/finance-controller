"""
Finance Controller — Normalizer Unit Tests
==========================================

Tests date parsing, currency standardization, and fuzzy merchant name normalization.
"""

import sys
import unittest
from datetime import datetime
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.reconciliation.normalizer import (
    normalize_date,
    normalize_currency,
    normalize_name,
    normalize_record,
)


class TestNormalizer(unittest.TestCase):

    def test_date_normalization(self):
        """Verify date parsing across various date string and timestamp formats."""
        # ISO string
        d1 = normalize_date("2025-01-15T14:30:00Z")
        self.assertEqual(d1.year, 2025)
        self.assertEqual(d1.month, 1)
        self.assertEqual(d1.day, 15)

        # Standard YYYY-MM-DD
        d2 = normalize_date("2025-06-20")
        self.assertEqual(d2.year, 2025)
        self.assertEqual(d2.month, 6)
        self.assertEqual(d2.day, 20)

        # Slash format DD/MM/YYYY
        d3 = normalize_date("25/12/2025")
        self.assertEqual(d3.year, 2025)
        self.assertEqual(d3.month, 12)
        self.assertEqual(d3.day, 25)

        # Invalid date should raise ValueError
        with self.assertRaises(ValueError):
            normalize_date("invalid-date-string")

    def test_currency_normalization(self):
        """Verify currency code standardization."""
        self.assertEqual(normalize_currency("inr"), "INR")
        self.assertEqual(normalize_currency("Rs."), "INR")
        self.assertEqual(normalize_currency("₹"), "INR")
        self.assertEqual(normalize_currency("usd"), "USD")
        self.assertEqual(normalize_currency("$"), "USD")
        self.assertEqual(normalize_currency(None), "INR")

    def test_near_duplicate_naming_normalization(self):
        """Verify fuzzy normalization strips suffixes and expands abbreviations."""
        v1 = normalize_name("Acme Technologies Pvt Ltd")
        v2 = normalize_name("Acme Tech Pvt. Ltd.")
        v3 = normalize_name("ACME TECHNOLOGIES PVT LTD")
        v4 = normalize_name("Acme Technologies Private Limited")

        # All four near-duplicate naming variants must normalize to identical string
        self.assertEqual(v1, "acme technologies")
        self.assertEqual(v2, "acme technologies")
        self.assertEqual(v3, "acme technologies")
        self.assertEqual(v4, "acme technologies")

        # Fresh Basket variants
        fb1 = normalize_name("Fresh Basket India")
        fb2 = normalize_name("Fresh Basket (India)")
        self.assertEqual(fb1, "fresh basket india")
        self.assertEqual(fb2, "fresh basket india")

    def test_normalize_record_complete(self):
        """Test full record dictionary normalization."""
        raw = {
            "amount": "1500.50",
            "currency": "rs.",
            "payment_date": "2025-03-10",
            "payer_name": "CloudServe Solutions Pvt. Ltd.",
        }
        clean = normalize_record(raw, record_type="payment")
        self.assertEqual(clean["amount"], 1500.50)
        self.assertEqual(clean["currency"], "INR")
        self.assertEqual(clean["normalized_payer_name"], "cloudserve solutions")


if __name__ == "__main__":
    unittest.main()
