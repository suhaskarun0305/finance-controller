# Evaluation Methodology — AI Finance Controller (Track 04)

## 1. Overview

The evaluation framework measures the accuracy, precision, and reliability of the two-stage reconciliation pipeline against an isolated **ground truth dataset** (`ground_truth_records`). The framework is designed to prevent self-grading data contamination and provide objective, statistically rigorous benchmarks.

---

## 2. Ground Truth Isolation Guarantee

To prevent data contamination (the system grading itself on data it had access to during processing):

1. **Isolated Table**: Ground truth records are stored in `ground_truth_records`, a separate SQLAlchemy model table.
2. **No Stage 1 Access**: Deterministic rules, candidate generator, and normalizer never query `ground_truth_records`.
3. **No Stage 2 Access**: AI Investigator tools (`get_payment`, `get_settlement`, etc.) are scoped to operational tables only.
4. **Post-Hoc Only**: The `Evaluator` class reads ground truth exclusively after all pipeline processing completes.

This guarantees that pipeline accuracy metrics reflect genuine predictive performance, not memorization or data leakage.

---

## 3. Evaluation Metrics

### 3.1 Core Metrics

| Metric | Definition | PRD Target |
|--------|-----------|------------|
| **Match Accuracy** | `correct_verdicts / total_evaluated` | ≥ 90% |
| **Precision** | `TP / (TP + FP)` — rate of auto-resolved verdicts that are correct | ≥ 95% |
| **Recall** | `TP / (TP + FN)` — rate of truly matching transactions the system identifies | ≥ 90% |
| **False Positive Rate** | `FP / (FP + TN)` — rate of incorrect auto-resolves | ≤ 1% |
| **False Negative Rate** | `FN / (FN + TP)` — rate of missed matches | ≤ 5% |
| **Auto-Resolution Rate** | Percentage of transactions resolved without human review | ≥ 85% |
| **Exception Rate** | Percentage routed to human review or exception hold | ≤ 15% |

### 3.2 Confusion Matrix

The evaluator builds a standard 2×2 confusion matrix:

```
                     Predicted Positive    Predicted Negative
                     (MATCHED/RESOLVED)    (UNRESOLVED/EXCEPTION)
Actual Positive         TP                     FN
(Should Match)
Actual Negative         FP                     TN
(Should Not Match)
```

- **TP (True Positive)**: System correctly matched a transaction that should be matched.
- **FP (False Positive)**: System incorrectly auto-resolved a transaction (most dangerous for financial systems).
- **FN (False Negative)**: System missed a valid match (sent to review unnecessarily).
- **TN (True Negative)**: System correctly identified a non-match.

### 3.3 Wilson 95% Confidence Intervals

All accuracy metrics are reported with **Wilson score 95% confidence intervals** to quantify statistical uncertainty, especially critical for small sample sizes.

The Wilson score interval for a proportion `p` with `n` observations is:

```
              p + z²/2n ± z × √(p(1-p)/n + z²/4n²)
CI_Wilson = ————————————————————————————————————————————
                         1 + z²/n
```

Where `z = 1.96` for 95% confidence.

**Why Wilson over Wald?**
- Wilson intervals are valid for small samples and proportions near 0 or 1.
- They never produce intervals outside [0, 1].
- They provide appropriate asymmetry for extreme proportions (e.g., 0% false positive rate).

---

## 4. Evaluation Scenarios

The benchmark evaluates across **11 reconciliation scenarios** representing the full spectrum of financial edge cases:

| # | Scenario | Description | Stage |
|---|----------|-------------|-------|
| 1 | `clean_match` | Exact 1:1 payment-invoice-settlement match | Stage 1 |
| 2 | `fee_deduction` | Gateway fee and tax deductions (gross - fee - tax = net) | Stage 1 |
| 3 | `refund` | Standard refund or partial refund reconciliation | Stage 1 |
| 4 | `many_to_one` | Multiple payments aggregated against a single invoice | Stage 1 |
| 5 | `partial_payment` | Split installment payments | Stage 1/2 |
| 6 | `name_mismatch` | Payer name differs from merchant name (abbreviations, typos) | Stage 2 |
| 7 | `date_drift` | Settlement delayed beyond normal window (>5 days) | Stage 2 |
| 8 | `chargeback` | Card network dispute / chargeback reversal | Stage 2 |
| 9 | `duplicate_transaction` | Re-ingested duplicate payment records | Stage 2 |
| 10 | `missing_invoice` | Payment without linked invoice record | Stage 2 |
| 11 | `missing_payment` | Invoice/settlement without corresponding payment | Stage 1 |

---

## 5. Running the Evaluation

### Full Pipeline with Evaluation

```bash
python scripts/run_reconciliation.py
```

This runs Stage 1 → Stage 2 → Evaluation in sequence, printing a formatted summary table.

### Standalone Benchmark

```bash
python scripts/run_benchmark.py
```

Evaluates the current state of `reconciliation_records` against `ground_truth_records` without re-running the pipeline.

### Output

The evaluation harness produces:
1. **Console Summary Table**: Human-readable metrics with target comparisons.
2. **JSON Report**: Machine-readable report saved to `data/generated/evaluation_report.json`.
3. **Dashboard Integration**: Metrics served via `GET /api/v1/metrics/summary` and rendered in the Evaluation Benchmark tab.

---

## 6. Evaluation Harness Implementation

### Core Classes

| Class | Module | Responsibility |
|-------|--------|----------------|
| `Evaluator` | `backend/evaluation/evaluator.py` | Orchestrates ground truth comparison, builds confusion matrix |
| `EvaluationMetrics` | `backend/evaluation/metrics.py` | Data classes for metrics, Wilson CI calculations |
| `format_summary_table` | `backend/evaluation/reports.py` | Formats console output table |
| `save_json_report` | `backend/evaluation/reports.py` | Serializes metrics to JSON |

### Evaluation Flow

```
1. Load all GroundTruthRecord entries
2. For each ground truth record:
   a. Find corresponding ReconciliationRecord (by payment_id)
   b. Compare expected_verdict vs actual match_status
   c. Classify as TP / FP / TN / FN
3. Aggregate per-scenario breakdowns
4. Calculate Wilson 95% CI for accuracy, precision, recall
5. Output summary + per-scenario accuracy table
```

---

## 7. Interpreting Results

### Key Indicators

- **High Precision (100%) with Lower Recall**: The system is conservative — it never incorrectly auto-resolves, but may send some valid matches to human review. This is the preferred operating mode for financial systems.
- **Scenario-Specific Accuracy**: Certain scenarios (e.g., `partial_payment`, `chargeback`) may show lower accuracy due to inherent ambiguity. These are expected to improve with richer evidence and model tuning.
- **Wilson CI Width**: Wider confidence intervals indicate insufficient sample size for that scenario. Increase synthetic data generation for under-represented scenarios.

### Performance Targets vs Current State

| Metric | PRD Target | Typical Result |
|--------|-----------|----------------|
| Deterministic Match Rate | ≥ 70% | ~86% |
| AI Investigation Accuracy | ≥ 90% | ~75% (improving) |
| False Positive Rate | ≤ 1% | 0% |
| Human Review Queue | ≤ 15% | ~4% |
| Throughput | ≥ 1k tx/min | ~1.2k tx/min |
