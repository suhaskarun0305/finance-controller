# AI Finance Controller — Track 04

> **Payment & Settlement Reconciliation Engine** with AI-Powered Exception Investigation, Evidence-Gated Confidence Routing, and Interactive Financial Operations Dashboard.

---

## Overview

The **AI Finance Controller** is an enterprise-grade financial reconciliation system that automatically matches payments against settlements, invoices, and refund records using a strict **two-stage pipeline**:

| Stage | Engine | Purpose | Coverage |
|-------|--------|---------|----------|
| **Stage 1** | Deterministic rules (5 priority-ordered checks) | Resolves clean matches, fees, refunds, multi-payment aggregation | ≥70% of transactions |
| **Stage 2** | AI Investigator Agent with 8 read-only tools | Investigates ambiguous cases: name mismatches, timing drift, chargebacks, missing invoices | Remaining ~30% |

Every AI-proposed resolution must pass an **independent 6-point evidence validation gate** before committing to the ledger:

1. **EXISTENCE** — Cited evidence IDs must exist in the database
2. **OWNERSHIP** — Evidence must belong to the payment under investigation
3. **AMOUNT_MATH** — Fee/refund arithmetic verified within ±₹1 tolerance
4. **TEMPORAL** — Timestamps within plausible horizons (≤45 days)
5. **IDEMPOTENCE** — Settlements not double-consumed by prior reconciliations
6. **CHECKSUM** — Evidence amounts explain the transaction delta

Verdicts are then routed by **calibrated confidence thresholds**:
- `≥ 0.95` + all 6 checks passed → **Auto-Resolve**
- `0.70 – 0.949` or validation failure → **Human Review Queue**
- `< 0.70` → **Exception Hold**

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  FastAPI Application (backend/main.py)                  │
│  ├── /api/v1/reconciliation   POST run, GET records     │
│  ├── /api/v1/exceptions       GET queue, POST decide    │
│  ├── /api/v1/metrics          GET summary, dashboard    │
│  ├── /api/v1/payments         GET list, detail          │
│  ├── /api/v1/settlements      GET list, detail          │
│  └── / (Dashboard UI)         Static HTML/CSS/JS        │
├─────────────────────────────────────────────────────────┤
│  Stage 1: Deterministic Matcher                         │
│  ├── Candidate Generator (amount/date/name proximity)   │
│  ├── 5 Priority Rules (exact, fee, refund, multi, part) │
│  └── Normalizer & Deduplicator                          │
├─────────────────────────────────────────────────────────┤
│  Stage 2: AI Investigator Agent                         │
│  ├── 8 Read-Only Tools (PRD Section 12.2)               │
│  ├── Structured Evidence Reasoning                      │
│  ├── 6-Point Evidence Validation Gate                   │
│  └── Confidence Routing (auto/review/exception)         │
├─────────────────────────────────────────────────────────┤
│  Services Layer                                         │
│  ├── AuditService (append-only immutable trail)         │
│  ├── ExceptionService (review queue & decisions)        │
│  ├── EvidenceService (scoped evidence collection)       │
│  ├── PaymentService & SettlementService                 │
│  └── EvaluationHarness (ground truth benchmarking)      │
├─────────────────────────────────────────────────────────┤
│  Database (SQLite local / PostgreSQL production)        │
│  └── SQLAlchemy ORM with dual-compatibility             │
└─────────────────────────────────────────────────────────┘
```

See [`docs/architecture.md`](docs/architecture.md) for the full system topology and pipeline diagrams.

---

## Quick Start

### Prerequisites

- **Python 3.11+**
- pip (Python package manager)

### 1. Install Dependencies

```bash
cd finance-controller
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your database settings (SQLite works out of the box)
```

### 3. Seed the Database

```bash
python scripts/seed_database.py
```

This creates the SQLite database (`finance_controller.db`) and populates it with synthetic financial data across 11 reconciliation scenarios (clean matches, fee deductions, partial payments, chargebacks, name mismatches, date drift, duplicates, etc.).

### 4. Run the Full Reconciliation Pipeline

```bash
python scripts/run_reconciliation.py
```

Executes the complete 2-stage pipeline:
- **Stage 1**: Deterministic rules processing all payments
- **Stage 2**: AI investigation on unresolved cases
- **Evaluation**: Benchmark metrics against ground truth

### 5. Start the Dashboard

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) to access the interactive dashboard.

---

## CLI Scripts

| Script | Purpose |
|--------|---------|
| `scripts/seed_database.py` | Create tables and seed synthetic data |
| `scripts/run_reconciliation.py` | Execute full 2-stage pipeline with evaluation |
| `scripts/run_benchmark.py` | Run evaluation harness against ground truth |
| `scripts/generate_data.py` | Generate synthetic datasets at configurable scales |
| `scripts/demo_stage2_investigation.py` | Demo Stage 2 AI investigation on a single payment |
| `scripts/test_db_connection.py` | Verify database connectivity |

---

## API Reference

### Reconciliation

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/reconciliation/run` | Run reconciliation (single or batch) |
| `GET` | `/api/v1/reconciliation/records` | List reconciliation records with filters |
| `GET` | `/api/v1/candidates/{payment_id}` | Get candidate settlements for a payment |

