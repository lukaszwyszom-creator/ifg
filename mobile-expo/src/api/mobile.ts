import { apiClient } from './client';
import { ensureApiAuth, AuthError } from './auth';
import { API_V1_PREFIX, getApiBaseUrl } from './config';

export type RecentPurchaseInvoice = {
  id: string;
  supplier_name: string;
  number: string;
  amount_gross: string;
  issue_date: string;
};

export type DashboardResponse = {
  period: string;
  sales_net: string;
  purchase_net: string;
  vat_balance: string;
  vat_label: 'due' | 'refund';
  debtors_count: number;
  debtors_total_due: string;
  debtors_overdue_due: string;
  creditors_count: number;
  creditors_total_due: string;
  creditors_overdue_due: string;
  unassigned_payments_count: number;
  unassigned_payments_total: string;
  ksef_new_invoices_count: number;
  ksef_last_sync_at: string | null;
  ksef_connection_status: 'connected' | 'disconnected' | 'error';
  notifications_active_count: number;
  recent_purchase_invoices: RecentPurchaseInvoice[];
};

export async function fetchDashboard(period: string): Promise<DashboardResponse> {
  ensureApiAuth();
  return apiClient.get<DashboardResponse>(`/mobile/dashboard?period=${encodeURIComponent(period)}`);
}

export type SettlementInvoiceItem = {
  invoice_id: string;
  number: string;
  issue_date: string;
  due_date: string | null;
  amount_due: string;
  overdue_days: number | null;
};

export type CounterpartyListItem = {
  id: string;
  name: string;
  total_due: string;
  overdue_due: string;
  invoices_count: number;
  overdue_invoices_count: number;
  last_invoice_due_date: string | null;
};

export type CounterpartyDetail = CounterpartyListItem & {
  invoices: SettlementInvoiceItem[];
};

type CounterpartiesListResponse = {
  items: CounterpartyListItem[];
};

export async function fetchDebtors(): Promise<CounterpartyListItem[]> {
  ensureApiAuth();
  const res = await apiClient.get<CounterpartiesListResponse>('/mobile/debtors');
  return res.items;
}

export async function fetchDebtor(id: string): Promise<CounterpartyDetail> {
  ensureApiAuth();
  return apiClient.get<CounterpartyDetail>(`/mobile/debtors/${encodeURIComponent(id)}`);
}

export async function fetchCreditors(): Promise<CounterpartyListItem[]> {
  ensureApiAuth();
  const res = await apiClient.get<CounterpartiesListResponse>('/mobile/creditors');
  return res.items;
}

export async function fetchCreditor(id: string): Promise<CounterpartyDetail> {
  ensureApiAuth();
  return apiClient.get<CounterpartyDetail>(`/mobile/creditors/${encodeURIComponent(id)}`);
}

export type InvoiceItemResponse = {
  id: string | null;
  name: string;
  quantity: string;
  unit: string;
  unit_price_net?: string | null;
  vat_rate?: string | null;
  /** API standard (InvoiceItemResponse backend). */
  net_total?: string | null;
  vat_total?: string | null;
  gross_total?: string | null;
  /** Aliasy zgodne z kolumnami DB / starszymi odpowiedziami API. */
  net_amount?: string | null;
  vat_amount?: string | null;
  gross_amount?: string | null;
  sort_order?: number;
  isbn?: string | null;
};

export type InvoiceItemDisplay = {
  lineNumber: number;
  name: string;
  quantityLabel: string;
  netLabel: string;
  vatRateLabel: string;
  vatLabel: string;
};

function parseOptionalAmount(raw: string | null | undefined): number | null {
  if (raw == null) {
    return null;
  }
  const trimmed = String(raw).trim();
  if (!trimmed) {
    return null;
  }
  const n = parseFloat(trimmed);
  return Number.isNaN(n) ? null : n;
}

function positiveAmount(raw: string | null | undefined): number | null {
  const n = parseOptionalAmount(raw);
  return n != null && n > 0 ? n : null;
}

const NET_FIELD_KEYS = ['net_total', 'net_amount'] as const;
const VAT_FIELD_KEYS = ['vat_total', 'vat_amount'] as const;
const GROSS_FIELD_KEYS = ['gross_total', 'gross_amount'] as const;

function pickRawField(item: InvoiceItemResponse, keys: readonly string[]): string | undefined {
  const row = item as Record<string, unknown>;
  for (const key of keys) {
    const value = row[key];
    if (value == null) {
      continue;
    }
    const trimmed = String(value).trim();
    if (trimmed) {
      return trimmed;
    }
  }
  return undefined;
}

function pickPositiveField(item: InvoiceItemResponse, keys: readonly string[]): number | null {
  return positiveAmount(pickRawField(item, keys));
}

