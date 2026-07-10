/** Znacznik czasu transmisji: ddmmyyyyggmmss */
export function formatTransmissionMarker(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  const pad = (n) => String(n).padStart(2, '0');
  return (
    `${pad(d.getDate())}${pad(d.getMonth() + 1)}${d.getFullYear()}`
    + `${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
  );
}

export function formatDateShort(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`;
}

const WEEKDAYS_PL = [
  'niedziela',
  'poniedziałek',
  'wtorek',
  'środa',
  'czwartek',
  'piątek',
  'sobota',
];

/** Data + dzień tygodnia + godzina dla widoku operatora. */
export function formatDateTimeWithWeekday(value) {
  if (!value) return { dateLine: '—', timeLine: '' };
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return { dateLine: '—', timeLine: '' };
  const pad = (n) => String(n).padStart(2, '0');
  const dateLine = `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} (${WEEKDAYS_PL[d.getDay()]})`;
  const timeLine = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  return { dateLine, timeLine };
}

function startOfLocalDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

/**
 * Prezentacja „ludzka”: Dzisiaj / Wczoraj / pełna data + dzień tygodnia + godzina.
 * @param {string|Date} value
 * @param {Date} [now] — punkt odniesienia (testy)
 */
export function formatOperatorDateTime(value, now = new Date()) {
  if (!value) return { dateLine: '—', timeLine: '' };
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return { dateLine: '—', timeLine: '' };

  const pad = (n) => String(n).padStart(2, '0');
  const timeLine = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  const weekday = WEEKDAYS_PL[d.getDay()];
  const dayMs = 86_400_000;
  const diffDays = Math.round((startOfLocalDay(now).getTime() - startOfLocalDay(d).getTime()) / dayMs);

  let dateLine;
  if (diffDays === 0) {
    dateLine = `Dzisiaj (${weekday})`;
  } else if (diffDays === 1) {
    dateLine = `Wczoraj (${weekday})`;
  } else {
    dateLine = `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} (${weekday})`;
  }
  return { dateLine, timeLine };
}

export function formatOperatorDateTimeDisplay(value, now = new Date()) {
  const { dateLine, timeLine } = formatOperatorDateTime(value, now);
  if (!timeLine) return dateLine;
  return `${dateLine}\n${timeLine}`;
}

export function formatDateTimeDisplay(value) {
  return formatOperatorDateTimeDisplay(value);
}

const PURCHASE_OPS = new Set([
  'PURCHASE_SYNC_MANUAL',
  'PURCHASE_SYNC_AUTO',
  'PURCHASE_METADATA_FETCH',
  'PURCHASE_INVOICE_FETCH',
  'PURCHASE_IMPORT_SUMMARY',
  'RESUME',
]);

const SALE_OPS = new Set([
  'SALE_SEND',
  'SALE_STATUS',
  'UPO_DOWNLOAD',
  'RETRY',
]);

const SESSION_OPS = new Set([
  'SESSION_OPEN',
  'SESSION_CLOSE',
  'SESSION_REFRESH',
  'SESSION_EXPIRED',
  'SESSION_RENEWED',
]);

const SCHEDULER_OPS = new Set([
  'SCHEDULER_STARTED',
  'SCHEDULER_TICK',
  'SCHEDULER_SLOT',
  'SCHEDULER_ENQUEUE',
  'SCHEDULER_SKIP_ALREADY_EXECUTED',
  'SCHEDULER_RECOVERY',
  'SCHEDULER_DISABLED',
  'SCHEDULER_INVALID_CRON',
]);

export const MONITOR_FILTERS = [
  { key: 'all', label: 'Wszystkie' },
  { key: 'sale', label: 'Sprzedaż' },
  { key: 'purchase', label: 'Zakupy' },
  { key: 'active', label: 'Aktywne' },
  { key: 'errors', label: 'Błędy' },
  { key: 'finished', label: 'Zakończone' },
];

const OPERATION_LABELS = {
  SALE_SEND: 'Wysyłka faktury',
  SALE_STATUS: 'Status KSeF',
  UPO_DOWNLOAD: 'Pobranie UPO',
  SESSION_OPEN: 'Otwarcie sesji',
  SESSION_CLOSE: 'Zamknięcie sesji',
  SESSION_REFRESH: 'Odświeżenie sesji',
  SESSION_EXPIRED: 'Sesja wygasła',
  SESSION_RENEWED: 'Sesja odnowiona',
  PURCHASE_SYNC_MANUAL: 'Synchronizacja zakupów',
  PURCHASE_SYNC_AUTO: 'Synchronizacja zakupów',
  PURCHASE_METADATA_FETCH: 'Pobranie metadanych zakupów',
  PURCHASE_INVOICE_FETCH: 'Pobranie XML zakupu',
  PURCHASE_IMPORT_SUMMARY: 'Podsumowanie importu',
  RETRY: 'Ponowienie',
  RESUME: 'Wznowienie',
  ERROR: 'Błąd',
  SCHEDULER_STARTED: 'Harmonogram — start',
  SCHEDULER_SLOT: 'Harmonogram — slot',
  SCHEDULER_ENQUEUE: 'Harmonogram — kolejka',
};

export function operationLabel(operationType) {
  if (!operationType) return 'Operacja KSeF';
  return OPERATION_LABELS[operationType] || operationType.replace(/_/g, ' ');
}

export function isPurchaseOperation(operationType) {
  return PURCHASE_OPS.has(operationType);
}

export function isSaleOperation(operationType) {
  return SALE_OPS.has(operationType);
}

function groupHasAny(rows, set) {
  return rows.some((row) => set.has(row.operation_type));
}

export function deriveProcessTitle(rows) {
  if (!rows.length) return 'Operacja KSeF';
  if (groupHasAny(rows, PURCHASE_OPS)) return 'Synchronizacja zakupów';
  if (groupHasAny(rows, SALE_OPS)) return 'Wysyłka sprzedaży';
  if (groupHasAny(rows, SESSION_OPS)) return 'Sesja KSeF';
  if (groupHasAny(rows, SCHEDULER_OPS)) return 'Harmonogram KSeF';
  return operationLabel(rows[0].operation_type);
}

export function groupMatchesFilter(group, filterKey = 'all') {
  if (!group) return false;
  const key = String(filterKey || 'all').toLowerCase();
  if (key === 'all') return true;

  const rows = Array.isArray(group.rows) ? group.rows : [];
  const statusKey = String(group.status?.key || '').toLowerCase();

  if (key === 'sale') return rows.some((row) => isSaleOperation(row.operation_type));
  if (key === 'purchase') return rows.some((row) => isPurchaseOperation(row.operation_type));
  if (key === 'active') return statusKey === 'running';
  if (key === 'errors') return statusKey === 'error' || statusKey === 'warning';
  if (key === 'finished') return statusKey === 'success' || statusKey === 'neutral';
  return true;
}

function buildGroupSearchText(group) {
  if (!group) return '';
  const rows = Array.isArray(group.rows) ? group.rows : [];
  const invoices = extractInvoicesFromRows(rows);
  const parts = [
    group.key,
    group.marker,
    group.title,
    group.status?.label,
    group.status?.key,
    ...rows.flatMap((row) => [
      row.id,
      row.transmission_id,
      row.correlation_id,
      row.job_id,
      row.ksef_reference_number,
      row.invoice_number_local,
    ]),
    ...invoices.flatMap((invoice) => [
      invoice.number,
      invoice.counterparty,
      invoice.ksefRef,
    ]),
  ];
  return parts
    .filter((value) => value != null && String(value).trim() !== '')
    .map((value) => String(value).toLowerCase())
    .join(' ');
}

export function groupMatchesSearch(group, query = '') {
  const needle = String(query || '').trim().toLowerCase();
  if (!needle) return true;
  return buildGroupSearchText(group).includes(needle);
}

export function filterAndSearchGroups(groups, filterKey = 'all', query = '') {
  return (groups || [])
    .filter((group) => groupMatchesFilter(group, filterKey))
    .filter((group) => groupMatchesSearch(group, query));
}

const PROGRESS_STEP_MODELS = {
  purchase: [
    { key: 'session', label: 'Sesja', match: (row) => String(row.operation_type || '').startsWith('SESSION_') },
    {
      key: 'metadata',
      label: 'Metadata',
      match: (row) => String(row.operation_type || '').includes('PURCHASE_METADATA'),
    },
    {
      key: 'xml',
      label: 'XML',
      match: (row) => String(row.operation_type || '').includes('PURCHASE_INVOICE_FETCH'),
    },
    {
      key: 'import',
      label: 'Import',
      match: (row) => String(row.operation_type || '').includes('PURCHASE_IMPORT'),
    },
    { key: 'summary', label: 'Podsumowanie', match: (row) => String(row.operation_type || '').includes('SUMMARY') },
  ],
  sale: [
    { key: 'prepare', label: 'Przygotowanie', match: (row) => String(row.operation_type || '').includes('SALE_SEND') },
    { key: 'send', label: 'Wysyłka', match: (row) => String(row.operation_type || '').includes('SALE_SEND') },
    { key: 'status', label: 'Status', match: (row) => String(row.operation_type || '').includes('SALE_STATUS') },
    {
      key: 'upo',
      label: 'UPO',
      match: (row) => String(row.operation_type || '').includes('UPO') || row.upo_status === 'fetched',
    },
    { key: 'summary', label: 'Podsumowanie', match: (row) => String(row.operation_type || '').includes('SUMMARY') },
  ],
  generic: [
    { key: 'start', label: 'Start', match: (_row, index) => index === 0 },
    { key: 'process', label: 'Przetwarzanie', match: (_row, index, rows) => rows.length > 1 && index < rows.length - 1 },
    { key: 'finish', label: 'Zakończenie', match: (_row, index, rows) => index === rows.length - 1 },
  ],
};

function rowLooksActive(row) {
  return isRowActivelyRunning(row, false) || rowStatus(row) === 'waiting_status';
}

function rowLooksWarning(row) {
  return isRowWarning(row);
}

function rowLooksFailed(row) {
  return isRowFailure(row);
}

function rowLooksDone(row) {
  return isRowSuccess(row);
}

function rowLooksSkipped(row) {
  return rowStatus(row) === 'skipped';
}

function deriveStepStatus(rows) {
  if (!rows.length) return 'pending';
  if (rows.some(rowLooksFailed)) return 'failed';
  if (rows.some(rowLooksWarning)) return 'warning';
  if (rows.some(rowLooksActive)) return 'active';
  if (rows.some(rowLooksDone)) return 'done';
  if (rows.some(rowLooksSkipped)) return 'skipped';
  return 'pending';
}

function normalizeProgressTone(stepStatuses, groupStatusKey) {
  if (stepStatuses.includes('failed') || groupStatusKey === 'error') return 'danger';
  if (stepStatuses.includes('warning') || groupStatusKey === 'warning') return 'warning';
  if (groupStatusKey === 'running' || stepStatuses.includes('active')) return 'info';
  if (groupStatusKey === 'success') return 'success';
  return 'neutral';
}

function progressPercent(steps, groupStatusKey) {
  if (!steps.length) return 0;
  if (groupStatusKey === 'success') return 100;
  const doneCount = steps.filter((s) => s.status === 'done' || s.status === 'skipped').length;
  const activeCount = steps.filter((s) => s.status === 'active').length;
  const base = (doneCount / steps.length) * 100;
  const activeBonus = activeCount > 0 ? (0.5 / steps.length) * 100 : 0;
  return Math.max(0, Math.min(99, Math.round(base + activeBonus)));
}

function buildTitleFromSteps(steps) {
  return steps.map((step) => `${step.label}: ${step.status}`).join(' | ');
}

/**
 * Wylicza postęp procesu na bazie istniejących zdarzeń w grupie (frontend-only).
 * Zwraca strukturę prezentacyjną do renderu subtelnego paska postępu.
 */
export function deriveProcessProgress(group) {
  if (!group || !Array.isArray(group.rows) || group.rows.length === 0) {
    return {
      percent: 0,
      tone: 'neutral',
      label: 'Brak danych',
      steps: [],
      fallback: true,
      title: 'Brak danych etapów',
    };
  }

  const rows = group.rows;
  const title = String(group.title || '').toLowerCase();
  const groupStatusKey = String(group.status?.key || '').toLowerCase();

  const model = title.includes('zakup')
    ? PROGRESS_STEP_MODELS.purchase
    : title.includes('sprzedaż')
      ? PROGRESS_STEP_MODELS.sale
      : PROGRESS_STEP_MODELS.generic;

  const steps = model.map((spec) => {
    const matchedRows = rows.filter((row, index) => spec.match(row, index, rows));
    return {
      key: spec.key,
      label: spec.label,
      status: deriveStepStatus(matchedRows),
    };
  });

  const anyRecognized = steps.some((step) => step.status !== 'pending');
  const fallback = !anyRecognized && model !== PROGRESS_STEP_MODELS.generic;

  if (fallback) {
    const eventCount = rows.length;
    const statusSteps = [
      { key: 'events', label: 'Zdarzenia', status: groupStatusKey === 'running' ? 'active' : 'pending' },
      { key: 'result', label: 'Wynik', status: groupStatusKey === 'success' ? 'done' : groupStatusKey === 'error' ? 'failed' : 'pending' },
    ];
    const tone = normalizeProgressTone(statusSteps.map((s) => s.status), groupStatusKey);
    const percent = groupStatusKey === 'success' ? 100 : Math.min(95, Math.round((eventCount / 6) * 100));
    return {
      percent,
      tone,
      label: `${eventCount} zdarzeń`,
      steps: statusSteps,
      fallback: true,
      title: buildTitleFromSteps(statusSteps),
    };
  }

  const stepStatuses = steps.map((step) => step.status);
  const doneCount = steps.filter((step) => step.status === 'done' || step.status === 'skipped').length;
  const percent = progressPercent(steps, groupStatusKey);
  const tone = normalizeProgressTone(stepStatuses, groupStatusKey);

  return {
    percent,
    tone,
    label: `${doneCount}/${steps.length} etapów`,
    steps,
    fallback: false,
    title: buildTitleFromSteps(steps),
  };
}

/** Statusy worker pipeline — tylko te oznaczają aktywną transmisję sprzedaży. */
const ACTIVE_TRANSMISSION_STATUSES = new Set([
  'queued',
  'processing',
  'submitted',
  'waiting_status',
]);

const FAILURE_STATUSES = new Set([
  'failed_permanent',
  'failed',
  'refresh_failed',
]);

const SUCCESS_STATUS_VALUES = new Set([
  'success',
  'ok',
  'renewed',
  'refreshed',
  'authenticated',
  'enqueued',
  'downloaded',
  'summary',
]);

const STALE_RUNNING_STATUSES = new Set(['started', 'slot_due']);
const WARNING_STATUS_VALUES = new Set([
  'waiting_status',
  'failed_retryable',
  'failed_temporary',
  'retry',
  'retrying',
  'incomplete',
]);
const INFO_STATUS_VALUES = new Set([
  'submitted',
  'enqueued',
  'queued',
  'processing',
  'ok',
  'summary',
  'refreshed',
  'renewed',
  'authenticated',
  'downloaded',
  'skipped',
  'started',
  'slot_due',
]);

function rowSeverity(row) {
  return String(row.severity || '').toUpperCase();
}

function rowStatus(row) {
  return String(row.status || '').toLowerCase();
}

function isRowFailure(row) {
  const status = rowStatus(row);
  const sev = rowSeverity(row);
  if (sev === 'ERROR' || FAILURE_STATUSES.has(status)) return true;
  return false;
}

function isRowWarning(row) {
  const status = rowStatus(row);
  const sev = rowSeverity(row);
  if (sev === 'WARNING') return true;
  if (status === 'failed_retryable' || status === 'failed_temporary' || status === 'incomplete') {
    return true;
  }
  return false;
}

function isRowSuccess(row) {
  const status = rowStatus(row);
  const sev = rowSeverity(row);
  if (status === 'success' || sev === 'SUCCESS') return true;
  if (SUCCESS_STATUS_VALUES.has(status)) return true;
  return false;
}

function isRowActivelyRunning(row, groupHasSuccess) {
  const status = rowStatus(row);
  const sev = rowSeverity(row);
  if (ACTIVE_TRANSMISSION_STATUSES.has(status)) return true;
  if (sev === 'RUNNING' && STALE_RUNNING_STATUSES.has(status) && groupHasSuccess) {
    return false;
  }
  if (sev === 'RUNNING') return true;
  return false;
}

/**
 * Agregacja statusu procesu.
 * Uwzględnia journal KSeF (statusy ok/summary/skipped) oraz worker pipeline.
 */
export function aggregateGroupStatus(rows) {
  if (!rows.length) return { key: 'neutral', label: 'INFO' };

  if (rows.some(isRowFailure)) {
    return { key: 'error', label: 'BŁĄD' };
  }
  if (rows.some(isRowWarning)) {
    return { key: 'warning', label: 'OSTRZEŻENIE' };
  }

  const hasSuccess = rows.some(isRowSuccess);
  const sorted = [...rows].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );
  const latest = sorted[0];
  const activelyRunning = rows.some((r) => isRowActivelyRunning(r, hasSuccess))
    || isRowActivelyRunning(latest, hasSuccess);

  if (activelyRunning) {
    return { key: 'running', label: 'W TOKU' };
  }
  if (hasSuccess) {
    return { key: 'success', label: 'SUKCES' };
  }
  if (rows.every((r) => rowSeverity(r) === 'INFO' || rowStatus(r) === 'skipped')) {
    return { key: 'neutral', label: 'INFO' };
  }
  return { key: 'success', label: 'SUKCES' };
}

