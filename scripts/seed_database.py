"""
Finance Controller -- Synthetic Data & Ground Truth Seed Script
================================================================

Generates 400+ financial records with deliberately injected edge cases
for testing the reconciliation system AND populates the Ground Truth table.

Usage (from project root):
    python scripts/seed_database.py
"""

import sys
import io
import uuid
import random
import json
from pathlib import Path
from datetime import datetime, date, timedelta
from decimal import Decimal

# ---------------------------------------------------------------------------
# Force UTF-8 on Windows
# ---------------------------------------------------------------------------
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.models import (
    Base, Customer, Invoice, Payment, Settlement, Refund, Adjustment, GroundTruthRecord,
)
from backend.database.connection import engine
from backend.database.session import SessionLocal

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
random.seed(42)

# ---------------------------------------------------------------------------
# Helper constants
# ---------------------------------------------------------------------------
PAYMENT_METHODS = ["upi", "card", "netbanking", "wallet", "bank_transfer"]
CURRENCIES = ["INR"]
FEE_RATE = Decimal("0.02")   # 2% processing fee
TAX_ON_FEE = Decimal("0.18") # 18% GST on fee

BASE_DATE = date(2025, 1, 1)

MERCHANTS = [
    {
        "name": "Acme Technologies Pvt Ltd",
        "variants": ["Acme Technologies Pvt Ltd", "Acme Tech Pvt. Ltd.", "ACME TECHNOLOGIES PVT LTD", "Acme Technologies Private Limited"],
        "email": "billing@acmetech.in",
        "business_type": "saas",
    },
    {
        "name": "Fresh Basket India",
        "variants": ["Fresh Basket India", "FreshBasket India", "FRESH BASKET INDIA", "Fresh Basket (India)"],
        "email": "payments@freshbasket.com",
        "business_type": "ecommerce",
    },
    {
        "name": "CloudServe Solutions",
        "variants": ["CloudServe Solutions", "Cloud Serve Solutions", "Cloudserve Solutions Pvt Ltd", "CLOUDSERVE SOLUTIONS"],
        "email": "finance@cloudserve.io",
        "business_type": "saas",
    },
    {
        "name": "Metro Logistics Co",
        "variants": ["Metro Logistics Co", "Metro Logistics Co.", "METRO LOGISTICS CO", "Metro Logistics Company"],
        "email": "accounts@metrologistics.in",
        "business_type": "logistics",
    },
    {
        "name": "Sunrise Healthcare",
        "variants": ["Sunrise Healthcare", "Sunrise Health Care", "SUNRISE HEALTHCARE", "Sunrise Healthcare Pvt Ltd"],
        "email": "billing@sunrisehc.com",
        "business_type": "healthcare",
    },
]

PAYER_NAMES = [
    "Rajesh Kumar", "Priya Sharma", "Amit Patel", "Sneha Reddy",
    "Vikram Singh", "Anita Desai", "Rohit Gupta", "Meera Nair",
    "Sanjay Joshi", "Kavita Rao", "Arjun Menon", "Deepa Iyer",
    "Manish Agarwal", "Pooja Bhat", "Suresh Pillai",
]


def gen_id() -> str:
    return str(uuid.uuid4())

def rzp_payment_id() -> str:
    return f"pay_{uuid.uuid4().hex[:14]}"

def rzp_settlement_id() -> str:
    return f"setl_{uuid.uuid4().hex[:13]}"

def rzp_refund_id() -> str:
    return f"rfnd_{uuid.uuid4().hex[:13]}"

def invoice_number(seq: int) -> str:
    return f"INV-2025-{seq:05d}"

def order_id() -> str:
    return f"order_{uuid.uuid4().hex[:12]}"

def utr_number() -> str:
    return f"UTR{random.randint(100000000000, 999999999999)}"

def rand_date(start: date, spread_days: int = 180) -> date:
    return start + timedelta(days=random.randint(0, spread_days))

def rand_amount(lo: int = 500, hi: int = 50000) -> Decimal:
    return Decimal(str(random.randint(lo * 100, hi * 100) / 100)).quantize(Decimal("0.01"))

