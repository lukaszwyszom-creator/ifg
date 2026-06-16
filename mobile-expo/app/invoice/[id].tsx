import { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { fetchInvoice, InvoiceResponse, invoiceDisplayNumber, mapInvoiceItemForDisplay, parseAmount } from '@/api/mobile';
import { isAuthFailure } from '@/api/auth';
import { useAuth } from '@/auth/AuthContext';
import { ScreenShell } from '@/components/ScreenShell';
import { formatPln } from '@/data/mock';
import { colors } from '@/theme/colors';

const STATUS_LABELS: Record<string, string> = {
  paid: 'Opłacona',
  partial: 'Częściowo opłacona',
  unpaid: 'Nieopłacona',
};

function resolveId(raw: string | string[] | undefined): string | null {
  if (typeof raw === 'string' && raw.trim()) {
    return raw;
  }
  if (Array.isArray(raw) && raw[0]?.trim()) {
    return raw[0];
  }
  return null;
}

function snapshotField(snapshot: Record<string, unknown>, key: string): string {
  const value = snapshot[key];
  return typeof value === 'string' ? value.trim() : '';
}

function contractorFromInvoice(invoice: InvoiceResponse): { name: string; nip: string } {
  const snapshot = invoice.direction === 'purchase' ? invoice.seller_snapshot : invoice.buyer_snapshot;
  return {
    name: snapshotField(snapshot, 'name') || 'Nieznany kontrahent',
    nip: snapshotField(snapshot, 'nip') || '—',
  };
}

function paidAmount(invoice: InvoiceResponse): number {
  if (invoice.paid_amount != null) {
    return parseAmount(invoice.paid_amount);
  }
  if (invoice.remaining_amount != null) {
    return Math.max(0, parseAmount(invoice.total_gross) - parseAmount(invoice.remaining_amount));
  }
  return 0;
}

function remainingAmount(invoice: InvoiceResponse): number {
  if (invoice.remaining_amount != null) {
    return parseAmount(invoice.remaining_amount);
  }
  return Math.max(0, parseAmount(invoice.total_gross) - paidAmount(invoice));
}

function paymentStatusKey(invoice: InvoiceResponse): string {
  const status = invoice.payment_status?.toLowerCase();
  if (status === 'paid' || status === 'partial' || status === 'unpaid') {
    return status;
  }
  const gross = parseAmount(invoice.total_gross);
  const paid = paidAmount(invoice);
  if (paid <= 0) return 'unpaid';
  if (paid >= gross) return 'paid';
  return 'partial';
}

function buildHistory(invoice: InvoiceResponse, paid: number, gross: number) {
  const rows: { date: string; label: string; amount?: number }[] = [];
  const issueDate = invoice.issue_date.slice(0, 10);
  if (invoice.direction === 'purchase' && invoice.ksef_reference_number) {
    rows.push({ date: issueDate, label: 'Pobrano z KSeF' });
  } else {
    rows.push({ date: issueDate, label: 'Wystawiono fakturę' });
  }
  if (paid > 0) {
    rows.push({
      date: issueDate,
      label: paid >= gross ? 'Opłacono w całości' : 'Częściowa płatność',
      amount: paid,
    });
  }
  return rows;
}

export default function InvoiceDetailScreen() {
  const { id: rawId } = useLocalSearchParams<{ id: string }>();
  const id = resolveId(rawId);
  const router = useRouter();
  const { logout } = useAuth();
  const [invoice, setInvoice] = useState<InvoiceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) {
      setInvoice(null);
      setError('Nie znaleziono faktury');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const payload = await fetchInvoice(id);
      setInvoice(payload);
    } catch (err) {
      if (isAuthFailure(err)) {
        logout();
        router.replace('/login');
        return;
      }
      setInvoice(null);
      setError(err instanceof Error ? err.message : 'Nie udało się pobrać faktury');
    } finally {
      setLoading(false);
    }
  }, [id, logout, router]);

  useEffect(() => {
    load();
  }, [load]);

  const viewModel = useMemo(() => {
    if (!invoice) {
      return null;
    }
    const contractor = contractorFromInvoice(invoice);
    const gross = parseAmount(invoice.total_gross);
    const paid = paidAmount(invoice);
    const remaining = remainingAmount(invoice);
    const statusKey = paymentStatusKey(invoice);
    return {
      number: invoiceDisplayNumber(invoice),
      direction: invoice.direction,
      contractorName: contractor.name,
      contractorNip: contractor.nip,
      ksefNumber: invoice.ksef_reference_number,
      statusKey,
      gross,
      paid,
      remaining,
      issueDate: invoice.issue_date.slice(0, 10),
      dueDate: invoice.due_date?.slice(0, 10) ?? '—',
      items: invoice.items.map((item, idx) => mapInvoiceItemForDisplay(item, idx)),
      history: buildHistory(invoice, paid, gross),
    };
  }, [invoice]);

  if (loading) {
    return (
      <ScreenShell title="Faktura" subtitle="Szczegóły" showBack scroll>
        <View style={styles.stateBox}>
          <ActivityIndicator color={colors.gold} size="large" />
          <Text style={styles.stateText}>Ładowanie faktury…</Text>
        </View>
      </ScreenShell>
    );
  }

  if (error || !viewModel) {
    return (
      <ScreenShell title="Faktura" subtitle="Szczegóły" showBack scroll>
        <View style={styles.stateBox}>
          <Text style={styles.errorText}>{error ?? 'Nie znaleziono faktury'}</Text>
          <Pressable style={styles.retryBtn} onPress={load}>
            <Text style={styles.retryText}>Spróbuj ponownie</Text>
          </Pressable>
        </View>
      </ScreenShell>
    );
  }

  const statusLabel = STATUS_LABELS[viewModel.statusKey] ?? STATUS_LABELS.unpaid;

  return (
    <ScreenShell
      title={viewModel.number}
      subtitle={viewModel.direction === 'sale' ? 'Sprzedaż' : 'Zakup'}
      showBack
      scroll
    >
      <View style={styles.card}>
        <Text style={styles.sectionLabel}>Kontrahent</Text>
        <Text style={styles.contractorName}>{viewModel.contractorName}</Text>
        <Text style={styles.meta}>NIP {viewModel.contractorNip}</Text>
        {viewModel.ksefNumber ? <Text style={styles.ksef}>KSeF: {viewModel.ksefNumber}</Text> : null}
      </View>

      <View style={styles.card}>
        <View style={styles.rowBetween}>
          <Text style={styles.label}>Status płatności</Text>
          <Text style={[styles.badge, viewModel.statusKey === 'paid' ? styles.badgeOk : styles.badgeWarn]}>
            {statusLabel}
          </Text>
        </View>
        <View style={styles.amounts}>
          <View style={styles.amountCol}>
            <Text style={styles.amountLabel}>Brutto</Text>
            <Text style={styles.amountValue}>{formatPln(viewModel.gross)}</Text>
          </View>
          <View style={styles.amountCol}>
            <Text style={styles.amountLabel}>Zapłacono</Text>
            <Text style={styles.amountValue}>{formatPln(viewModel.paid)}</Text>
          </View>
          <View style={styles.amountCol}>
            <Text style={styles.amountLabel}>Pozostało</Text>
            <Text style={[styles.amountValue, viewModel.remaining > 0 && styles.danger]}>
              {formatPln(viewModel.remaining)}
            </Text>
          </View>
        </View>
        <Text style={styles.meta}>
          Wystawiono: {viewModel.issueDate} · Termin: {viewModel.dueDate}
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.sectionLabel}>Pozycje</Text>
        {viewModel.items.length === 0 ? (
          <Text style={styles.empty}>Brak pozycji.</Text>
        ) : (
          viewModel.items.map((item) => (
            <View key={`${item.lineNumber}-${item.name}`} style={styles.itemRow}>
              <Text style={styles.itemHeader}>
                {item.lineNumber}. {item.name}
              </Text>
              <Text style={styles.itemQuantity}>Ilość: {item.quantityLabel}</Text>
              <View style={styles.itemAmounts}>
                <View style={styles.itemAmountCol}>
                  <Text style={styles.itemAmountLabel}>Netto</Text>
                  <Text style={styles.itemAmountValue}>{item.netLabel}</Text>
                </View>
                <View style={styles.itemAmountCol}>
                  <Text style={styles.itemAmountLabel}>VAT %</Text>
                  <Text style={styles.itemAmountValue}>{item.vatRateLabel}</Text>
                </View>
                <View style={styles.itemAmountCol}>
                  <Text style={styles.itemAmountLabel}>Kwota VAT</Text>
                  <Text style={styles.itemAmountValue}>{item.vatLabel}</Text>
                </View>
              </View>
            </View>
          ))
        )}
      </View>

      <View style={styles.card}>
        <Text style={styles.sectionLabel}>Historia</Text>
        {viewModel.history.map((h, idx) => (
          <View key={idx} style={styles.historyRow}>
            <Text style={styles.historyDate}>{h.date}</Text>
            <View style={styles.historyMain}>
              <Text style={styles.historyLabel}>{h.label}</Text>
              {h.amount != null ? <Text style={styles.historyAmount}>{formatPln(h.amount)}</Text> : null}
            </View>
          </View>
        ))}
      </View>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  stateBox: {
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    paddingVertical: 32,
  },
  stateText: { color: colors.textMuted, fontSize: 16 },
  errorText: { color: colors.danger, fontSize: 16, textAlign: 'center' },
  retryBtn: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
  retryText: { color: colors.gold, fontSize: 15, fontWeight: '600' },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
    gap: 8,
  },
  sectionLabel: { color: colors.gold, fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  contractorName: { color: colors.text, fontSize: 18, fontWeight: '700' },
  meta: { color: colors.textMuted, fontSize: 12 },
  ksef: { color: colors.goldDim, fontSize: 11 },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  label: { color: colors.textMuted, fontSize: 13 },
  badge: { fontSize: 12, fontWeight: '700', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  badgeOk: { backgroundColor: 'rgba(61,214,140,0.15)', color: colors.success },
  badgeWarn: { backgroundColor: colors.goldGlow, color: colors.gold },
  amounts: { flexDirection: 'row', gap: 8, marginTop: 4 },
  amountCol: { flex: 1, gap: 2 },
  amountLabel: { color: colors.textDim, fontSize: 10 },
  amountValue: { color: colors.text, fontSize: 14, fontWeight: '700' },
  danger: { color: colors.danger },
  empty: { color: colors.textDim, fontSize: 12, fontStyle: 'italic' },
  itemRow: {
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: 6,
  },
  itemHeader: { color: colors.text, fontSize: 14, fontWeight: '600' },
  itemQuantity: { color: colors.textMuted, fontSize: 12 },
  itemAmounts: { flexDirection: 'row', gap: 8, marginTop: 2 },
  itemAmountCol: { flex: 1, gap: 2 },
  itemAmountLabel: { color: colors.textDim, fontSize: 10, textTransform: 'uppercase' },
  itemAmountValue: { color: colors.text, fontSize: 13, fontWeight: '600' },
  historyRow: { flexDirection: 'row', gap: 10, paddingVertical: 6 },
  historyDate: { color: colors.textDim, fontSize: 11, width: 72 },
  historyMain: { flex: 1, gap: 2 },
  historyLabel: { color: colors.text, fontSize: 13 },
  historyAmount: { color: colors.gold, fontSize: 12 },
});
