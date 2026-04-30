import { invoicesApi } from '../../api/invoices';

export function currentMonthPrefix() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  return `${y}-${m}`;
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

export function resolveEffectiveFilters(filters = {}) {
  const periodPrefix = filters?.month || currentMonthPrefix();
  const month = monthRange(periodPrefix);

  const issueDateFrom = filters?.issue_date_from || '';
  const issueDateTo = filters?.issue_date_to || '';
  const contractorFilter = normalizeContractorFilter(filters?.contractor);
  const status = filters?.status || '';

  const dateRangeActive = !!(issueDateFrom || issueDateTo);
  const useImplicitMonthRange = !dateRangeActive && !contractorFilter;

  return {
    from: useImplicitMonthRange ? month.from : issueDateFrom,
    to: useImplicitMonthRange ? month.to : issueDateTo,
    monthPrefix: periodPrefix,
    status,
    contractorFilter,
  };
}

export function buildInvoiceParams(filters = {}, direction) {
  const resolved = resolveEffectiveFilters(filters);

  return {
    direction,
    ...(resolved.from && { issue_date_from: resolved.from }),
    ...(resolved.to && { issue_date_to: resolved.to }),
    ...(resolved.status && { status: resolved.status }),
    ...(resolved.contractorFilter && { number_filter: resolved.contractorFilter }),
  };
}

export async function fetchAllInvoices(baseParams) {
  let page = 1;
  const size = 100;
  let total = 0;
  const items = [];

  do {
    const res = await invoicesApi.list({ ...baseParams, page, size });
    total = Number(res?.total || 0);
    items.push(...(res?.items || []));
    page += 1;
  } while (items.length < total);

  return items;
}