export function formatGroupStatusDisplay(status) {
  const map = {
    success: '✔ Sukces',
    error: '✖ Błąd',
    warning: '⚠ Ostrzeżenie',
    running: '◌ W toku',
    neutral: 'ℹ Info',
  };
  return map[status?.key] || status?.label || '—';
}

/**
 * Wspólny helper UX: mapowanie statusu/severity na ton koloru.
 * Używany konsekwentnie dla ikon, badge i akcentów grup.
 */
export function mapStatusKeyToTone(key) {
  const k = String(key || '').toLowerCase();
  if (!k) return 'neutral';
  if (k === 'warning' || WARNING_STATUS_VALUES.has(k)) return 'warning';
  if (k === 'error' || FAILURE_STATUSES.has(k) || k === 'failed_permanent' || k === 'failed') return 'error';
  if (k === 'success') return 'success';
  if (k === 'info' || k === 'running' || INFO_STATUS_VALUES.has(k)) return 'info';
  if (k === 'neutral') return 'neutral';
  return 'neutral';
}

export function deriveRowStatusTone(row) {
  const severity = String(row?.severity || '').toLowerCase();
  const status = String(row?.status || '').toLowerCase();
  const toneFromStatus = mapStatusKeyToTone(status);
  const toneFromSeverity = mapStatusKeyToTone(severity);

  if (toneFromStatus === 'error' || toneFromSeverity === 'error') return 'error';
  if (toneFromStatus === 'warning' || toneFromSeverity === 'warning') return 'warning';
  if (toneFromStatus === 'success' || toneFromSeverity === 'success') return 'success';
  if (toneFromStatus === 'info' || toneFromSeverity === 'info') return 'info';
  return 'neutral';
}

