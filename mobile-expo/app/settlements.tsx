import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { ScreenShell } from '@/components/ScreenShell';
import { debtors, dueLabel, formatPln, purchaseInvoices, salesInvoices } from '@/data/mock';
import { colors } from '@/theme/colors';

type Tab = 'receivables' | 'payables';

export default function SettlementsScreen() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>('receivables');

  const receivables = salesInvoices.filter((i) => i.status !== 'paid');
  const payables = purchaseInvoices.filter((i) => i.status !== 'paid');

  const items = tab === 'receivables' ? receivables : payables;

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

      <Pressable style={styles.summaryCard} onPress={() => router.push('/debtors')}>
        <Text style={styles.summaryLabel}>
          {tab === 'receivables' ? 'Agregat dłużników (demo)' : 'Wierzyciele — widok listy'}
        </Text>
        <Text style={styles.summaryValue}>
          {tab === 'receivables'
            ? `${debtors.length} kontrahentów · ${formatPln(debtors.reduce((s, d) => s + d.totalDue, 0))}`
            : `${formatPln(payables.reduce((s, i) => s + (i.gross - i.paid), 0))} do zapłaty`}
        </Text>
      </Pressable>

      {items.map((inv) => {
        const remaining = inv.gross - inv.paid;
        return (
          <Pressable key={inv.id} style={styles.row} onPress={() => router.push(`/invoice/${inv.id}`)}>
            <View style={styles.rowMain}>
              <Text style={styles.name}>{inv.contractorName}</Text>
              <Text style={styles.number}>{inv.number}</Text>
              <Text style={styles.due}>{dueLabel(inv.dueDate)}</Text>
            </View>
            <View style={styles.rowRight}>
              <Text style={styles.amount}>{formatPln(remaining)}</Text>
              <Text style={styles.remaining}>pozostało</Text>
            </View>
          </Pressable>
        );
      })}
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
