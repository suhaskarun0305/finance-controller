/**
 * AI Finance Controller — TypeScript Domain Types
 * ===============================================
 * Mirrors backend models and API contracts (PRD Section 8, 14, 16).
 */

export type MatchStatus =
  | 'MATCHED'
  | 'PARTIALLY_MATCHED'
  | 'RESOLVED_AFTER_INVESTIGATION'
  | 'NEEDS_HUMAN_REVIEW'
  | 'EXCEPTION'
  | 'UNMATCHED';

export type ResolutionMethod =
  | 'DETERMINISTIC'
  | 'AI_INVESTIGATION'
  | 'HUMAN_REVIEW'
  | 'HUMAN_OVERRIDE'
  | 'AUTOMATED_EXCEPTION';

export interface Payment {
  id: string;
  razorpay_payment_id: string;
  amount: number;
  currency: string;
  status: string;
  method?: string;
  payer_name?: string;
  payer_email?: string;
  order_id?: string;
  invoice_id?: string;
  customer_id?: string;
  payment_date: string;
  scenario_type?: string;
}

export interface Settlement {
  id: string;
  razorpay_settlement_id: string;
  payment_id?: string;
  gross_amount: number;
  fee: number;
  tax: number;
  net_amount: number;
  currency: string;
  status: string;
  utr?: string;
  settlement_date: string;
}

export interface ReconciliationRecord {
  id: string;
  payment_id?: string;
  invoice_id?: string;
  settlement_id?: string;
  match_status: MatchStatus;
  match_score?: number;
  match_method?: ResolutionMethod;
  stage: number;
  payment_amount?: number;
  settlement_amount?: number;
  discrepancy?: number;
  notes?: string;
  scenario_type?: string;
  created_at: string;
}

export interface CandidateItem {
  settlement_id?: string;
  invoice_id?: string;
  net_amount?: number;
  gross_amount?: number;
  settled_at?: string;
  source: string;
  score: number;
  notes?: string;
}

export interface TimelineStep {
  step: 'CANDIDATE_GEN' | 'DETERMINISTIC_CHECK' | 'AI_INVESTIGATION' | 'EVIDENCE_VALIDATION' | 'CONFIDENCE_ROUTING' | 'HUMAN_REVIEW';
  summary: string;
  actor?: string;
  timestamp?: string;
  input_snapshot?: Record<string, any>;
  output_snapshot?: Record<string, any>;
  evidence_refs?: string[];
}

export interface CaseDetail {
  reconciliation_id: string;
  payment: Payment;
  timeline: TimelineStep[];
  final_status: MatchStatus;
  notes?: string;
}

export interface ReviewQueueItem {
  reconciliation_id: string;
  payment_id?: string;
  razorpay_payment_id: string;
  payer_name?: string;
  amount_at_risk: number;
  currency: string;
  confidence: number;
  reason_code: string;
  status: string;
  created_at: string;
  notes?: string;
}

export interface MetricCard {
  title: string;
  value: string;
  target: string;
  status: 'OK' | 'WARN' | 'CRITICAL';
}

export interface EvaluationReport {
  total_evaluated_cases: number;
  correct_verdicts: number;
  incorrect_verdicts: number;
  match_accuracy_pct: number;
  match_accuracy_ci_95: [number, number];
  precision_pct: number;
  recall_pct: number;
  auto_resolution_rate_pct: number;
  exception_rate_pct: number;
  false_positive_rate_pct: number;
  true_positives: number;
  false_positives: number;
  true_negatives: number;
  false_negatives: number;
  scenario_breakdown: Record<string, {
    total: number;
    correct: number;
    accuracy_pct: number;
  }>;
}
