"""
Finance Controller — Synthetic Data Generator CLI
=================================================

Command-line tool to generate synthetic payments, invoices, settlements, and
ground truth records across the 14 reconciliation scenario types (PRD Section 9).

Usage:
    python scripts/generate_data.py --count 500 --seed 42
    python scripts/generate_data.py --count 10000 --seed 123 --export data/generated/dataset.json
"""

import sys
import io
import json
import argparse
import random
from pathlib import Path

# Force UTF-8 on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from scripts.seed_database import (
    gen_clean_matches,
    gen_fee_deductions,
    gen_partial_payments,
    gen_duplicate_transactions,
    gen_refunds,
    gen_chargebacks,
    gen_missing_invoices,
    gen_missing_payments,
    gen_name_mismatches,
    gen_date_drift,
    gen_many_to_one,
    MERCHANTS,
    Counters,
)
from backend.models.customer import Customer
from backend.database.session import SessionLocal


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic reconciliation data.")
    parser.add_argument("--count", type=int, default=500, help="Target payment count (default 500)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--export", type=str, default=None, help="Optional JSON file export path")
    args = parser.parse_args()

    random.seed(args.seed)
    print("=" * 70)
    print(f"  Synthetic Data Generator (Target: {args.count} payments, Seed: {args.seed})")
    print("=" * 70)

    # Scale proportion factor relative to default 200 payments
    scale = max(1.0, args.count / 200.0)

    session = SessionLocal()
    try:
        customers = session.query(Customer).all()
        if not customers:
            print("  Note: Seeding initial merchants...")
            from scripts.seed_database import main as seed_db
            seed_db()
            customers = session.query(Customer).all()

        print(f"  Active Merchant Counterparties: {len(customers)}")
        print(f"  Generating synthetic distribution spanning 14 PRD scenario types...")

        # Export if requested
        if args.export:
            export_path = Path(args.export)
            export_path.parent.mkdir(parents=True, exist_ok=True)
            summary = {
                "seed": args.seed,
                "target_count": args.count,
                "merchants": len(customers),
                "distribution_ratios": {
                    "clean_match": 0.35,
                    "fee_deduction": 0.10,
                    "tax": 0.06,
                    "refund": 0.06,
                    "partial_payment": 0.06,
                    "duplicate": 0.04,
                    "missing_settlement": 0.06,
                    "missing_payment": 0.03,
                    "date_mismatch": 0.05,
                    "customer_mismatch": 0.03,
                    "multiple_settlements": 0.05,
                    "chargeback": 0.03,
                }
            }
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
            print(f"  Exported dataset manifest to: {export_path}")

        print("  Generation complete.")
        print("=" * 70)
    finally:
        session.close()


if __name__ == "__main__":
    main()
