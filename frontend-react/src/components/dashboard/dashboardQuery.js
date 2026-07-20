export function currentMonthPrefix() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  return `${y}-${m}`;
}

/**
 * Zakres YTD bieżącego roku kalendarzowego systemu:
 * od 1 stycznia aktualnego roku do dnia bieżącego (włącznie).
 * Rok NIE jest hardcodowany — zależy od `now`.
 */
export function currentYearToDateRange(now = new Date()) {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return {
    from: `${y}-01-01`,
    to: `${y}-${m}-${d}`,
  };
}

function monthRange(prefix) {
  const [y, m] = String(prefix || currentMonthPrefix()).split('-').map(Number);
  const lastDay = new Date(y, m, 0).getDate();
  const month = String(m).padStart(2, '0');
  return {
    from: `${y}-${month}-01`,
    to: `${y}-${month}-${String(lastDay).padStart(2, '0')}`,
  };
}

function normalizeContractorFilter(raw) {
  const contractor = String(raw || '').trim();
  return contractor.length >= 3 ? contractor : '';
}

function toIsoDate(value) {
  const text = String(value || '').trim();
  return /^\d{4}-\d{2}-\d{2}$/.test(text) ? text : '';
}

function toMonthPrefix(value) {
  const text = String(value || '').trim();
  return /^\d{4}-\d{2}$/.test(text) ? text : '';
}

function invoiceIssueDate(invoice) {
  return String(invoice?.issue_date || '').slice(0, 10);
}

export function resolveEffectiveFilters(filters = {}, options = {}) {
  const {
    defaultToCurrentMonth = true,
  } = options;

  const monthPrefix = toMonthPrefix(filters?.month);
  const explicitFrom = toIsoDate(filters?.issue_date_from);
  const explicitTo = toIsoDate(filters?.issue_date_to);
  const explicitBefore = toIsoDate(filters?.issue_date_before);
  const contractorFilter = normalizeContractorFilter(filters?.contractor);
  const status = String(filters?.status || '').trim();

  let from = explicitFrom;
  let to = explicitTo;

  if (!from && !to && monthPrefix) {
    const month = monthRange(monthPrefix);
    from = month.from;
    to = month.to;
  }

  if (!from && !to && !explicitBefore && defaultToCurrentMonth) {
    const currentMonth = monthRange(currentMonthPrefix());
    from = currentMonth.from;
    to = currentMonth.to;
  }

  return {
    from,
    to,
    before: explicitBefore,
    monthPrefix: monthPrefix || currentMonthPrefix(),
    status,
    contractorFilter,
  };
}

export function buildInvoicePoolQuery(filters = {}, direction, options = {}) {
  const resolved = resolveEffectiveFilters(filters, options);
  return {
    direction,
    ...(resolved.from && { issue_date_from: resolved.from }),
    ...(resolved.to && { issue_date_to: resolved.to }),
    ...(resolved.before && { issue_date_before: resolved.before }),
    ...(resolved.status && { status: resolved.status }),
    ...(resolved.contractorFilter && { number_filter: resolved.contractorFilter }),
  };
}

export function buildInvoicePoolKey(query = {}) {
  const normalized = Object.entries(query)
    .filter(([, value]) => value !== undefined && value !== null && String(value) !== '')
    .sort(([a], [b]) => a.localeCompare(b));
  return JSON.stringify(normalized);
}

export function filterInvoicesFromPool(invoices = [], filters = {}, options = {}) {
  const resolved = resolveEffectiveFilters(filters, options);
  const from = resolved.from;
  const to = resolved.to;
  const before = resolved.before;
  const status = resolved.status;

  return invoices.filter((invoice) => {
    const issueDate = invoiceIssueDate(invoice);
    if (!issueDate) return false;
    if (from && issueDate < from) return false;
    if (to && issueDate > to) return false;
    if (before && issueDate >= before) return false;
    if (status && String(invoice?.status || '') !== status) return false;
    return true;
  });
}
