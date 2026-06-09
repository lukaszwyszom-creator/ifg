import { apiClient } from './client';
import { ensureApiAuth } from './auth';

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