def compute_fee(amount: Decimal) -> tuple[Decimal, Decimal]:
    fee = (amount * FEE_RATE).quantize(Decimal("0.01"))
    tax = (fee * TAX_ON_FEE).quantize(Decimal("0.01"))
    return fee, tax


class Counters:
    inv_seq = 0
    records: dict[str, list] = {
        "customers": [], "invoices": [], "payments": [],
        "settlements": [], "refunds": [], "adjustments": [],
        "ground_truth": [],
    }
    scenario_counts: dict[str, dict[str, int]] = {}

    @classmethod
    def next_inv(cls) -> int:
        cls.inv_seq += 1
        return cls.inv_seq

    @classmethod
    def add(cls, table: str, obj, scenario: str):
        cls.records[table].append(obj)
        if scenario not in cls.scenario_counts:
            cls.scenario_counts[scenario] = {}
        cls.scenario_counts[scenario][table] = cls.scenario_counts[scenario].get(table, 0) + 1


def gen_clean_matches(customers: list[Customer], count: int = 60):
    scenario = "clean_match"
    for _ in range(count):
        cust = random.choice(customers)
        amt = rand_amount()
        d = rand_date(BASE_DATE)
        fee, tax = compute_fee(amt)

        inv = Invoice(
            id=gen_id(),
            invoice_number=invoice_number(Counters.next_inv()),
            customer_id=cust.id, amount=float(amt), currency="INR",
            status="paid", issue_date=d, due_date=d + timedelta(days=30),
            description="Standard service invoice", scenario_type=scenario,
        )
        Counters.add("invoices", inv, scenario)

        pay = Payment(
            id=gen_id(),
            razorpay_payment_id=rzp_payment_id(), order_id=order_id(),
            invoice_id=inv.id, customer_id=cust.id,
            amount=float(amt), currency="INR",
            method=random.choice(PAYMENT_METHODS), status="captured",
            fee=float(fee), tax=float(tax),
            payer_name=random.choice(PAYER_NAMES),
            payer_email=f"{random.choice(PAYER_NAMES).split()[0].lower()}@example.com",
            payment_date=datetime.combine(d + timedelta(days=random.randint(0, 2)), datetime.min.time()),
            description="Payment for invoice", scenario_type=scenario,
        )
        Counters.add("payments", pay, scenario)

        stl = Settlement(
            id=gen_id(),
            razorpay_settlement_id=rzp_settlement_id(),
            payment_id=pay.id,
            gross_amount=float(amt), fee=float(fee), tax=float(tax),
            net_amount=float(amt - fee - tax), currency="INR",
            status="processed", utr=utr_number(),
            settlement_date=d + timedelta(days=random.choice([1, 2, 3])),
            description="Normal settlement", scenario_type=scenario,
        )
        Counters.add("settlements", stl, scenario)

        gt = GroundTruthRecord(
            id=gen_id(),
            payment_id=pay.id, invoice_id=inv.id, settlement_id=stl.id,
            scenario_type=scenario, expected_verdict="MATCHED", expected_stage=1,
            expected_match_score=1.0,
            explanation="Direct 1:1 match between payment, invoice, and settlement.",
            fee_breakup_json=json.dumps({"gross": float(amt), "fee": float(fee), "tax": float(tax), "net": float(amt - fee - tax)}),
        )
        Counters.add("ground_truth", gt, scenario)


