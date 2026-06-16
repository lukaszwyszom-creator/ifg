import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { CounterpartyDetail, fetchCreditor, parseAmount } from '@/api/mobile';
import { isAuthFailure } from '@/api/auth';
import { useAuth } from '@/auth/AuthContext';
import { ScreenShell } from '@/components/ScreenShell';
import { formatPln } from '@/data/mock';
import { colors } from '@/theme/colors';

function resolveId(raw: string | string[] | undefined): string | null {
  if (typeof raw === 'string' && raw.trim()) {
    return raw;
  }
  if (Array.isArray(raw) && raw[0]?.trim()) {
    return raw[0];
  }
  return null;
}

export default function CreditorDetailScreen() {
  const { id: rawId } = useLocalSearchParams<{ id: string }>();
  const id = resolveId(rawId);
  const router = useRouter();
  const { logout } = useAuth();
  const [creditor, setCreditor] = useState<CounterpartyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) {
      setCreditor(null);
      setError('Nie znaleziono wierzyciela');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const payload = await fetchCreditor(id);
      setCreditor(payload);
    } catch (err) {
      if (isAuthFailure(err)) {
        logout();
        router.replace('/login');
        return;
      }
      setCreditor(null);
      setError(err instanceof Error ? err.message : 'Nie udało się pobrać wierzyciela');
    } finally {
      setLoading(false);
    }
  }, [id, logout, router]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <ScreenShell title="Wierzyciel" subtitle="Szczegóły wierzyciela" showBack scroll>
        <View style={styles.stateBox}>
          <ActivityIndicator color={colors.gold} size="large" />
          <Text style={styles.stateText}>Ładowanie szczegółów…</Text>
        </View>
      </ScreenShell>
    );
  }

  if (error || !creditor) {
    return (
      <ScreenShell title="Wierzyciel" subtitle="Szczegóły wierzyciela" showBack scroll>
        <View style={styles.stateBox}>
          <Text style={styles.errorText}>{error ?? 'Nie znaleziono wierzyciela'}</Text>
          <Pressable style={styles.retryBtn} onPress={load}>
            <Text style={styles.retryText}>Spróbuj ponownie</Text>
          </Pressable>
        </View>
      </ScreenShell>
    );
  }

  const overdueDue = parseAmount(creditor.overdue_due);

  return (
    <ScreenShell title={creditor.name} subtitle="Szczegóły wierzyciela" showBack scroll>
      <View style={styles.summary}>
        <View style={styles.summaryCol}>
          <Text style={styles.summaryLabel}>Zobowiązanie</Text>
          <Text style={styles.summaryValue}>{formatPln(creditor.total_due)}</Text>
        </View>
        <View style={styles.summaryCol}>
          <Text style={styles.summaryLabel}>Po terminie</Text>
          <Text style={[styles.summaryValue, overdueDue > 0 && styles.danger]}>
            {formatPln(creditor.overdue_due)}
          </Text>
        </View>
        <View style={styles.summaryCol}>
          <Text style={styles.summaryLabel}>Faktury</Text>
          <Text style={styles.summaryValue}>{creditor.invoices_count}</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Faktury</Text>
        {creditor.invoices.length === 0 ? (
          <Text style={styles.empty}>Brak faktur.</Text>
        ) : (
          creditor.invoices.map((inv) => (
            <Pressable
              key={inv.invoice_id}
              style={styles.invRow}
              onPress={() => router.push(`/invoice/${inv.invoice_id}`)}
            >
              <View style={styles.invMain}>
                <Text style={styles.invNumber}>{inv.number}</Text>
                <Text style={styles.invMeta}>Termin {inv.due_date ?? '—'}</Text>
              </View>
              <View style={styles.invRight}>
                <Text style={styles.invAmount}>{formatPln(inv.amount_due)}</Text>
                {inv.overdue_days != null && inv.overdue_days > 0 ? (
                  <Text style={styles.overdue}>{inv.overdue_days} dni po terminie</Text>
                ) : null}
              </View>
            </Pressable>
          ))
        )}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Historia notatek</Text>
        <Text style={styles.empty}>Brak notatek windykacyjnych.</Text>
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
  summary: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
    gap: 8,
  },
  summaryCol: { flex: 1, gap: 4, alignItems: 'center' },
  summaryLabel: { color: colors.textMuted, fontSize: 10, textTransform: 'uppercase' },
  summaryValue: { color: colors.text, fontSize: 15, fontWeight: '700' },
  danger: { color: colors.danger },
  section: { gap: 8 },
  sectionTitle: { color: colors.gold, fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  invRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  invMain: { flex: 1, gap: 2 },
  invNumber: { color: colors.text, fontSize: 14, fontWeight: '600' },
  invMeta: { color: colors.textMuted, fontSize: 11 },
  invRight: { alignItems: 'flex-end', gap: 2 },
  invAmount: { color: colors.text, fontSize: 14, fontWeight: '700' },
  overdue: { color: colors.danger, fontSize: 10 },
  empty: { color: colors.textDim, fontSize: 12, fontStyle: 'italic' },
});
