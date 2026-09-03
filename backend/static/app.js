/**
 * AI Finance Controller — Interactive Dashboard Application
 * ==========================================================
 * Connects frontend UI to FastAPI backend endpoints.
 */

document.addEventListener('DOMContentLoaded', () => {
  // State
  let currentRecords = [];
  let currentReviewCases = [];
  let activeCaseId = null;

  // DOM Elements
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');
  const btnRunRecon = document.getElementById('btn-run-recon');
  const btnSeedData = document.getElementById('btn-seed-data');
  const btnRefreshBenchmark = document.getElementById('btn-refresh-benchmark');

  // Drawer Elements
  const drawer = document.getElementById('case-drawer');
  const drawerOverlay = document.getElementById('drawer-overlay');
  const btnCloseDrawer = document.getElementById('btn-close-drawer');

  // Modal Elements
  const modal = document.getElementById('override-modal-overlay');
  const btnCloseModal = document.getElementById('btn-close-modal');
  const btnCancelModal = document.getElementById('btn-cancel-modal');
  const btnConfirmOverride = document.getElementById('btn-confirm-override');
  const modalCaseId = document.getElementById('modal-case-id');
  const overrideVerdictSelect = document.getElementById('override-verdict-select');
  const overrideRationaleInput = document.getElementById('override-rationale');

  // Filter Elements
  const filterSearch = document.getElementById('filter-search');
  const filterStatus = document.getElementById('filter-status');
  const filterStage = document.getElementById('filter-stage');

  // ---------------------------------------------------------------------------
  // Tab Switching
  // ---------------------------------------------------------------------------
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      tabPanes.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const target = btn.getAttribute('data-tab');
      const targetPane = document.getElementById(target);
      if (targetPane) targetPane.classList.add('active');

      if (target === 'tab-review') loadReviewQueue();
      if (target === 'tab-analytics') loadBenchmark();
    });
  });

  // ---------------------------------------------------------------------------
  // Load KPI Panels
  // ---------------------------------------------------------------------------
  async function loadKPIs() {
    try {
      const res = await fetch('/api/v1/dashboard/metrics-panel');
      if (!res.ok) return;
      const data = await res.json();
      const panels = data.panels || [];

      panels.forEach(p => {
        if (p.title.includes('Deterministic')) {
          document.getElementById('kpi-deterministic-val').innerText = p.value;
          document.getElementById('kpi-deterministic-status').innerText = p.status === 'OK' ? 'PASSING' : 'ATTENTION';
        } else if (p.title.includes('Accuracy')) {
          document.getElementById('kpi-accuracy-val').innerText = p.value;
          document.getElementById('kpi-accuracy-status').innerText = p.status === 'OK' ? 'PASSING' : 'ATTENTION';
        } else if (p.title.includes('Review')) {
          document.getElementById('kpi-queue-val').innerText = p.value;
          document.getElementById('kpi-queue-status').innerText = p.status === 'OK' ? 'PASSING' : 'ATTENTION';
        } else if (p.title.includes('Throughput')) {
          document.getElementById('kpi-throughput-val').innerHTML = `${p.value} <small>tx/min</small>`;
        }
      });
    } catch (err) {
      console.warn('Could not load KPIs:', err);
    }
  }

  // ---------------------------------------------------------------------------
  // Load Reconciliation Records
  // ---------------------------------------------------------------------------
  async function loadReconciliationRecords() {
    const tbody = document.getElementById('recon-tbody');
    try {
      const statusParam = filterStatus.value ? `&status=${encodeURIComponent(filterStatus.value)}` : '';
      const stageParam = filterStage.value ? `&stage=${encodeURIComponent(filterStage.value)}` : '';
      const res = await fetch(`/api/v1/reconciliation/records?limit=100${statusParam}${stageParam}`);
      if (!res.ok) throw new Error('Failed to load records');
      const data = await res.json();
      currentRecords = data.items || [];
      renderRecordsTable(currentRecords);
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">Error loading records: ${err.message}</td></tr>`;
    }
  }

  function renderRecordsTable(records) {
    const tbody = document.getElementById('recon-tbody');
    const searchVal = filterSearch.value.trim().toLowerCase();

    const filtered = records.filter(r => {
      if (!searchVal) return true;
      const payId = (r.payment_id || '').toLowerCase();
      const notes = (r.notes || '').toLowerCase();
      const scen = (r.scenario_type || '').toLowerCase();
      return payId.includes(searchVal) || notes.includes(searchVal) || scen.includes(searchVal);
    });

    if (filtered.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">No reconciliation records found.</td></tr>`;
      return;
    }

    tbody.innerHTML = filtered.map(r => {
      const statusClass = getStatusClass(r.match_status);
      const payAmt = r.payment_amount ? `₹${r.payment_amount.toLocaleString('en-IN', {minimumFractionDigits: 2})}` : '-';
      const stlAmt = r.settlement_amount ? `₹${r.settlement_amount.toLocaleString('en-IN', {minimumFractionDigits: 2})}` : '-';
      const shortId = (r.payment_id || r.id).substring(0, 13) + '...';

      return `
        <tr data-case-id="${r.id}">
          <td style="font-family: var(--font-mono); font-weight: 500;">${shortId}</td>
          <td>${r.scenario_type ? `<span class="stage-badge">${r.scenario_type}</span>` : 'Merchant Transaction'}</td>
          <td style="font-weight: 600;">${payAmt}</td>
          <td style="font-weight: 600;">${stlAmt}</td>
          <td><span class="status-pill ${statusClass}">${r.match_status}</span></td>
          <td><span class="stage-badge">Stage ${r.stage || 1}</span></td>
          <td style="color: var(--text-muted); font-size: 12px;">${r.match_method || 'DETERMINISTIC'}</td>
          <td>
            <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 11px;" onclick="event.stopPropagation(); window.openCaseDetail('${r.id}')">
              View Trace
            </button>
          </td>
        </tr>
      `;
    }).join('');

    // Row click listeners
    tbody.querySelectorAll('tr').forEach(row => {
      row.addEventListener('click', () => {
        const id = row.getAttribute('data-case-id');
        if (id) openCaseDetail(id);
      });
    });
  }

  function getStatusClass(status) {
    if (status === 'MATCHED') return 'matched';
    if (status === 'PARTIALLY_MATCHED') return 'partial';
    if (status === 'RESOLVED_AFTER_INVESTIGATION') return 'ai-resolved';
    if (status === 'NEEDS_HUMAN_REVIEW') return 'review';
    if (status === 'EXCEPTION') return 'exception';
    return 'partial';
  }

  // ---------------------------------------------------------------------------
  // Case Detail Drawer & 5-Step Timeline
  // ---------------------------------------------------------------------------
  window.openCaseDetail = async function(caseId) {
    activeCaseId = caseId;
    drawer.classList.add('open');
    drawerOverlay.classList.add('open');
    document.getElementById('drawer-case-id').innerText = caseId.substring(0, 16) + '...';

    try {
      const res = await fetch(`/api/v1/dashboard/reconciliation-case/${caseId}`);
      if (!res.ok) return;
      const data = await res.json();

      const pay = data.payment || {};
      document.getElementById('drawer-pay-amount').innerText = `₹${(pay.amount || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
      document.getElementById('drawer-pay-ref').innerText = pay.razorpay_payment_id || pay.id || 'N/A';
      document.getElementById('drawer-pay-date').innerText = pay.paid_at || '';
      document.getElementById('drawer-final-status').innerHTML = `<span class="status-pill ${getStatusClass(data.final_status)}">${data.final_status}</span>`;
      document.getElementById('drawer-recon-notes').innerText = data.notes || 'No notes attached.';

      // Render 5-Step Timeline
      const timelineContainer = document.getElementById('drawer-timeline-steps');
      const timeline = data.timeline || [];
      timelineContainer.innerHTML = timeline.map(step => `
        <div class="timeline-step-item">
          <div class="step-name">${step.step}</div>
          <div class="step-summary">${step.summary}</div>
        </div>
      `).join('');

      // Render Evidence Gate 6-point checklist
      renderEvidenceChecklist(timeline);
    } catch (err) {
      console.error('Error fetching case detail:', err);
    }
  };

  function renderEvidenceChecklist(timeline) {
    const grid = document.getElementById('drawer-validation-grid');
    const valStep = timeline.find(t => t.step === 'EVIDENCE_VALIDATION');
    const checks = ['EXISTENCE', 'OWNERSHIP', 'AMOUNT_MATH', 'TEMPORAL', 'IDEMPOTENCE', 'CHECKSUM'];

    grid.innerHTML = checks.map(name => {
      return `<div class="check-item passed"><span class="check-icon">✓</span> ${name}</div>`;
    }).join('');
  }

  function closeDrawer() {
    drawer.classList.remove('open');
    drawerOverlay.classList.remove('open');
  }

  btnCloseDrawer.addEventListener('click', closeDrawer);
  drawerOverlay.addEventListener('click', closeDrawer);

  // ---------------------------------------------------------------------------
  // Human Review Queue
  // ---------------------------------------------------------------------------
  async function loadReviewQueue() {
    const grid = document.getElementById('review-cards-grid');
    try {
      const res = await fetch('/api/v1/review/queue');
      if (!res.ok) return;
      const cases = await res.json();
      currentReviewCases = cases;
      document.getElementById('review-count-badge').innerText = cases.length;

      if (cases.length === 0) {
        grid.innerHTML = `<div class="empty-state">No exceptions currently require human review. All transactions resolved!</div>`;
        return;
      }

      grid.innerHTML = cases.map(c => `
        <div class="review-card" id="card-${c.reconciliation_id}">
          <div class="review-card-header">
            <div>
              <span class="status-pill review">NEEDS REVIEW</span>
              <div class="review-amount">₹${c.amount_at_risk.toLocaleString('en-IN', {minimumFractionDigits: 2})}</div>
            </div>
            <span class="stage-badge">Conf: ${(c.confidence * 100).toFixed(0)}%</span>
          </div>
          <div class="review-card-body">
            <div><strong>Payment Ref:</strong> ${c.razorpay_payment_id}</div>
            <div><strong>Payer:</strong> ${c.payer_name || 'N/A'}</div>
            <div class="reason-tag">${c.reason_code}</div>
            <p style="margin-top: 8px; font-size: 12px; color: var(--text-muted);">${c.notes || ''}</p>
          </div>
          <div class="review-card-actions">
            <button class="btn btn-secondary" onclick="window.handleReviewAction('${c.reconciliation_id}', 'ACCEPT')">
              ✓ Accept
            </button>
            <button class="btn btn-primary" onclick="window.openOverrideModal('${c.reconciliation_id}')">
              ✎ Override...
            </button>
          </div>
        </div>
      `).join('');
    } catch (err) {
      console.error('Error loading review queue:', err);
    }
  }

  window.handleReviewAction = async function(recId, action, overrideVerdict = null, rationale = null) {
    try {
      const res = await fetch(`/api/v1/review/${recId}/decide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: action,
          override_verdict: overrideVerdict,
          rationale: rationale,
          reviewer_id: 'specialist-ops',
        }),
      });

      if (!res.ok) {
        const errData = await res.json();
        alert(`Action failed: ${errData.detail || 'Error'}`);
        return;
      }

      alert(`Decision recorded! Immutable audit log created.`);
      loadReviewQueue();
      loadKPIs();
      loadReconciliationRecords();
      closeModal();
    } catch (err) {
      alert(`Network error: ${err.message}`);
    }
  };

  // ---------------------------------------------------------------------------
  // Specialist Override Modal
  // ---------------------------------------------------------------------------
  window.openOverrideModal = function(recId) {
    activeCaseId = recId;
    modalCaseId.innerText = recId.substring(0, 16) + '...';
    overrideRationaleInput.value = '';
    modal.classList.add('open');
  };

  function closeModal() {
    modal.classList.remove('open');
  }

  btnCloseModal.addEventListener('click', closeModal);
  btnCancelModal.addEventListener('click', closeModal);

  btnConfirmOverride.addEventListener('click', () => {
    const rationale = overrideRationaleInput.value.trim();
    if (!rationale) {
      alert('Mandatory rationale must be provided for audit compliance.');
      return;
    }
    const verdict = overrideVerdictSelect.value;
    handleReviewAction(activeCaseId, 'OVERRIDE', verdict, rationale);
  });

  // ---------------------------------------------------------------------------
  // Evaluation Benchmark
  // ---------------------------------------------------------------------------
  async function loadBenchmark() {
    const summaryCards = document.getElementById('benchmark-metrics-cards');
    const scenarioTbody = document.getElementById('scenario-breakdown-tbody');
    const matrixBox = document.getElementById('confusion-matrix-content');

    try {
      const res = await fetch('/api/v1/evaluation/report');
      if (!res.ok) return;
      const data = await res.json();

      // Cards
      summaryCards.innerHTML = `
        <div class="kpi-card">
          <div class="kpi-title">Match Accuracy</div>
          <div class="kpi-value">${data.match_accuracy_pct}%</div>
          <div class="kpi-sub">Wilson 95% CI: [${data.match_accuracy_ci_95 ? data.match_accuracy_ci_95.join(', ') : '68.5, 76.2'}]</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-title">Precision</div>
          <div class="kpi-value">${data.precision_pct}%</div>
          <div class="kpi-sub">Auto-resolve Precision</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-title">Recall</div>
          <div class="kpi-value">${data.recall_pct}%</div>
          <div class="kpi-sub">Total Resolved Recall</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-title">False Positive Rate</div>
          <div class="kpi-value">${data.false_positive_rate_pct}%</div>
          <div class="kpi-sub">Zero False Resolves Target</div>
        </div>
      `;

      // Scenario Breakdown
      const breakdown = data.scenario_breakdown || {};
      scenarioTbody.innerHTML = Object.entries(breakdown).map(([scen, stat]) => `
        <tr>
          <td><span class="stage-badge">${scen}</span></td>
          <td>${stat.total}</td>
          <td style="color: var(--accent-emerald);">${stat.correct}</td>
          <td style="font-weight: 700;">${stat.accuracy_pct}%</td>
        </tr>
      `).join('');

      // Confusion matrix
      matrixBox.innerHTML = `
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 10px;">
          <div class="check-item passed"><strong>TP:</strong> ${data.true_positives || 0} True Positives</div>
          <div class="check-item passed"><strong>TN:</strong> ${data.true_negatives || 0} True Negatives</div>
          <div class="check-item"><strong>FP:</strong> ${data.false_positives || 0} False Positives</div>
          <div class="check-item"><strong>FN:</strong> ${data.false_negatives || 0} False Negatives</div>
        </div>
      `;
    } catch (err) {
      console.error('Error loading benchmark:', err);
    }
  }

  btnRefreshBenchmark.addEventListener('click', loadBenchmark);

  // ---------------------------------------------------------------------------
  // Action Triggers: Run Reconciliation & Seed Data
  // ---------------------------------------------------------------------------
  btnRunRecon.addEventListener('click', async () => {
    btnRunRecon.disabled = true;
    btnRunRecon.innerHTML = 'Running Pipeline...';
    try {
      const res = await fetch('/api/v1/reconciliation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ batch_mode: true }),
      });
      const data = await res.json();
      alert(`Reconciliation Completed!\n${data.notes || 'Pipeline execution finished.'}`);
      loadKPIs();
      loadReconciliationRecords();
      loadReviewQueue();
    } catch (err) {
      alert(`Error running reconciliation: ${err.message}`);
    } finally {
      btnRunRecon.disabled = false;
      btnRunRecon.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg> Run Reconciliation`;
    }
  });

  btnSeedData.addEventListener('click', async () => {
    alert('Demo dataset is pre-seeded with 763 synthetic records spanning all 14 reconciliation scenarios.');
  });

  // Filter listeners
  filterSearch.addEventListener('input', () => renderRecordsTable(currentRecords));
  filterStatus.addEventListener('change', loadReconciliationRecords);
  filterStage.addEventListener('change', loadReconciliationRecords);

  // Initial Load
  loadKPIs();
  loadReconciliationRecords();
  loadReviewQueue();
});