def gen_fee_deductions(customers: list[Customer], count: int = 15):
    scenario = "fee_deduction"
    for _ in range(count):
        cust = random.choice(customers)
        amt = rand_amount(1000, 80000)
        d = rand_date(BASE_DATE)
        high_fee = (amt * Decimal("0.035")).quantize(Decimal("0.01"))
        high_tax = (high_fee * TAX_ON_FEE).quantize(Decimal("0.01"))

        inv = Invoice(
            id=gen_id(),
            invoice_number=invoice_number(Counters.next_inv()),
            customer_id=cust.id, amount=float(amt), currency="INR",
            status="paid", issue_date=d, due_date=d + timedelta(days=30),
            scenario_type=scenario,
        )
        Counters.add("invoices", inv, scenario)

        pay = Payment(
            id=gen_id(),
            razorpay_payment_id=rzp_payment_id(), order_id=order_id(),
            invoice_id=inv.id, customer_id=cust.id,
            amount=float(amt), currency="INR",
            method=random.choice(PAYMENT_METHODS), status="captured",
            fee=float(high_fee), tax=float(high_tax),
            payer_name=random.choice(PAYER_NAMES),
            payment_date=datetime.combine(d, datetime.min.time()),
            scenario_type=scenario,
        )
        Counters.add("payments", pay, scenario)

        stl = Settlement(
            id=gen_id(),
            razorpay_settlement_id=rzp_settlement_id(),
            payment_id=pay.id,
            gross_amount=float(amt), fee=float(high_fee), tax=float(high_tax),
            net_amount=float(amt - high_fee - high_tax), currency="INR",
            status="processed", utr=utr_number(),
            settlement_date=d + timedelta(days=2),
            description="Settlement with elevated processing fee",
            scenario_type=scenario,
        )
        Counters.add("settlements", stl, scenario)

        gt = GroundTruthRecord(
            id=gen_id(),
            payment_id=pay.id, invoice_id=inv.id, settlement_id=stl.id,
            scenario_type=scenario, expected_verdict="MATCHED", expected_stage=1,
            expected_match_score=0.95,
            explanation="Gross payment matches invoice; net settlement reflects 3.5% fee + GST deduction.",
            fee_breakup_json=json.dumps({"gross": float(amt), "fee": float(high_fee), "tax": float(high_tax), "net": float(amt - high_fee - high_tax)}),
        )
        Counters.add("ground_truth", gt, scenario)


def gen_partial_payments(customers: list[Customer], count: int = 10):
    scenario = "partial_payment"
    for _ in range(count):
        cust = random.choice(customers)
        total_amt = rand_amount(5000, 50000)
        d = rand_date(BASE_DATE)
        num_parts = random.choice([2, 3])
        parts = []
        remaining = total_amt
        for i in range(num_parts - 1):
            part = (remaining * Decimal(str(random.uniform(0.2, 0.6)))).quantize(Decimal("0.01"))
            parts.append(part)
            remaining -= part
        parts.append(remaining)

        inv = Invoice(
            id=gen_id(),
            invoice_number=invoice_number(Counters.next_inv()),
            customer_id=cust.id, amount=float(total_amt), currency="INR",
            status="paid", issue_date=d, due_date=d + timedelta(days=30),
            description=f"Invoice paid in {num_parts} installments",
            scenario_type=scenario,
        )
        Counters.add("invoices", inv, scenario)

        for idx, part_amt in enumerate(parts):
            fee, tax = compute_fee(part_amt)
            pay_date = d + timedelta(days=idx * random.randint(3, 10))

            pay = Payment(
                id=gen_id(),
                razorpay_payment_id=rzp_payment_id(), order_id=order_id(),
                invoice_id=inv.id, customer_id=cust.id,
                amount=float(part_amt), currency="INR",
                method=random.choice(PAYMENT_METHODS), status="captured",
                fee=float(fee), tax=float(tax),
                payer_name=random.choice(PAYER_NAMES),
                payment_date=datetime.combine(pay_date, datetime.min.time()),
                description=f"Partial payment {idx + 1}/{num_parts}",
                scenario_type=scenario,
            )
            Counters.add("payments", pay, scenario)

            stl = Settlement(
                id=gen_id(),
                razorpay_settlement_id=rzp_settlement_id(),
                payment_id=pay.id,
                gross_amount=float(part_amt), fee=float(fee), tax=float(tax),
                net_amount=float(part_amt - fee - tax), currency="INR",
                status="processed", utr=utr_number(),
                settlement_date=pay_date + timedelta(days=2),
                scenario_type=scenario,
            )
            Counters.add("settlements", stl, scenario)

            gt = GroundTruthRecord(
                id=gen_id(),
                payment_id=pay.id, invoice_id=inv.id, settlement_id=stl.id,
                scenario_type=scenario, expected_verdict="PARTIALLY_MATCHED", expected_stage=1,
                expected_match_score=0.85,
                explanation=f"Installment payment {idx + 1}/{num_parts} of amount {float(part_amt)} against invoice total {float(total_amt)}.",
            )
            Counters.add("ground_truth", gt, scenario)


