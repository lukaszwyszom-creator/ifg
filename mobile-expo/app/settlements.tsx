import { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { useRouter, Href } from 'expo-router';
import {
  dueLabel,
  fetchSettlements,
  parseAmount,
  SettlementItem,
  settlementContractorName,
  settlementDisplayNumber,
} from '@/api/mobile';
import { isAuthFailure } from '@/api/auth';
import { useAuth } from '@/auth/AuthContext';
import { ScreenShell } from '@/components/ScreenShell';
import { formatPln } from '@/data/mock';
import { colors } from '@/theme/colors';

type Tab = 'receivables' | 'payables';

function uniqueContractors(items: SettlementItem[]): number {
  const names = new Set(
    items.map((item) => settlementContractorName(item).toLowerCase()),
  );
  return names.size;
}

function sumRemaining(items: SettlementItem[]): number {
  return items.reduce((sum, item) => sum + parseAmount(item.remaining_amount), 0);
}

export default function SettlementsScreen() {
  const router = useRouter();
  const { logout } = useAuth();
  const [tab, setTab] = useState<Tab>('receivables');
  const [debtors, setDebtors] = useState<SettlementItem[]>([]);
  const [creditors, setCreditors] = useState<SettlementItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchSettlements();
      setDebtors(res.debtors);
      setCreditors(res.creditors);
    } catch (err) {
      if (isAuthFailure(err)) {
        logout();
        router.replace('/login');
        return;
      }
      setDebtors([]);
      setCreditors([]);
      setError(err instanceof Error ? err.message : 'Nie udało się pobrać rozrachunków');
    } finally {
      setLoading(false);
    }
  }, [logout, router]);

  useEffect(() => {
    load();
  }, [load]);

  const items = tab === 'receivables' ? debtors : creditors;

  const summaryLabel = tab === 'receivables' ? 'Agregat dłużników' : 'Agregat wierzycieli';
  const summaryValue = useMemo(() => {
    const count = uniqueContractors(items);
    const total = sumRemaining(items);
    return `${count} kontrahentów · ${formatPln(total)}`;
  }, [items]);

  const summaryRoute = (tab === 'receivables' ? '/debtors' : '/creditors') as Href;

  return (
    <ScreenShell title="Rozrachunki" subtitle="Należności i zobowiązania" showBack scroll>
      <View style={styles.tabs}>
        <Pressable
          style={[styles.tab, tab === 'receivables' && styles.tabActive]}
          onPress={() => setTab('receivables')}
        >
          <Text style={[styles.tabText, tab === 'receivables' && styles.tabTextActive]}>Należności</Text>
        </Pressable>
        <Pressable
          style={[styles.tab, tab === 'payables' && styles.tabActive]}
          onPress={() => setTab('payables')}
        >
          <Text style={[styles.tabText, tab === 'payables' && styles.tabTextActive]}>Zobowiązania</Text>
        </Pressable>
      </View>

      {loading ? (
        <View style={styles.stateBox}>
          <ActivityIndicator color={colors.gold} size="large" />
          <Text style={styles.stateText}>Ładowanie rozrachunków…</Text>
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

      {!loading && !error ? (
        <>
          <Pressable style={styles.summaryCard} onPress={() => router.push(summaryRoute)}>
            <Text style={styles.summaryLabel}>{summaryLabel}</Text>
            <Text style={styles.summaryValue}>{summaryValue}</Text>
          </Pressable>

          {items.length === 0 ? (
            <Text style={styles.emptyText}>
              {tab === 'receivables' ? 'Brak otwartych należności' : 'Brak otwartych zobowiązań'}
            </Text>
          ) : null}

          {items.map((inv) => (
            <Pressable
              key={inv.invoice_id}
              style={styles.row}
              onPress={() => router.push(`/invoice/${inv.invoice_id}`)}
            >
              <View style={styles.rowMain}>
                <Text style={styles.name}>{settlementContractorName(inv)}</Text>
                <Text style={styles.number}>{settlementDisplayNumber(inv)}</Text>
                <Text style={styles.due}>{dueLabel(inv.due_date)}</Text>
              </View>
              <View style={styles.rowRight}>
                <Text style={styles.amount}>{formatPln(inv.remaining_amount)}</Text>
                <Text style={styles.remaining}>pozostało</Text>
              </View>
            </Pressable>
          ))}
        </>
      ) : null}
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  tabs: { flexDirection: 'row', gap: 8 },
  tab: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 10,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
  },
  tabActive: { borderColor: colors.gold, backgroundColor: colors.goldGlow },
  tabText: { color: colors.textMuted, fontSize: 13, fontWeight: '600' },
  tabTextActive: { color: colors.gold },
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
  summaryCard: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: colors.border,
    gap: 4,
  },
  summaryLabel: { color: colors.textMuted, fontSize: 11 },
  summaryValue: { color: colors.text, fontSize: 14, fontWeight: '600' },
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
  due: { color: colors.textMuted, fontSize: 11 },
  rowRight: { alignItems: 'flex-end', gap: 2 },
  amount: { color: colors.text, fontSize: 15, fontWeight: '700' },
  remaining: { color: colors.textDim, fontSize: 10 },
});
