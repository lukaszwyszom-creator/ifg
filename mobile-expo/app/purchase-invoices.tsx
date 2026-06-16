import { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import {
  contractorNameFromListItem,
  dueLabel,
  fetchInvoices,
  InvoiceListItem,
  invoiceDisplayNumber,
  invoiceListDisplayAmount,
  normalizePaymentStatus,
  parseMonthParam,
} from '@/api/mobile';
import { isAuthFailure } from '@/api/auth';
import { useAuth } from '@/auth/AuthContext';
import { ScreenShell } from '@/components/ScreenShell';
import { SearchBar } from '@/components/SearchBar';
import { formatPln } from '@/data/mock';
import { colors } from '@/theme/colors';

type Filter = 'all' | 'ksef' | 'unpaid' | 'paid';

export default function PurchaseInvoicesScreen() {
  const router = useRouter();
  const { month: rawMonth } = useLocalSearchParams<{ month?: string }>();
  const month = parseMonthParam(rawMonth);
  const { logout } = useAuth();
  const [invoices, setInvoices] = useState<InvoiceListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<Filter>('all');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchInvoices({ direction: 'purchase', month });
      setInvoices(res.items);
    } catch (err) {
      if (isAuthFailure(err)) {
        logout();
        router.replace('/login');
        return;
      }
      setInvoices([]);
      setError(err instanceof Error ? err.message : 'Nie udało się pobrać faktur zakupu');
    } finally {
      setLoading(false);
    }
  }, [logout, router, month]);

  useEffect(() => {
    load();
  }, [load]);

  const items = useMemo(() => {
    return invoices.filter((inv) => {
      const status = normalizePaymentStatus(inv.payment_status);
      if (filter === 'ksef' && !inv.ksef_reference_number) return false;
      if (filter === 'unpaid' && status !== 'unpaid') return false;
      if (filter === 'paid' && status !== 'paid') return false;
      const q = query.trim().toLowerCase();
      if (!q) return true;
      const number = invoiceDisplayNumber(inv).toLowerCase();
      const contractor = contractorNameFromListItem(inv).toLowerCase();
      const ksef = (inv.ksef_reference_number ?? '').toLowerCase();
      return number.includes(q) || contractor.includes(q) || ksef.includes(q);
    });
  }, [invoices, query, filter]);

  const chips: { key: Filter; label: string }[] = [
    { key: 'all', label: 'Wszystkie' },
    { key: 'ksef', label: 'Z KSeF' },
    { key: 'unpaid', label: 'Do zapłaty' },
    { key: 'paid', label: 'Opłacone' },
  ];

  return (
    <ScreenShell
      title="Faktury zakupu"
      subtitle={month ? `Okres: ${month}` : undefined}
      showBack
      scroll
    >
      <SearchBar value={query} onChangeText={setQuery} placeholder="Dostawca, numer, KSeF…" />
      <View style={styles.filters}>
        {chips.map((f) => (
          <Pressable
            key={f.key}
            style={[styles.chip, filter === f.key && styles.chipActive]}
            onPress={() => setFilter(f.key)}
          >
            <Text style={[styles.chipText, filter === f.key && styles.chipTextActive]}>{f.label}</Text>
          </Pressable>
        ))}
      </View>

      {loading ? (
        <View style={styles.stateBox}>
          <ActivityIndicator color={colors.gold} size="large" />
          <Text style={styles.stateText}>Ładowanie faktur…</Text>
        </View>
      ) : null}

      {!loading && error ? (
        <View style={styles.stateBox}>
          <Text style={styles.errorText}>{error}</Text>
          <Pressable style={styles.retryBtn} onPress={load}>
            <Text style={styles.retryText}>Spróbuj ponownie</Text>
          </Pressable>
        </View>
      ) : null}

      {!loading && !error && items.length === 0 ? (
        <Text style={styles.emptyText}>Brak faktur zakupu</Text>
      ) : null}

      {!loading && !error
        ? items.map((inv) => {
            const isOverdue = inv.overdue_days != null && inv.overdue_days > 0;
            return (
            <Pressable key={inv.id} style={styles.row} onPress={() => router.push(`/invoice/${inv.id}`)}>
              <View style={styles.rowMain}>
                <Text style={styles.name}>{contractorNameFromListItem(inv)}</Text>
                <Text style={styles.number}>{invoiceDisplayNumber(inv)}</Text>
                {inv.ksef_reference_number ? (
                  <Text style={styles.ksef}>{inv.ksef_reference_number}</Text>
                ) : null}
                <Text style={[styles.due, isOverdue && styles.dueOver]}>{dueLabel(inv.due_date)}</Text>
              </View>
              <Text style={styles.amount}>{formatPln(invoiceListDisplayAmount(inv))}</Text>
            </Pressable>
            );
          })
        : null}
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  filters: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: { borderColor: colors.gold, backgroundColor: colors.goldGlow },
  chipText: { color: colors.textMuted, fontSize: 12 },
  chipTextActive: { color: colors.gold, fontWeight: '600' },
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
  emptyText: { color: colors.textMuted, fontSize: 15, paddingVertical: 8 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: colors.border,
  },
  rowMain: { flex: 1, gap: 3 },
  name: { color: colors.text, fontSize: 15, fontWeight: '600' },
  number: { color: colors.textMuted, fontSize: 12 },
  ksef: { color: colors.goldDim, fontSize: 10 },
  due: { color: colors.textMuted, fontSize: 11 },
  dueOver: { color: colors.danger },
  amount: { color: colors.text, fontSize: 15, fontWeight: '700' },
});
