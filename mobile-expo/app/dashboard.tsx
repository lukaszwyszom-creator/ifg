import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { useRouter, Href } from 'expo-router';
import {
  DashboardResponse,
  fetchDashboard,
  fetchRecentKsefPurchaseInvoices,
  formatIssueDate,
  formatSyncLabel,
  parseAmount,
  RecentKsefPurchaseRow,
} from '@/api/mobile';
import { isAuthFailure } from '@/api/auth';
import { useAuth } from '@/auth/AuthContext';
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

type HorizontalKpiProps = {
  label: string;
  labelCompact?: boolean;
  lines?: string[];
  primary?: string;
  detail?: string;
  danger?: boolean;
  onPress?: () => void;
};

function HorizontalKpiTile({
  label,
  labelCompact,
  lines,
  primary,
  detail,
  danger,
  onPress,
}: HorizontalKpiProps) {
  return (
    <Pressable
      style={({ pressed }) => [styles.kpiRow, pressed && styles.kpiRowPressed]}
      onPress={onPress}
      disabled={!onPress}
    >
      <View style={styles.kpiRowLeft}>
        <Text style={[styles.kpiLabel, labelCompact && styles.kpiLabelCompact]} numberOfLines={1}>
          {label}
        </Text>
        {lines?.map((line) => (
          <Text
            key={line}
            style={[styles.kpiLine, danger && line.startsWith('Po terminie') && styles.kpiLineDanger]}
            numberOfLines={1}
          >
            {line}
          </Text>
        ))}
        {detail ? (
          <Text style={[styles.kpiDetail, danger && styles.kpiDetailDanger]} numberOfLines={1}>
            {detail}
          </Text>
        ) : null}
      </View>
      {primary ? (
        <Text style={[styles.kpiPrimary, danger && styles.dangerText]} numberOfLines={1}>
          {primary}
        </Text>
      ) : null}
    </Pressable>
  );
}

export default function DashboardScreen() {
  const router = useRouter();
  const { logout } = useAuth();
  const initial = currentPeriod();
  const [periodYear, setPeriodYear] = useState(initial.year);
  const [periodMonth, setPeriodMonth] = useState(initial.month);
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [recentKsef, setRecentKsef] = useState<RecentKsefPurchaseRow[]>([]);
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

  const loadRecentKsef = useCallback(async () => {
    try {
      const items = await fetchRecentKsefPurchaseInvoices(5);
      setRecentKsef(items);
    } catch (err) {
      if (isAuthFailure(err)) {
        logout();
        router.replace('/login');
        return;
      }
      setRecentKsef([]);
    }
  }, [logout, router]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    loadRecentKsef();
  }, [loadRecentKsef]);

  const vatIsDue = data?.vat_label !== 'refund';
  const vatTitle = vatIsDue ? 'VAT do zapłaty' : 'VAT do odliczenia';
  const vatValueColor = vatIsDue ? colors.vatDue : colors.vatRefund;
  const debtorsOverdue = data ? parseAmount(data.debtors_overdue_due) : 0;
  const creditorsOverdue = data ? parseAmount(data.creditors_overdue_due) : 0;
  const monthParam = periodKey(periodYear, periodMonth);

  const creditorLines = [`${data?.creditors_count ?? 0} pozycji`];
  if (data && creditorsOverdue > 0) {
    creditorLines.push(`Po terminie: ${formatPln(data.creditors_overdue_due)}`);
  }

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
            <View style={styles.heroLinks}>
              <Pressable
                style={styles.heroLinkBtn}
                onPress={() => router.push(`/sales-invoices?month=${monthParam}` as Href)}
              >
                <Text style={styles.heroLinkText} numberOfLines={1}>
                  FV sprzedaż
                </Text>
              </Pressable>
              <Pressable
                style={styles.heroLinkBtn}
                onPress={() => router.push(`/purchase-invoices?month=${monthParam}` as Href)}
              >
                <Text style={styles.heroLinkText} numberOfLines={1}>
                  FV zakup
                </Text>
              </Pressable>
            </View>
          </View>

          <View style={styles.globalSection}>
            <Text style={styles.globalSectionTitle}>Stan ogólny</Text>
            <Text style={styles.globalSectionHint}>Poza wybranym miesiącem</Text>
            <View style={styles.kpiList}>
              <HorizontalKpiTile
                label="Dłużnicy"
                primary={formatPln(data.debtors_total_due)}
                detail={
                  debtorsOverdue > 0
                    ? `${data.debtors_count} pozycji · Po terminie ${formatPln(data.debtors_overdue_due)}`
                    : `${data.debtors_count} pozycji`
                }
                danger={debtorsOverdue > 0}
                onPress={() => router.push('/debtors')}
              />
              <HorizontalKpiTile
                label="Wierzyciele"
                lines={creditorLines}
                primary={formatPln(data.creditors_total_due)}
                danger={creditorsOverdue > 0}
                onPress={() => router.push('/creditors' as Href)}
              />
              <HorizontalKpiTile
                label="Płatności do przypisania"
                labelCompact
                primary={String(data.unassigned_payments_count)}
                detail={formatPln(data.unassigned_payments_total)}
                onPress={() => router.push('/payments-unassigned')}
              />
              <HorizontalKpiTile
                label="KSeF w IFG"
                lines={[
                  `Ostatni import: ${formatSyncLabel(data.ksef_last_sync_at)}`,
                  `${data.ksef_new_invoices_count} faktur z KSeF`,
                ]}
                onPress={() => router.push('/ksef')}
              />
            </View>
          </View>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Ostatnie zakupy KSeF</Text>
            {recentKsef.length === 0 ? (
              <Text style={styles.emptyText}>Brak faktur zakupu z KSeF</Text>
            ) : (
              recentKsef.map((p) => (
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
  vatValue: { fontSize: 16, fontWeight: '700', flexShrink: 0 },
  heroLinks: {
    flexDirection: 'row',
    gap: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: 12,
  },
  heroLinkBtn: {
    flex: 1,
    backgroundColor: colors.surfaceElevated,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
  },
  heroLinkText: { color: colors.gold, fontSize: 13, fontWeight: '600' },
  globalSection: { gap: 4, marginTop: 4 },
  globalSectionTitle: { color: colors.text, fontSize: 17, fontWeight: '700' },
  globalSectionHint: { color: colors.textDim, fontSize: 12, marginBottom: 4 },
  kpiList: { gap: 8 },
  kpiRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  kpiRowPressed: { opacity: 0.85, borderColor: colors.goldDim },
  kpiRowLeft: { flex: 1, gap: 3, minWidth: 0 },
  kpiLabel: { color: colors.textMuted, fontSize: 13, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.4 },
  kpiLabelCompact: { fontSize: 11, letterSpacing: 0.2 },
  kpiLine: { color: colors.textDim, fontSize: 12 },
  kpiLineDanger: { color: colors.gold },
  kpiDetail: { color: colors.textDim, fontSize: 12 },
  kpiDetailDanger: { color: colors.gold },
  kpiPrimary: { color: colors.text, fontSize: 18, fontWeight: '700', flexShrink: 0, maxWidth: '42%', textAlign: 'right' },
  dangerText: { color: colors.danger },
  section: { gap: 8, marginTop: 8 },
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
  purchaseName: { color: colors.text, fontSize: 17, fontWeight: '600' },
  purchaseMeta: { color: colors.textMuted, fontSize: 14 },
  purchaseAmount: { color: colors.text, fontSize: 17, fontWeight: '700', flexShrink: 0 },
});