def gen_duplicate_transactions(customers: list[Customer], count: int = 8):
    scenario = "duplicate_transaction"
    for _ in range(count):
        cust = random.choice(customers)
        amt = rand_amount()
        d = rand_date(BASE_DATE)
        fee, tax = compute_fee(amt)
        shared_rzp_id = rzp_payment_id()
        shared_order = order_id()

        inv = Invoice(
            id=gen_id(),
            invoice_number=invoice_number(Counters.next_inv()),
            customer_id=cust.id, amount=float(amt), currency="INR",
            status="paid", issue_date=d, due_date=d + timedelta(days=30),
            scenario_type=scenario,
        )
        Counters.add("invoices", inv, scenario)

        p1 = None
        p2 = None
        for dup_idx in range(2):
            pay = Payment(
                id=gen_id(),
                razorpay_payment_id=shared_rzp_id,
                order_id=shared_order,
                invoice_id=inv.id, customer_id=cust.id,
                amount=float(amt), currency="INR",
                method=random.choice(PAYMENT_METHODS), status="captured",
                fee=float(fee), tax=float(tax),
                payer_name=random.choice(PAYER_NAMES),
                payment_date=datetime.combine(d, datetime.min.time()) + timedelta(seconds=dup_idx * 5),
                description=f"Duplicate ingestion #{dup_idx + 1}",
                scenario_type=scenario,
            )
            Counters.add("payments", pay, scenario)
            if dup_idx == 0:
                p1 = pay
            else:
                p2 = pay

        stl = Settlement(
            id=gen_id(),
            razorpay_settlement_id=rzp_settlement_id(),
            payment_id=None,
            gross_amount=float(amt), fee=float(fee), tax=float(tax),
            net_amount=float(amt - fee - tax), currency="INR",
            status="processed", utr=utr_number(),
            settlement_date=d + timedelta(days=2),
            description="Settlement for duplicated payment",
            scenario_type=scenario,
        )
        Counters.add("settlements", stl, scenario)

        gt1 = GroundTruthRecord(
            id=gen_id(),
            payment_id=p1.id, invoice_id=inv.id, settlement_id=stl.id,
            scenario_type=scenario, expected_verdict="MATCHED", expected_stage=1,
            expected_match_score=1.0,
            explanation="Original payment transaction correctly matched.",
        )
        Counters.add("ground_truth", gt1, scenario)

        gt2 = GroundTruthRecord(
            id=gen_id(),
            payment_id=p2.id, invoice_id=inv.id, settlement_id=None,
            scenario_type=scenario, expected_verdict="RESOLVED_AFTER_INVESTIGATION", expected_stage=2,
            expected_match_score=0.50,
            explanation="Duplicate transaction ingestion detected; flagged and resolved in Stage 2.",
        )
        Counters.add("ground_truth", gt2, scenario)


def gen_refunds(customers: list[Customer], count: int = 12):
    scenario = "refund"
    for _ in range(count):
        cust = random.choice(customers)
        amt = rand_amount()
        d = rand_date(BASE_DATE)
        fee, tax = compute_fee(amt)

        inv = Invoice(
            id=gen_id(),
            invoice_number=invoice_number(Counters.next_inv()),
            customer_id=cust.id, amount=float(amt), currency="INR",
            status="cancelled", issue_date=d, due_date=d + timedelta(days=30),
            scenario_type=scenario,
        )
        Counters.add("invoices", inv, scenario)

        pay = Payment(
            id=gen_id(),
            razorpay_payment_id=rzp_payment_id(), order_id=order_id(),
            invoice_id=inv.id, customer_id=cust.id,
            amount=float(amt), currency="INR",
            method=random.choice(PAYMENT_METHODS), status="refunded",
            fee=float(fee), tax=float(tax),
            payer_name=random.choice(PAYER_NAMES),
            payment_date=datetime.combine(d, datetime.min.time()),
            scenario_type=scenario,
        )
        Counters.add("payments", pay, scenario)

        rfnd = Refund(
            id=gen_id(),
            razorpay_refund_id=rzp_refund_id(),
            payment_id=pay.id, amount=float(amt), currency="INR",
            status="processed", refund_type="refund",
            reason=random.choice([
                "Customer requested cancellation",
                "Product not as described",
                "Duplicate charge",
                "Service not delivered",
            ]),
            refund_date=datetime.combine(d + timedelta(days=random.randint(1, 7)), datetime.min.time()),
            scenario_type=scenario,
        )
        Counters.add("refunds", rfnd, scenario)

        gt = GroundTruthRecord(
            id=gen_id(),
            payment_id=pay.id, invoice_id=inv.id, refund_id=rfnd.id,
            scenario_type=scenario, expected_verdict="MATCHED", expected_stage=1,
            expected_match_score=1.0,
            explanation="Refunded payment matched with refund object and cancelled invoice.",
        )
        Counters.add("ground_truth", gt, scenario)