/** Subtelna ikona typu procesu (nie zastępuje kolumny statusu). */
export function deriveProcessIcon(title, status) {
  const t = String(title || '').toLowerCase();
  if (t.includes('zakup')) return '📥';
  if (t.includes('sprzedaż')) return '📤';
  if (t.includes('sesja')) return '🔐';
  if (t.includes('harmonogram')) return '⏰';
  if (status?.key === 'error') return '❌';
  if (status?.key === 'warning') return '⚠';
  return '•';
}

export const TOOLTIP_EMPTY_MESSAGE = 'Brak szczegółów faktury dla tego wpisu dziennika.';

export function invoiceHasTooltipDetails(invoice) {
  if (!invoice) return false;
  if (invoice.hasDetails === false) return false;
  const hasNumber = invoice.number && invoice.number !== '—';
  const hasParty = invoice.counterparty && invoice.counterparty !== '—';
  return Boolean(hasNumber && (hasParty || invoice.nip || invoice.amount || invoice.ksefRef));
}

function pickMarkerValue(row) {
  if (!row || typeof row !== 'object') return null;
  const meta = row.metadata_json && typeof row.metadata_json === 'object' ? row.metadata_json : {};
  const candidates = [
    row.marker,
    row.transmission_marker,
    row.batch_marker,
    meta.marker,
    meta.transmission_marker,
    meta.batch_marker,
  ];
  for (const value of candidates) {
    if (value != null && String(value).trim() !== '') return String(value).trim();
  }
  return null;
}