### Exceptions & Human Review

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/exceptions` | List open exceptions |
| `GET` | `/api/v1/review/queue` | Human review queue (sorted by amount-at-risk) |
| `POST` | `/api/v1/review/{reconciliation_id}/decide` | Process reviewer decision |

### Metrics & Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/metrics/summary` | Executive KPIs |
| `GET` | `/api/v1/dashboard/metrics-panel` | Formatted metric cards |
| `GET` | `/api/v1/dashboard/reconciliation-case/{id}` | Detailed case with timeline |

### Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/payments` | List payments |
| `GET` | `/api/v1/settlements` | List settlements |

Full OpenAPI documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## Dashboard

The interactive dashboard provides:

1. **KPI Header** — 4 real-time metric cards with PRD target comparisons
2. **Reconciliation Ledger** — Searchable, filterable transaction table with expandable case investigation traces
3. **Human Review Queue** — Exception cards sorted by amount-at-risk with Accept/Override actions
4. **Evaluation Benchmark** — Ground truth metrics with Wilson 95% confidence intervals and scenario breakdowns

---

## Testing

```bash
# Run all tests (33 unit + integration tests)
python -m unittest discover -s tests -v

# Run specific test suites
python -m unittest tests/unit/test_evidence_validation.py -v
python -m unittest tests/integration/test_reconciliation.py -v
python -m unittest tests/integration/test_investigation.py -v
```

---

## Project Structure

```
finance-controller/
├── backend/
│   ├── agents/           # Stage 2 AI Investigator, tools, validator, prompts
│   ├── api/              # FastAPI REST endpoints
│   ├── config/           # Application settings
│   ├── database/         # SQLAlchemy connection & session
│   ├── evaluation/       # Benchmark harness, metrics, reports
│   ├── models/           # SQLAlchemy ORM models
│   ├── reconciliation/   # Stage 1 matcher, rules, scorer, normalizer
│   ├── schemas/          # Pydantic request/response schemas
│   ├── services/         # Business logic services
│   ├── static/           # Dashboard HTML/CSS/JS
│   ├── workers/          # Background reconciliation workers
│   └── main.py           # FastAPI application entry point
├── data/                 # Generated reports, ground truth, raw data
├── docs/                 # Architecture, data model, demo script, evaluation
├── frontend/             # TypeScript types & API client scaffold
├── PRD/                  # Product Requirements Document
├── scripts/              # CLI pipeline & utility scripts
├── tests/                # Unit, integration, and evaluation tests
├── requirements.txt      # Python dependencies
└── docker-compose.yml    # Container orchestration
```

---

## Documentation

- [Architecture](docs/architecture.md) — System topology, pipeline diagrams, evidence gating
- [Data Model](docs/data-model.md) — Schema documentation, ER relationships
- [Demo Script](docs/demo-script.md) — 5-minute walkthrough for stakeholder demos
- [Evaluation](docs/evaluation.md) — Benchmark methodology, Wilson CI, ground truth isolation

---

## License

Internal use — Razorpay Engineering.