function pickAmountField(item: InvoiceItemResponse, keys: readonly string[]): number | null {
  return parseOptionalAmount(pickRawField(item, keys));
}

export function formatAmountOrDash(value: number | null): string {
  if (value == null) {
    return '—';
  }
  return `${value.toLocaleString('pl-PL', { minimumFractionDigits: 0, maximumFractionDigits: 2 })} zł`;
}

export function formatVatRateOrDash(value: number | null): string {
  if (value == null) {
    return '—';
  }
  const normalized =
    Math.abs(value - Math.round(value)) < 0.001
      ? String(Math.round(value))
      : value.toFixed(2).replace(/\.?0+$/, '');
  return `${normalized}%`;
}

export function resolveInvoiceItemFields(item: InvoiceItemResponse): {
  net: number | null;
  vat: number | null;
  vatRate: number | null;
} {
  const qty = parseOptionalAmount(item.quantity) ?? 1;
  const unitPrice = positiveAmount(item.unit_price_net);
  let net = pickPositiveField(item, NET_FIELD_KEYS);
  let vat = pickAmountField(item, VAT_FIELD_KEYS);
  const gross = pickPositiveField(item, GROSS_FIELD_KEYS);
  const rateRaw = parseOptionalAmount(item.vat_rate);
  let vatRate = rateRaw != null && rateRaw >= 0 ? rateRaw : null;

  if (net == null && unitPrice != null) {
    net = parseFloat((qty * unitPrice).toFixed(2));
  }

  if (net == null && gross != null && vatRate != null && vatRate > 0) {
    net = parseFloat((gross / (1 + vatRate / 100)).toFixed(2));
  }

  if (net == null && gross != null && vat != null && vat > 0 && gross >= vat) {
    net = parseFloat((gross - vat).toFixed(2));
  }

  if (net == null && gross != null && vatRate === 0) {
    net = gross;
    if (vat == null) {
      vat = 0;
    }
  }

  if (vat == null && net != null && net > 0 && vatRate != null) {
    vat = parseFloat((net * vatRate / 100).toFixed(2));
  }

  if (vat == null && net != null && gross != null && gross > net) {
    vat = parseFloat((gross - net).toFixed(2));
  }

  if (vatRate == null && net != null && net > 0 && vat != null && vat >= 0) {
    vatRate = parseFloat(((vat / net) * 100).toFixed(2));
  }

  if (net != null && net <= 0) {
    net = null;
  }
  if (vat != null && vat < 0) {
    vat = null;
  }

  return { net, vat, vatRate };
}

export function mapInvoiceItemForDisplay(item: InvoiceItemResponse, index: number): InvoiceItemDisplay {
  const { net, vat, vatRate } = resolveInvoiceItemFields(item);
  const qty = parseOptionalAmount(item.quantity);
  const unit = item.unit?.trim() || 'szt.';
  const quantityLabel =
    qty != null ? `${qty.toLocaleString('pl-PL', { maximumFractionDigits: 4 })} ${unit}` : '—';

  return {
    lineNumber: item.sort_order != null && item.sort_order > 0 ? item.sort_order : index + 1,
    name: item.name?.trim() || 'Pozycja',
    quantityLabel,
    netLabel: formatAmountOrDash(net),
    vatRateLabel: formatVatRateOrDash(vatRate),
    vatLabel: vat != null ? formatAmountOrDash(vat) : '—',
  };
}

export type InvoiceResponse = {
  id: string;
  number_local: string | null;
  issue_date: string;
  due_date: string | null;
  ksef_reference_number: string | null;
  direction: 'sale' | 'purchase';
  seller_snapshot: Record<string, unknown>;
  buyer_snapshot: Record<string, unknown>;
  items: InvoiceItemResponse[];
  total_gross: string;
  payment_status: string;
  remaining_amount: string | null;
  paid_amount: string | null;
};

export async function fetchInvoice(id: string): Promise<InvoiceResponse> {
  ensureApiAuth();
  return apiClient.get<InvoiceResponse>(`/invoices/${encodeURIComponent(id)}`);
}

export type UnassignedPayment = {
  id: string;
  transaction_date: string;
  amount: string;
  remaining_amount: string;
  counterparty_name: string | null;
  counterparty_account: string | null;
  title: string | null;
  match_status: string;
};

type UnassignedPaymentsResponse = {
  items: UnassignedPayment[];
  total: number;
  page: number;
  size: number;
};

export async function fetchUnassignedPayments(params?: {
  page?: number;
  size?: number;
}): Promise<UnassignedPaymentsResponse> {
  ensureApiAuth();
  const page = params?.page ?? 1;
  const size = params?.size ?? 200;
  const qs = new URLSearchParams({
    match_status: 'unmatched',
    page: String(page),
    size: String(size),
  });
  return apiClient.get<UnassignedPaymentsResponse>(`/payments/transactions?${qs.toString()}`);
}

