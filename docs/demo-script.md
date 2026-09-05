# AI Finance Controller — Live Demo Script (Track 04)

This guide walks through demonstrating the AI Finance Controller system end-to-end to hackathon judges or finance stakeholders.

---

## 1. Environment Startup

Start the FastAPI application and dashboard:
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload
```
Open your browser to: **`http://localhost:8001`** (or `/dashboard`).

---

## 2. Walkthrough Flow (5-Minute Demonstration)

### Step 1: Executive KPI Panel (30 seconds)
- **Visual**: Point to the top 4 KPI cards matching PRD Section 3 & 26.8.
- **Narrative**:
  > *"Welcome to the AI Finance Controller for Razorpay Track 04. In high-volume payments, 70-80% of transactions are clean and should never touch an LLM. Our system uses a strict 2-stage architecture: Stage 1 resolves ~75% deterministically at over 1,200 transactions per minute, while Stage 2 invokes our AI Investigator Agent only for genuine edge cases."*

### Step 2: Triggering Full Reconciliation (45 seconds)
- **Action**: Click the **"Run Reconciliation"** button in the header (or run `python scripts/run_reconciliation.py` in the terminal).
- **Narrative**:
  > *"When reconciliation triggers, Stage 1 processes all payments across 5 deterministic rules (Exact Match, Fee Deductions, Refunds, Many-to-One, and Installments). Unmatched cases cleanly flow into Stage 2, where our AI Investigator gathers scoped evidence across settlements, invoices, and disputes."*

### Step 3: Inspecting AI Investigation & 6-Point Evidence Gate (90 seconds)
- **Action**: In the **Reconciliation Ledger** tab, find a row with status `RESOLVED_AFTER_INVESTIGATION` (e.g. `name_mismatch` or `duplicate_transaction`) and click **"View Trace"**.
- **Visual**: The side-over drawer opens displaying:
  1. Side-by-side Payment vs Settlement comparison.
  2. The **5-Step End-to-End Timeline**:
     - `CANDIDATE_GEN`: Surfaced candidates within ±5% amount and ±15 days.
     - `DETERMINISTIC_CHECK`: Checked rules, escalated to AI due to name variant.
     - `AI_INVESTIGATION`: Agent executed scoped tools and fuzzy similarity.
     - `EVIDENCE_VALIDATION`: 6-Point deterministic evidence gate.
     - `CONFIDENCE_ROUTING`: Auto-resolved due to high confidence (≥0.95).
  3. The **6-Point Checklist** badge grid (`EXISTENCE`, `OWNERSHIP`, `AMOUNT_MATH`, `TEMPORAL`, `IDEMPOTENCE`, `CHECKSUM`).
- **Narrative**:
  > *"Notice that the AI is not allowed to commit financial entries unchecked. Every proposed resolution passes our 6-point deterministic evidence gate. If any check fails or confidence drops below 95%, it is automatically downgraded to the Human Review Queue."*

### Step 4: Human Review & Specialist Override (60 seconds)
- **Action**: Switch to the **"Human Review Queue"** tab.
- **Visual**: Cards sorted by **Amount at Risk**.
- **Action**: Click **"✎ Override..."** on any card.
- **Visual**: The modal appears with a 2-step confirmation and a mandatory rationale textarea.
- **Action**: Enter a rationale: *"Verified manual bank credit advice UTR-98234"* and click **"Confirm & Record Audit"**.
- **Narrative**:
  > *"For cases in the 70-95% confidence zone, specialists have a bounded workbench. Every override strictly requires a rationale and writes an immutable entry into our append-only audit trail."*

### Step 5: Ground Truth Evaluation Benchmark (60 seconds)
- **Action**: Switch to the **"Evaluation Benchmark"** tab (or run `python scripts/run_benchmark.py`).
- **Visual**:
  - Match Accuracy: **~75%** with **Wilson 95% Confidence Intervals**.
  - Precision: **100.0%** (zero false positive auto-resolutions).
  - Recall: **~94.5%**.
  - Scenario-by-scenario breakdown table across clean match, fee deductions, chargebacks, duplicates, and refunds.
- **Narrative**:
  > *"Finally, our evaluation benchmark grades the pipeline against held-out ground truth records with zero data leakage. The system achieves 100% precision on auto-resolutions and reports separated throughputs for Stage 1 and Stage 2."*