export function deriveProcessKey(row) {
  if (!row || typeof row !== 'object') return 'row:unknown';

  const jobId = row.job_id;
  if (jobId != null && String(jobId).trim() !== '') {
    return `job:${String(jobId).trim()}`;
  }

  const correlationId = row.correlation_id;
  if (correlationId != null && String(correlationId).trim() !== '') {
    return `corr:${String(correlationId).trim()}`;
  }

  const marker = pickMarkerValue(row);
  if (marker) return `marker:${marker}`;

  const transmissionId = row.transmission_id ?? row.id;
  if (transmissionId != null && String(transmissionId).trim() !== '') {
    return `tx:${String(transmissionId).trim()}`;
  }

  return `row:${row.id ?? 'unknown'}`;
}

export function groupTransmissions(rows) {
  const map = new Map();
  for (const row of rows) {
    const key = deriveProcessKey(row);
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(row);
  }

  const groups = Array.from(map.entries()).map(([key, items]) => {
    const sorted = [...items].sort(
      (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    );
    const createdAt = sorted[0]?.created_at;
    return {
      key,
      rows: sorted,
      marker: formatTransmissionMarker(createdAt),
      datetime: formatOperatorDateTimeDisplay(createdAt),
      dateTimeParts: formatOperatorDateTime(createdAt),
      title: deriveProcessTitle(sorted),
      status: aggregateGroupStatus(sorted),
    };
  });

  return groups.sort(
    (a, b) => new Date(b.rows[0]?.created_at).getTime() - new Date(a.rows[0]?.created_at).getTime(),
  );
}

function formatAmount(value, currency) {
  if (value == null || value === '') return null;
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  const formatted = num.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return currency ? `${formatted} ${currency}` : formatted;
}

export function buildInvoiceSnapshot(row) {
  const snap = row.invoice_snapshot && typeof row.invoice_snapshot === 'object'
    ? row.invoice_snapshot
    : null;
  const meta = row.metadata_json && typeof row.metadata_json === 'object' ? row.metadata_json : {};
  const purchase = snap?.direction === 'purchase' || isPurchaseOperation(row.operation_type);

  if (snap) {
    return {
      id: row.invoice_id,
      number: snap.number || row.invoice_number_local || '—',
      counterparty: snap.counterparty_name || '—',
      nip: snap.counterparty_nip || null,
      amount: formatAmount(snap.gross_total, snap.currency),
      date: snap.issue_date || row.finished_at || row.created_at,
      status: snap.status || row.status,
      ksefRef: snap.ksef_reference_number || row.ksef_reference_number,
      direction: snap.direction || (purchase ? 'purchase' : 'sale'),
      hasDetails: true,
      hasSnapshot: true,
    };
  }

  const hasInvoiceLink = Boolean(row.invoice_id);
  const counterparty = meta.counterparty || meta.seller_name || meta.buyer_name || meta.description || '—';
  const hasRichMeta = Boolean(
    meta.nip || meta.seller_nip || meta.buyer_nip || meta.amount || meta.gross_total,
  );

  return {
    id: row.invoice_id,
    number: row.invoice_number_local || '—',
    counterparty,
    nip: meta.nip || meta.seller_nip || meta.buyer_nip || null,
    amount: formatAmount(meta.amount || meta.gross_total, meta.currency),
    date: row.finished_at || row.created_at,
    status: row.status,
    ksefRef: row.ksef_reference_number,
    direction: purchase ? 'purchase' : 'sale',
    hasDetails: hasInvoiceLink && hasRichMeta && counterparty !== '—',
    hasSnapshot: false,
  };
}

export function extractInvoicesFromRows(rows) {
  const invoices = new Map();
  for (const row of rows) {
    const number = row.invoice_number_local;
    const id = row.invoice_id;
    if (!number && !id) continue;
    const key = id || number;
    const existing = invoices.get(key);
    const candidate = buildInvoiceSnapshot(row);
    if (!existing) {
      invoices.set(key, candidate);
      continue;
    }
    invoices.set(key, {
      ...existing,
      counterparty: candidate.counterparty !== '—' ? candidate.counterparty : existing.counterparty,
      nip: candidate.nip || existing.nip,
      amount: candidate.amount || existing.amount,
      ksefRef: candidate.ksefRef || existing.ksefRef,
      status: candidate.status || existing.status,
      hasDetails: existing.hasDetails || candidate.hasDetails,
      hasSnapshot: existing.hasSnapshot || candidate.hasSnapshot,
    });
  }
  return Array.from(invoices.values());
}

export function summarizeGroup(rows) {
  const invoices = extractInvoicesFromRows(rows);
  const warningCount = rows.filter((r) => rowSeverity(r) === 'WARNING').length;
  const errorCount = rows.filter((r) => isRowFailure(r)).length;

  const started = rows.map((r) => r.started_at || r.created_at).filter(Boolean);
  const finished = rows.map((r) => r.finished_at).filter(Boolean);
  let durationSec = null;
  if (started.length && finished.length) {
    const ms = new Date(finished[finished.length - 1]).getTime() - new Date(started[0]).getTime();
    if (ms >= 0) durationSec = Math.round(ms / 1000);
  }
  if (durationSec == null && started.length >= 2) {
    const ms = new Date(started[started.length - 1]).getTime() - new Date(started[0]).getTime();
    if (ms >= 0) durationSec = Math.round(ms / 1000);
  }

  const purchaseSaved = rows.reduce((max, r) => {
    const saved = Number(r.metadata_json?.saved);
    return Number.isFinite(saved) ? Math.max(max, saved) : max;
  }, 0);

  const metaSaved = rows.reduce((sum, r) => sum + (Number(r.metadata_json?.saved) || 0), 0);
  const invoiceCount = invoices.length || purchaseSaved || metaSaved || 0;

  const saleRef = rows.find((r) => r.ksef_reference_number)?.ksef_reference_number;
  const upoOk = rows.some((r) => r.upo_status === 'fetched');
  const isPurchase = groupHasAny(rows, PURCHASE_OPS);

  return {
    stageCount: rows.length,
    invoiceCount,
    purchaseSaved,
    invoices,
    warningCount,
    errorCount,
    durationSec,
    saleRef,
    upoOk,
    isPurchase,
    hasRetryable: rows.some((r) => rowStatus(r) === 'failed_retryable'),
    retryRow: rows.find((r) => rowStatus(r) === 'failed_retryable') || null,
  };
}

export function buildProcessSummaryMeta(summary, title) {
  const parts = [];

  if (summary.isPurchase && summary.purchaseSaved > 0) {
    parts.push(`${summary.purchaseSaved} nowych faktur`);
  } else if (summary.invoices[0]?.number && summary.invoices[0].number !== '—') {
    parts.push(summary.invoices[0].number);
  } else if (summary.invoiceCount > 0) {
    parts.push(`${summary.invoiceCount} faktur`);
  }

  if (summary.upoOk) parts.push('UPO odebrane');
  if (summary.durationSec != null) parts.push(`czas ${summary.durationSec} s`);
  parts.push(`${summary.stageCount} etap${summary.stageCount === 1 ? '' : summary.stageCount < 5 ? 'y' : 'ów'}`);

  return parts.join(' · ');
}

/** Podsumowanie rozwinięte: efekt procesu przed metadanymi technicznymi. */
export function buildSummaryLines(summary, status, title) {
  const effects = [];

  if (summary.isPurchase && summary.purchaseSaved > 0) {
    const noun = summary.purchaseSaved === 1 ? 'nowa faktura' : 'nowych faktur';
    effects.push(`${summary.purchaseSaved} ${noun}`);
  } else if (title.includes('sprzedaż') && summary.invoices[0]?.number) {
    effects.push(summary.invoices[0].number);
  } else if (summary.invoiceCount > 0) {
    const noun = summary.invoiceCount === 1 ? 'faktura' : 'faktur';
    effects.push(`${summary.invoiceCount} ${noun}`);
  }

  if (summary.upoOk) effects.push('UPO odebrane');
  if (summary.saleRef && !summary.upoOk) effects.push('Numer KSeF nadany');

  const meta = [];
  if (summary.durationSec != null) meta.push(`czas ${summary.durationSec} s`);
  meta.push(`${summary.stageCount} etap${summary.stageCount === 1 ? '' : summary.stageCount < 5 ? 'y' : 'ów'}`);
  if (summary.warningCount) {
    meta.push(`${summary.warningCount} ostrzeżenie${summary.warningCount === 1 ? '' : summary.warningCount < 5 ? 'a' : 'ń'}`);
  }

  return {
    status: formatGroupStatusDisplay(status),
    effects,
    meta,
  };
}

export function invoicesSummaryLabel(summary) {
  const count = summary.invoiceCount;
  if (!count) return '—';
  if (summary.isPurchase && summary.purchaseSaved > 0) {
    return summary.purchaseSaved === 1 ? '1 nowa' : `${summary.purchaseSaved} nowych`;
  }
  if (count === 1 && summary.invoices[0]?.number) {
    const invoice = summary.invoices[0];
    if (invoice.hasSnapshot && invoice.counterparty && invoice.counterparty !== '—') {
      return `${invoice.number} · ${invoice.counterparty}`;
    }
    return invoice.number;
  }
  return `${count} faktur`;
}