async function fetchTransactionsByStatus(
  matchStatus: string,
  size = 200,
): Promise<UnassignedPayment[]> {
  ensureApiAuth();
  const qs = new URLSearchParams({
    match_status: matchStatus,
    page: '1',
    size: String(size),
  });
  const res = await apiClient.get<UnassignedPaymentsResponse>(
    `/payments/transactions?${qs.toString()}`,
  );
  return res.items;
}

export async function fetchPaymentsForAssignment(): Promise<{
  items: UnassignedPayment[];
  total: number;
}> {
  const [unmatchedRes, partial, manualReview] = await Promise.all([
    fetchUnassignedPayments({ size: 200 }),
    fetchTransactionsByStatus('partial'),
    fetchTransactionsByStatus('manual_review'),
  ]);
  const merged = new Map<string, UnassignedPayment>();
  for (const payment of [...unmatchedRes.items, ...partial, ...manualReview]) {
    merged.set(payment.id, payment);
  }
  const items = Array.from(merged.values());
  return { items, total: items.length };
}

export type PaymentAllocation = {
  id: string;
  transaction_id: string;
  invoice_id: string;
  allocated_amount: string;
  is_reversed: boolean;
};

export async function allocatePayment(
  transactionId: string,
  invoiceId: string,
  amount: string,
): Promise<PaymentAllocation> {
  ensureApiAuth();
  return apiClient.post<PaymentAllocation>(
    `/payments/transactions/${encodeURIComponent(transactionId)}/allocate`,
    { invoice_id: invoiceId, amount },
  );
}

export async function fetchInvoicePaymentHistory(
  invoiceId: string,
): Promise<PaymentAllocation[]> {
  ensureApiAuth();
  return apiClient.get<PaymentAllocation[]>(
    `/payments/invoice/${encodeURIComponent(invoiceId)}/history`,
  );
}

async function apiDelete(path: string): Promise<void> {
  ensureApiAuth();
  const token = apiClient.getToken();
  const normalized = path.startsWith('/') ? path : `/${path}`;
  const url = `${getApiBaseUrl()}${API_V1_PREFIX}${normalized}`;
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(url, { method: 'DELETE', headers });
  if (response.status === 401) {
    throw new AuthError('Brak uwierzytelnienia');
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message =
      (payload as { error?: { message?: string }; detail?: string })?.error?.message ??
      (payload as { detail?: string })?.detail ??
      `HTTP ${response.status}`;
    throw new Error(typeof message === 'string' ? message : `HTTP ${response.status}`);
  }
}

export async function reversePaymentAllocation(allocationId: string): Promise<void> {
  await apiDelete(`/payments/allocations/${encodeURIComponent(allocationId)}`);
}

export type SettlementItem = {
  invoice_id: string;
  number_local: string | null;
  ksef_reference_number: string | null;
  contractor_name: string | null;
  currency: string;
  issue_date: string;
  due_date: string | null;
  gross_total: string;
  paid_amount: string;
  remaining_amount: string;
  payment_status: string;
  side: string;
};

export type SettlementsResponse = {
  debtors: SettlementItem[];
  creditors: SettlementItem[];
};

export async function fetchSettlements(): Promise<SettlementsResponse> {
  ensureApiAuth();
  return apiClient.get<SettlementsResponse>('/payments/settlements?side=all');
}

export function settlementDisplayNumber(
  item: Pick<SettlementItem, 'number_local' | 'ksef_reference_number'>,
): string {
  return item.number_local?.trim() || item.ksef_reference_number?.trim() || 'Brak numeru';
}

export function settlementContractorName(item: SettlementItem): string {
  const name = item.contractor_name?.trim();
  return name || 'Nieznany kontrahent';
}

export function unassignedPaymentDisplayAmount(payment: UnassignedPayment): string {
  const remaining = parseAmount(payment.remaining_amount);
  if (remaining > 0) {
    return payment.remaining_amount;
  }
  return payment.amount;
}

export function unassignedPaymentCounterparty(payment: UnassignedPayment): string {
  const name = payment.counterparty_name?.trim();
  return name || 'Nieznany kontrahent';
}

export type InvoiceListItem = {
  id: string;
  number_local: string | null;
  ksef_reference_number: string | null;
  direction: 'sale' | 'purchase';
  issue_date: string;
  due_date: string | null;
  total_gross: string;
  payment_status: string;
  remaining_amount: string | null;
  seller_snapshot: Record<string, unknown>;
  buyer_snapshot: Record<string, unknown>;
  overdue_days: number | null;
};

type InvoiceListResponse = {
  items: InvoiceListItem[];
  total: number;
  page: number;
  size: number;
};