def gen_chargebacks(customers: list[Customer], count: int = 6):
    scenario = "chargeback"
    for _ in range(count):
        cust = random.choice(customers)
        amt = rand_amount(2000, 30000)
        d = rand_date(BASE_DATE)
        fee, tax = compute_fee(amt)

        inv = Invoice(
            id=gen_id(),
            invoice_number=invoice_number(Counters.next_inv()),
            customer_id=cust.id, amount=float(amt), currency="INR",
            status="paid", issue_date=d, due_date=d + timedelta(days=30),
            scenario_type=scenario,
        )
        Counters.add("invoices", inv, scenario)

        pay = Payment(
            id=gen_id(),
            razorpay_payment_id=rzp_payment_id(), order_id=order_id(),
            invoice_id=inv.id, customer_id=cust.id,
            amount=float(amt), currency="INR",
            method="card", status="captured",
            fee=float(fee), tax=float(tax),
            payer_name=random.choice(PAYER_NAMES),
            payment_date=datetime.combine(d, datetime.min.time()),
            scenario_type=scenario,
        )
        Counters.add("payments", pay, scenario)

        stl = Settlement(
            id=gen_id(),
            razorpay_settlement_id=rzp_settlement_id(),
            payment_id=pay.id,
            gross_amount=float(amt), fee=float(fee), tax=float(tax),
            net_amount=float(amt - fee - tax), currency="INR",
            status="processed", utr=utr_number(),
            settlement_date=d + timedelta(days=2),
            scenario_type=scenario,
        )
        Counters.add("settlements", stl, scenario)

        rfnd = Refund(
            id=gen_id(),
            razorpay_refund_id=rzp_refund_id(),
            payment_id=pay.id, amount=float(amt), currency="INR",
            status="processed", refund_type="chargeback",
            reason="Chargeback initiated by card network",
            refund_date=datetime.combine(d + timedelta(days=random.randint(15, 45)), datetime.min.time()),
            scenario_type=scenario,
        )
        Counters.add("refunds", rfnd, scenario)

        gt = GroundTruthRecord(
            id=gen_id(),
            payment_id=pay.id, invoice_id=inv.id, settlement_id=stl.id, refund_id=rfnd.id,
            scenario_type=scenario, expected_verdict="RESOLVED_AFTER_INVESTIGATION", expected_stage=2,
            expected_match_score=0.60,
            explanation="Disputed payment requiring AI investigation into chargeback evidence and settlement clawback.",
        )
        Counters.add("ground_truth", gt, scenario)


