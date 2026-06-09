import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import {
  DashboardResponse,
  fetchDashboard,
  formatIssueDate,
  formatSyncLabel,
  ksefStatusLabel,
  parseAmount,
} from '@/api/mobile';
import { isAuthFailure } from '@/api/auth';
import { useAuth } from '@/auth/AuthContext';
import { KpiTile } from '@/components/KpiTile';
import { DashboardHeader } from '@/components/DashboardHeader';
import { ScreenShell } from '@/components/ScreenShell';
import { formatPln } from '@/data/mock';
import { colors } from '@/theme/colors';

function currentPeriod(): { year: number; month: number } {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

function periodKey(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, '0')}`;
}

export default function DashboardScreen() {
  const router = useRouter();
  const { logout } = useAuth();
  const initial = currentPeriod();
  const [periodYear, setPeriodYear] = useState(initial.year);
  const [periodMonth, setPeriodMonth] = useState(initial.month);
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchDashboard(periodKey(periodYear, periodMonth));
      setData(payload);
    } catch (err) {
      if (isAuthFailure(err)) {
        logout();
        router.replace('/login');
        return;
      }
      setData(null);
      setError(err instanceof Error ? err.message : 'Nie udało się pobrać dashboardu');
    } finally {
      setLoading(false);
    }
  }, [periodYear, periodMonth, logout, router]);

  useEffect(() => {
    load();
  }, [load]);

  const vatIsDue = data?.vat_label !== 'refund';
  const vatTitle = vatIsDue ? 'VAT do zapłaty' : 'VAT do odliczenia';
  const vatValueColor = vatIsDue ? colors.vatDue : colors.vatRefund;
  const debtorsOverdue = data ? parseAmount(data.debtors_overdue_due) : 0;
  const creditorsOverdue = data ? parseAmount(data.creditors_overdue_due) : 0;

  return (
    <ScreenShell scroll>
      <DashboardHeader
        periodYear={periodYear}
        periodMonth={periodMonth}
        onPeriodChange={(y, m) => {
          setPeriodYear(y);
          setPeriodMonth(m);
        }}
      />

      {loading ? (
        <View style={styles.stateBox}>
          <ActivityIndicator color={colors.gold} size="large" />
          <Text style={styles.stateText}>Ładowanie dashboardu…</Text>
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

      {!loading && !error && data ? (
        <>
          <View style={styles.hero}>
            <View style={styles.heroRow}>
              <View style={styles.heroCol}>
                <Text style={styles.heroLabel}>Sprzedaż netto</Text>
                <Text style={[styles.heroValue, styles.salesValue]} numberOfLines={1}>
                  {formatPln(data.sales_net)}
                </Text>
              </View>
              <View style={styles.heroDivider} />
              <View style={styles.heroCol}>
                <Text style={styles.heroLabel}>Zakup netto</Text>
                <Text style={[styles.heroValue, styles.purchaseValue]} numberOfLines={1}>
                  {formatPln(data.purchase_net)}
                </Text>
              </View>
            </View>
            <View style={styles.heroVat}>
              <Text style={styles.vatLabel} numberOfLines={1}>
                {vatTitle}
              </Text>
              <Text style={[styles.vatValue, { color: vatValueColor }]}>
                {formatPln(Math.abs(parseAmount(data.vat_balance)))}
              </Text>
            </View>
          </View>

          <View style={styles.kpiGrid}>
            <KpiTile
              large
              compactLabel
              heroPrimary
              label="Dłużnicy"
              primary={formatPln(data.debtors_total_due)}
              secondary={`${data.debtors_count} pozycji`}
              overdueAmount={debtorsOverdue > 0 ? formatPln(data.debtors_overdue_due) : undefined}
              danger={debtorsOverdue > 0}
              onPress={() => router.push('/debtors')}
            />
            <KpiTile
              large
              compactLabel
              heroPrimary
              label="Wierzyciele"
              primary={formatPln(data.creditors_total_due)}
              secondary={`${data.creditors_count} pozycji`}
              overdueAmount={creditorsOverdue > 0 ? formatPln(data.creditors_overdue_due) : undefined}
              onPress={() => router.push('/settlements')}
            />
            <KpiTile
              large
              label="Płatności"
              labelLine2="do przypisania"
              primary={String(data.unassigned_payments_count)}
              secondary={formatPln(data.unassigned_payments_total)}
              onPress={() => router.push('/payments-unassigned')}
            />
            <KpiTile
              large
              label="KSeF"
              primary={ksefStatusLabel(data.ksef_connection_status)}
              secondary={`${data.ksef_new_invoices_count} nowe zakupy`}
              accent={formatSyncLabel(data.ksef_last_sync_at)}
              compactAccent
              onPress={() => router.push('/ksef')}
            />
          </View>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Ostatnie zakupy KSeF</Text>
            {data.recent_purchase_invoices.length === 0 ? (
              <Text style={styles.emptyText}>Brak faktur zakupu w wybranym okresie</Text>
            ) : (
              data.recent_purchase_invoices.map((p) => (
                <Pressable
                  key={p.id}
                  style={styles.purchaseRow}
                  onPress={() => router.push(`/invoice/${p.id}`)}
                >
                  <View style={styles.purchaseMain}>
                    <Text style={styles.purchaseName}>{p.supplier_name}</Text>
                    <Text style={styles.purchaseMeta}>
                      {p.number} · {formatIssueDate(p.issue_date)}
                    </Text>
                  </View>
                  <Text style={styles.purchaseAmount}>{formatPln(p.amount_gross)}</Text>
                </Pressable>
              ))
            )}
          </View>

          <View style={styles.quickLinks}>
            <Pressable style={styles.quickLink} onPress={() => router.push('/sales-invoices')}>
              <Text style={styles.quickLinkText} numberOfLines={1}>FV sprzedaż</Text>
            </Pressable>
            <Pressable style={styles.quickLink} onPress={() => router.push('/purchase-invoices')}>
              <Text style={styles.quickLinkText} numberOfLines={1}>FV zakup</Text>
            </Pressable>
          </View>
        </>
      ) : null}
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
  hero: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.goldDim,
    padding: 16,
    gap: 14,
  },
  heroRow: { flexDirection: 'row', alignItems: 'center' },
  heroCol: { flex: 1, gap: 6, minWidth: 0 },
  heroDivider: { width: 1, height: 52, backgroundColor: colors.border, marginHorizontal: 6 },
  heroLabel: { color: colors.textMuted, fontSize: 15 },
  heroValue: { fontSize: 20, fontWeight: '700' },
  salesValue: { color: colors.sales },
  purchaseValue: { color: colors.purchase },
  heroVat: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: 12,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  vatLabel: { color: colors.textMuted, fontSize: 17, fontWeight: '600', flex: 1, flexShrink: 1, minWidth: 0 },
  vatValue: { fontSize: 23, fontWeight: '800', flexShrink: 0 },
  kpiGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  section: { gap: 8, marginTop: 4 },
  sectionTitle: { color: colors.text, fontSize: 19, fontWeight: '700' },
  purchaseRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  purchaseMain: { flex: 1, gap: 3, minWidth: 0 },
  purchaseName: { color: colors.text, fontSize: 19, fontWeight: '600' },
  purchaseMeta: { color: colors.textMuted, fontSize: 16 },
  purchaseAmount: { color: colors.text, fontSize: 21, fontWeight: '700' },
  quickLinks: { flexDirection: 'row', gap: 8, marginTop: 8 },
  quickLink: {
    flex: 1,
    backgroundColor: colors.surfaceElevated,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
  },
  quickLinkText: { color: colors.textMuted, fontSize: 15 },
});
