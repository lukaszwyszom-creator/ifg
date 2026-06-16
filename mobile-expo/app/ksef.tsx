import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { fetchDashboard, formatSyncLabel } from '@/api/mobile';
import { isAuthFailure } from '@/api/auth';
import { useAuth } from '@/auth/AuthContext';
import { ScreenShell } from '@/components/ScreenShell';
import { colors } from '@/theme/colors';

function currentPeriodKey(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

export default function KsefScreen() {
  const router = useRouter();
  const { logout } = useAuth();
  const [lastSyncAt, setLastSyncAt] = useState<string | null>(null);
  const [newCount, setNewCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDashboard(currentPeriodKey());
      setLastSyncAt(data.ksef_last_sync_at);
      setNewCount(data.ksef_new_invoices_count);
    } catch (err) {
      if (isAuthFailure(err)) {
        logout();
        router.replace('/login');
        return;
      }
      setError(err instanceof Error ? err.message : 'Nie udało się pobrać danych KSeF z IFG');
    } finally {
      setLoading(false);
    }
  }, [logout, router]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <ScreenShell title="KSeF w IFG" subtitle="Faktury zakupowe z KSeF" showBack scroll>
      <View style={styles.infoCard}>
        <Text style={styles.infoTitle}>Jak to działa</Text>
        <Text style={styles.infoText}>IFGM pokazuje faktury KSeF pobrane przez IFG.</Text>
        <Text style={styles.infoText}>Synchronizacja KSeF odbywa się po stronie IFG — nie z telefonu.</Text>
      </View>

      {loading ? (
        <View style={styles.stateBox}>
          <ActivityIndicator color={colors.gold} />
          <Text style={styles.stateText}>Ładowanie danych z IFG…</Text>
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
        <View style={styles.statusCard}>
          <Text style={styles.statusLabel}>Ostatni import</Text>
          <Text style={styles.statusValue}>{formatSyncLabel(lastSyncAt)}</Text>
          <Text style={styles.meta}>Faktury z ostatniego importu: {newCount ?? 0}</Text>
        </View>
      ) : null}

      <Pressable style={styles.backBtn} onPress={() => router.back()}>
        <Text style={styles.backBtnText}>Wróć</Text>
      </Pressable>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  infoCard: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 16,
    gap: 8,
  },
  infoTitle: { color: colors.gold, fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  infoText: { color: colors.textMuted, fontSize: 14, lineHeight: 20 },
  stateBox: { alignItems: 'center', gap: 10, paddingVertical: 24 },
  stateText: { color: colors.textMuted, fontSize: 14 },
  errorText: { color: colors.danger, fontSize: 14, textAlign: 'center' },
  retryBtn: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
  retryText: { color: colors.gold, fontSize: 14, fontWeight: '600' },
  statusCard: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 16,
    gap: 6,
  },
  statusLabel: { color: colors.textMuted, fontSize: 12, fontWeight: '600', textTransform: 'uppercase' },
  statusValue: { color: colors.text, fontSize: 18, fontWeight: '700' },
  meta: { color: colors.textDim, fontSize: 13 },
  backBtn: {
    marginTop: 8,
    backgroundColor: colors.surface,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: 14,
    alignItems: 'center',
  },
  backBtnText: { color: colors.gold, fontSize: 15, fontWeight: '600' },
});