def gen_missing_invoices(customers: list[Customer], count: int = 10):
    scenario = "missing_invoice"
    for _ in range(count):
        cust = random.choice(customers)
        amt = rand_amount()
        d = rand_date(BASE_DATE)
        fee, tax = compute_fee(amt)

        pay = Payment(
            id=gen_id(),
            razorpay_payment_id=rzp_payment_id(), order_id=order_id(),
            invoice_id=None,
            customer_id=cust.id,
            amount=float(amt), currency="INR",
            method=random.choice(PAYMENT_METHODS), status="captured",
            fee=float(fee), tax=float(tax),
            payer_name=random.choice(PAYER_NAMES),
            payment_date=datetime.combine(d, datetime.min.time()),
            description="Payment received with no matching invoice",
            scenario_type=scenario,
        )
        Counters.add("payments", pay, scenario)

        stl = Settlement(
            id=gen_id(),
            razorpay_settlement_id=rzp_settlement_id(),
            payment_id=pay.id,
            gross_amount=float(amt), fee=float(fee), tax=float(tax),
            net_amount=float(amt - fee - tax), currency="INR",
            status="processed", utr=utr_number(),
            settlement_date=d + timedelta(days=2),
            scenario_type=scenario,
        )
        Counters.add("settlements", stl, scenario)

        gt = GroundTruthRecord(
            id=gen_id(),
            payment_id=pay.id, invoice_id=None, settlement_id=stl.id,
            scenario_type=scenario, expected_verdict="RESOLVED_AFTER_INVESTIGATION", expected_stage=2,
            expected_match_score=0.40,
            explanation="Unmatched payment requiring Stage 2 AI agent to locate or generate matching invoice.",
        )
        Counters.add("ground_truth", gt, scenario)


def gen_missing_payments(customers: list[Customer], count: int = 10):
    scenario = "missing_payment"
    for _ in range(count):
        cust = random.choice(customers)
        amt = rand_amount()
        d = rand_date(BASE_DATE)

        inv = Invoice(
            id=gen_id(),
            invoice_number=invoice_number(Counters.next_inv()),
            customer_id=cust.id, amount=float(amt), currency="INR",
            status="overdue", issue_date=d, due_date=d + timedelta(days=30),
            description="Invoice with no payment received",
            scenario_type=scenario,
        )
        Counters.add("invoices", inv, scenario)

        gt = GroundTruthRecord(
            id=gen_id(),
            payment_id=None, invoice_id=inv.id, settlement_id=None,
            scenario_type=scenario, expected_verdict="EXCEPTION", expected_stage=1,
            expected_match_score=0.0,
            explanation="Overdue invoice with no matching payment ingested.",
        )
        Counters.add("ground_truth", gt, scenario)


def gen_name_mismatches(customers: list[Customer], merchants: list[dict], count: int = 12):
    scenario = "name_mismatch"
    for _ in range(count):
        merch_data = random.choice(merchants)
        cust = next(c for c in customers if c.name == merch_data["name"])
        amt = rand_amount()
        d = rand_date(BASE_DATE)
        fee, tax = compute_fee(amt)

        inv = Invoice(
            id=gen_id(),
            invoice_number=invoice_number(Counters.next_inv()),
            customer_id=cust.id, amount=float(amt), currency="INR",
            status="paid", issue_date=d, due_date=d + timedelta(days=30),
            description=f"Invoice from {cust.name}",
            scenario_type=scenario,
        )
        Counters.add("invoices", inv, scenario)

        variant = random.choice([v for v in merch_data["variants"] if v != cust.name])
        pay = Payment(
            id=gen_id(),
            razorpay_payment_id=rzp_payment_id(), order_id=order_id(),
            invoice_id=inv.id, customer_id=cust.id,
            amount=float(amt), currency="INR",
            method=random.choice(PAYMENT_METHODS), status="captured",
            fee=float(fee), tax=float(tax),
            payer_name=variant,
            reference_number=f"REF-{variant.replace(' ', '').upper()[:8]}-{random.randint(100,999)}",
            payment_date=datetime.combine(d, datetime.min.time()),
            description=f"Payment with name variant: {variant}",
            scenario_type=scenario,
        )
        Counters.add("payments", pay, scenario)

        stl = Settlement(
            id=gen_id(),
            razorpay_settlement_id=rzp_settlement_id(),
            payment_id=pay.id,
            gross_amount=float(amt), fee=float(fee), tax=float(tax),
            net_amount=float(amt - fee - tax), currency="INR",
            status="processed", utr=utr_number(),
            settlement_date=d + timedelta(days=2),
            scenario_type=scenario,
        )
        Counters.add("settlements", stl, scenario)

        gt = GroundTruthRecord(
            id=gen_id(),
            payment_id=pay.id, invoice_id=inv.id, settlement_id=stl.id,
            scenario_type=scenario, expected_verdict="RESOLVED_AFTER_INVESTIGATION", expected_stage=2,
            expected_match_score=0.75,
            explanation=f"Name spelling mismatch ('{variant}' vs '{cust.name}') resolved via Stage 2 fuzzy matching.",
        )
        Counters.add("ground_truth", gt, scenario)


