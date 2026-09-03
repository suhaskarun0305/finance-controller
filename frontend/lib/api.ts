/**
 * AI Finance Controller — Frontend API Client
 * ===========================================
 * Type-safe API client for backend REST endpoints.
 */

import {
  ReconciliationRecord,
  ReviewQueueItem,
  CaseDetail,
  EvaluationReport,
  MetricCard,
  CandidateItem,
} from '../types';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

export async function fetchMetricsPanel(): Promise<MetricCard[]> {
  const res = await fetch(`${BASE_URL}/api/v1/dashboard/metrics-panel`);
  if (!res.ok) throw new Error('Failed to fetch metrics panel');
  const data = await res.json();
  return data.panels;
}

export async function fetchReconciliationRecords(params?: {
  status?: string;
  stage?: number;
  limit?: number;
}): Promise<ReconciliationRecord[]> {
  const q = new URLSearchParams();
  if (params?.status) q.set('status', params.status);
  if (params?.stage) q.set('stage', params.stage.toString());
  if (params?.limit) q.set('limit', params.limit.toString());

  const res = await fetch(`${BASE_URL}/api/v1/reconciliation/records?${q.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch records');
  const data = await res.json();
  return data.items;
}

export async function fetchCaseDetail(caseId: string): Promise<CaseDetail> {
  const res = await fetch(`${BASE_URL}/api/v1/dashboard/reconciliation-case/${caseId}`);
  if (!res.ok) throw new Error(`Failed to fetch case ${caseId}`);
  return res.json();
}

export async function fetchReviewQueue(): Promise<ReviewQueueItem[]> {
  const res = await fetch(`${BASE_URL}/api/v1/review/queue`);
  if (!res.ok) throw new Error('Failed to fetch review queue');
  return res.json();
}

export async function submitReviewDecision(
  reconciliationId: string,
  decision: {
    action: 'ACCEPT' | 'OVERRIDE' | 'REQUEST_MORE_EVIDENCE';
    override_verdict?: string;
    rationale?: string;
    reviewer_id?: string;
  }
): Promise<{ reconciliation_id: string; new_status: string; audit_id: string }> {
  const res = await fetch(`${BASE_URL}/api/v1/review/${reconciliationId}/decide`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(decision),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to submit decision');
  }
  return res.json();
}

export async function fetchEvaluationReport(): Promise<EvaluationReport> {
  const res = await fetch(`${BASE_URL}/api/v1/evaluation/report`);
  if (!res.ok) throw new Error('Failed to fetch evaluation report');
  return res.json();
}

export async function runReconciliationBatch(): Promise<{ status: string; processed_count: number }> {
  const res = await fetch(`${BASE_URL}/api/v1/reconciliation/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ batch_mode: true }),
  });
  if (!res.ok) throw new Error('Failed to trigger reconciliation');
  return res.json();
}