const MONTH_PARAM_PATTERN = /^\d{4}-\d{2}$/;

export function parseMonthParam(value: string | string[] | undefined): string | undefined {
  const raw = Array.isArray(value) ? value[0] : value;
  if (!raw || !MONTH_PARAM_PATTERN.test(raw)) {
    return undefined;
  }
  const month = Number(raw.split('-')[1]);
  if (month < 1 || month > 12) {
    return undefined;
  }
  return raw;
}

export async function fetchInvoices(params: {
  direction: 'sale' | 'purchase';
  page?: number;
  size?: number;
  month?: string;
  number_filter?: string;
}): Promise<InvoiceListResponse> {
  ensureApiAuth();
  const page = params.page ?? 1;
  const size = params.size ?? 100;
  const qs = new URLSearchParams({
    direction: params.direction,
    page: String(page),
    size: String(size),
  });
  const month = params.month ? parseMonthParam(params.month) : undefined;
  if (month) {
    qs.set('month', month);
  }
  const numberFilter = params.number_filter?.trim();
  if (numberFilter) {
    qs.set('number_filter', numberFilter);
  }
  return apiClient.get<InvoiceListResponse>(`/invoices/?${qs.toString()}`);
}

export type RecentKsefPurchaseRow = {
  id: string;
  supplier_name: string;
  number: string;
  amount_gross: string;
  issue_date: string;
};

export async function fetchRecentKsefPurchaseInvoices(limit = 5): Promise<RecentKsefPurchaseRow[]> {
  const res = await fetchInvoices({ direction: 'purchase', size: 50 });
  return res.items
    .filter((inv) => Boolean(inv.ksef_reference_number?.trim()))
    .sort((a, b) => b.issue_date.localeCompare(a.issue_date))
    .slice(0, limit)
    .map((inv) => ({
      id: inv.id,
      supplier_name: contractorNameFromListItem(inv),
      number: invoiceDisplayNumber(inv),
      amount_gross: inv.total_gross,
      issue_date: inv.issue_date,
    }));
}

export async function searchInvoices(query: string): Promise<InvoiceListItem[]> {
  const q = query.trim();
  if (q.length < 2) {
    return [];
  }
  const [sales, purchases] = await Promise.all([
    fetchInvoices({ direction: 'sale', size: 20, number_filter: q }),
    fetchInvoices({ direction: 'purchase', size: 20, number_filter: q }),
  ]);
  return [...sales.items, ...purchases.items];
}

export function invoiceDisplayNumber(
  inv: Pick<InvoiceListItem, 'number_local' | 'ksef_reference_number'>,
): string {
  return inv.number_local?.trim() || inv.ksef_reference_number?.trim() || 'Brak numeru';
}

export function invoiceListDisplayAmount(
  inv: Pick<InvoiceListItem, 'total_gross' | 'remaining_amount'>,
): string {
  if (inv.remaining_amount != null) {
    return inv.remaining_amount;
  }
  return inv.total_gross;
}

export function contractorNameFromListItem(inv: InvoiceListItem): string {
  const snapshot = inv.direction === 'purchase' ? inv.seller_snapshot : inv.buyer_snapshot;
  const name = snapshot.name;
  return typeof name === 'string' && name.trim() ? name.trim() : 'Nieznany kontrahent';
}

export function normalizePaymentStatus(status: string | undefined): 'paid' | 'partial' | 'unpaid' {
  const normalized = status?.toLowerCase();
  if (normalized === 'paid' || normalized === 'unpaid') {
    return normalized;
  }
  if (normalized === 'partial' || normalized === 'partially_paid') {
    return 'partial';
  }
  return 'unpaid';
}

export function dueLabel(dueDate: string | null | undefined): string {
  if (!dueDate) {
    return 'brak terminu';
  }
  const due = new Date(dueDate.slice(0, 10));
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  due.setHours(0, 0, 0, 0);
  const diff = Math.round((due.getTime() - today.getTime()) / 86400000);
  if (diff > 0) return `za ${diff} dni`;
  if (diff < 0) return `${Math.abs(diff)} dni po terminie`;
  return 'termin dziś';
}

export function parseAmount(value: string): number {
  const n = parseFloat(value);
  return Number.isNaN(n) ? 0 : n;
}

export function ksefStatusLabel(status: DashboardResponse['ksef_connection_status']): string {
  if (status === 'connected') return 'KSeF OK';
  if (status === 'error') return 'KSeF błąd';
  return 'KSeF offline';
}

export function formatSyncLabel(iso: string | null): string {
  if (!iso) return 'brak synchronizacji';
  return new Date(iso).toLocaleString('pl-PL', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatIssueDate(iso: string): string {
  return iso.slice(0, 10);
}