def gen_date_drift(customers: list[Customer], count: int = 12):
    scenario = "date_drift"
    for _ in range(count):
        cust = random.choice(customers)
        amt = rand_amount()
        d = rand_date(BASE_DATE)
        fee, tax = compute_fee(amt)
        drift = random.randint(5, 15)

        inv = Invoice(
            id=gen_id(),
            invoice_number=invoice_number(Counters.next_inv()),
            customer_id=cust.id, amount=float(amt), currency="INR",
            status="paid", issue_date=d, due_date=d + timedelta(days=30),
            scenario_type=scenario,
        )
        Counters.add("invoices", inv, scenario)

        pay = Payment(
            id=gen_id(),
            razorpay_payment_id=rzp_payment_id(), order_id=order_id(),
            invoice_id=inv.id, customer_id=cust.id,
            amount=float(amt), currency="INR",
            method=random.choice(PAYMENT_METHODS), status="captured",
            fee=float(fee), tax=float(tax),
            payer_name=random.choice(PAYER_NAMES),
            payment_date=datetime.combine(d, datetime.min.time()),
            description=f"Payment with {drift}-day settlement drift",
            scenario_type=scenario,
        )
        Counters.add("payments", pay, scenario)

        stl = Settlement(
            id=gen_id(),
            razorpay_settlement_id=rzp_settlement_id(),
            payment_id=pay.id,
            gross_amount=float(amt), fee=float(fee), tax=float(tax),
            net_amount=float(amt - fee - tax), currency="INR",
            status="processed", utr=utr_number(),
            settlement_date=d + timedelta(days=drift),
            description=f"Delayed settlement ({drift} days)",
            scenario_type=scenario,
        )
        Counters.add("settlements", stl, scenario)

        gt = GroundTruthRecord(
            id=gen_id(),
            payment_id=pay.id, invoice_id=inv.id, settlement_id=stl.id,
            scenario_type=scenario, expected_verdict="RESOLVED_AFTER_INVESTIGATION", expected_stage=2,
            expected_match_score=0.80,
            explanation=f"Settlement date drifted by {drift} days beyond standard window; resolved via Stage 2 AI window expansion.",
        )
        Counters.add("ground_truth", gt, scenario)


def gen_many_to_one(customers: list[Customer], count: int = 8):
    scenario = "many_to_one"
    for _ in range(count):
        cust = random.choice(customers)
        num_txns = random.choice([3, 4, 5])
        d = rand_date(BASE_DATE)

        total = Decimal("0")
        payments_list = []
        for i in range(num_txns):
            amt = rand_amount(500, 10000)
            total += amt
            fee, tax = compute_fee(amt)

            pay = Payment(
                id=gen_id(),
                razorpay_payment_id=rzp_payment_id(), order_id=order_id(),
                invoice_id=None,
                customer_id=cust.id,
                amount=float(amt), currency="INR",
                method=random.choice(PAYMENT_METHODS), status="captured",
                fee=float(fee), tax=float(tax),
                payer_name=random.choice(PAYER_NAMES),
                payment_date=datetime.combine(d + timedelta(days=i), datetime.min.time()),
                description=f"Txn {i+1}/{num_txns} for combined invoice",
                scenario_type=scenario,
            )
            Counters.add("payments", pay, scenario)
            payments_list.append((pay, amt, fee, tax))

        inv = Invoice(
            id=gen_id(),
            invoice_number=invoice_number(Counters.next_inv()),
            customer_id=cust.id, amount=float(total), currency="INR",
            status="paid", issue_date=d, due_date=d + timedelta(days=30),
            description=f"Invoice covered by {num_txns} transactions",
            scenario_type=scenario,
        )
        Counters.add("invoices", inv, scenario)

        for pay, amt, fee, tax in payments_list:
            pay.invoice_id = inv.id

            stl = Settlement(
                id=gen_id(),
                razorpay_settlement_id=rzp_settlement_id(),
                payment_id=pay.id,
                gross_amount=float(amt), fee=float(fee), tax=float(tax),
                net_amount=float(amt - fee - tax), currency="INR",
                status="processed", utr=utr_number(),
                settlement_date=d + timedelta(days=random.randint(2, 4)),
                scenario_type=scenario,
            )
            Counters.add("settlements", stl, scenario)

            gt = GroundTruthRecord(
                id=gen_id(),
                payment_id=pay.id, invoice_id=inv.id, settlement_id=stl.id,
                scenario_type=scenario, expected_verdict="MATCHED", expected_stage=1,
                expected_match_score=0.90,
                explanation=f"Transaction part of {num_txns}-payment set totaling {float(total)} covering invoice.",
            )
            Counters.add("ground_truth", gt, scenario)


