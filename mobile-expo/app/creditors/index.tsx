import { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { useRouter, Href } from 'expo-router';
import { CounterpartyListItem, fetchCreditors, parseAmount } from '@/api/mobile';
import { isAuthFailure } from '@/api/auth';
import { useAuth } from '@/auth/AuthContext';
import { ScreenShell } from '@/components/ScreenShell';
import { formatPln } from '@/data/mock';
import { colors } from '@/theme/colors';

export default function CreditorsListScreen() {
  const router = useRouter();
  const { logout } = useAuth();
  const [items, setItems] = useState<CounterpartyListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchCreditors();
      setItems(payload);
    } catch (err) {
      if (isAuthFailure(err)) {
        logout();
        router.replace('/login');
        return;
      }
      setItems([]);
      setError(err instanceof Error ? err.message : 'Nie udało się pobrać wierzycieli');
    } finally {
      setLoading(false);
    }
  }, [logout, router]);

  useEffect(() => {
    load();
  }, [load]);

  const sorted = useMemo(
    () =>
      [...items].sort(
        (a, b) =>
          parseAmount(b.overdue_due) - parseAmount(a.overdue_due) ||
          parseAmount(b.total_due) - parseAmount(a.total_due),
      ),
    [items],
  );

  return (
    <ScreenShell title="Wierzyciele" subtitle="Zobowiązania po kontrahentach" showBack scroll>
      {loading ? (
        <View style={styles.stateBox}>
          <ActivityIndicator color={colors.gold} size="large" />
          <Text style={styles.stateText}>Ładowanie wierzycieli…</Text>
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

      {!loading && !error && sorted.length === 0 ? (
        <Text style={styles.emptyText}>Brak zobowiązań po kontrahentach</Text>
      ) : null}

      {!loading && !error
        ? sorted.map((d) => {
            const overdueDue = parseAmount(d.overdue_due);
            return (
              <Pressable key={d.id} style={styles.card} onPress={() => router.push(`/creditors/${d.id}` as Href)}>
                <View style={styles.cardHeader}>
                  <Text style={styles.name}>{d.name}</Text>
                  <Text style={styles.amount}>{formatPln(d.total_due)}</Text>
                </View>
                <Text style={styles.meta}>
                  {d.invoices_count} faktur
                  {overdueDue > 0 ? ` · po terminie ${formatPln(d.overdue_due)}` : ''}
                </Text>
                <Text style={styles.noNote}>Brak notatek</Text>
              </Pressable>
            );
          })
        : null}
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
  emptyText: { color: colors.textMuted, fontSize: 15, paddingVertical: 8 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
    gap: 8,
  },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  name: { color: colors.text, fontSize: 16, fontWeight: '700', flex: 1, marginRight: 8 },
  amount: { color: colors.text, fontSize: 16, fontWeight: '700' },
  meta: { color: colors.textMuted, fontSize: 12 },
  noNote: { color: colors.textDim, fontSize: 11, fontStyle: 'italic' },
});