def main() -> None:
    print("=" * 75)
    print("  Finance Controller -- Synthetic Data & Ground Truth Seed Script")
    print("=" * 75)
    print()

    print("[1/3] Resetting database tables ...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("      Tables ready.\n")

    print("[2/3] Generating synthetic data & ground truth ...")
    customers = []
    for m in MERCHANTS:
        cust = Customer(
            id=gen_id(),
            name=m["name"],
            display_name=m["variants"][1],
            email=m["email"],
            business_type=m["business_type"],
            razorpay_merchant_id=f"merch_{uuid.uuid4().hex[:10]}",
        )
        customers.append(cust)
        Counters.add("customers", cust, "merchant")

    gen_clean_matches(customers, count=60)
    gen_fee_deductions(customers, count=15)
    gen_partial_payments(customers, count=10)
    gen_duplicate_transactions(customers, count=8)
    gen_refunds(customers, count=12)
    gen_chargebacks(customers, count=6)
    gen_missing_invoices(customers, count=10)
    gen_missing_payments(customers, count=10)
    gen_name_mismatches(customers, MERCHANTS, count=12)
    gen_date_drift(customers, count=12)
    gen_many_to_one(customers, count=8)

    print("      Generation complete.\n")

    print("[3/3] Inserting into database ...")
    session = SessionLocal()
    try:
        for table in ["customers", "invoices", "payments", "settlements", "refunds", "adjustments", "ground_truth"]:
            objs = Counters.records[table]
            if objs:
                session.add_all(objs)
                session.flush()
        session.commit()
        print("      Committed successfully.\n")
    except Exception as exc:
        session.rollback()
        print(f"      [FAIL] {exc}\n")
        raise
    finally:
        session.close()

    print("=" * 75)
    print("  SUMMARY: Records Generated Per Scenario")
    print("=" * 75)
    print()
    print(f"  {'Scenario':<24} {'Cust':>4} {'Inv':>4} {'Pay':>4} {'Stl':>4} {'Rfnd':>4} {'GT':>4} {'Total':>6}")
    print("  " + "-" * 67)

    grand_total = 0
    for scenario, counts in sorted(Counters.scenario_counts.items()):
        row_total = sum(counts.values())
        grand_total += row_total
        print(
            f"  {scenario:<24}"
            f" {counts.get('customers', 0):>4}"
            f" {counts.get('invoices', 0):>4}"
            f" {counts.get('payments', 0):>4}"
            f" {counts.get('settlements', 0):>4}"
            f" {counts.get('refunds', 0):>4}"
            f" {counts.get('ground_truth', 0):>4}"
            f" {grand_total:>6}"
        )

    print("  " + "-" * 67)

    table_totals = {}
    for counts in Counters.scenario_counts.values():
        for t, n in counts.items():
            table_totals[t] = table_totals.get(t, 0) + n

    print(
        f"  {'TOTAL':<24}"
        f" {table_totals.get('customers', 0):>4}"
        f" {table_totals.get('invoices', 0):>4}"
        f" {table_totals.get('payments', 0):>4}"
        f" {table_totals.get('settlements', 0):>4}"
        f" {table_totals.get('refunds', 0):>4}"
        f" {table_totals.get('ground_truth', 0):>4}"
        f" {grand_total:>6}"
    )
    print()
    print("=" * 75)
    print("  Seeding complete!")
    print("=" * 75)


if __name__ == "__main__":
    main()
