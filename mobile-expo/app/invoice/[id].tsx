import { useLocalSearchParams } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';
import { ScreenShell } from '@/components/ScreenShell';
import { allInvoices, formatPln } from '@/data/mock';
import { colors } from '@/theme/colors';

const STATUS_LABELS = { paid: 'Opłacona', partial: 'Częściowo opłacona', unpaid: 'Nieopłacona' };

export default function InvoiceDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const invoice =
    allInvoices.find((i) => i.id === id) ??
    allInvoices.find((i) => i.id === `inv-${id}`) ??
    allInvoices[0];

  const remaining = invoice.gross - invoice.paid;

  return (
    <ScreenShell title={invoice.number} subtitle={invoice.direction === 'sale' ? 'Sprzedaż' : 'Zakup'} showBack scroll>
      <View style={styles.card}>
        <Text style={styles.sectionLabel}>Kontrahent</Text>
        <Text style={styles.contractorName}>{invoice.contractorName}</Text>
        <Text style={styles.meta}>NIP {invoice.contractorNip}</Text>
        {invoice.ksefNumber ? <Text style={styles.ksef}>KSeF: {invoice.ksefNumber}</Text> : null}
      </View>

      <View style={styles.card}>
        <View style={styles.rowBetween}>
          <Text style={styles.label}>Status płatności</Text>
          <Text style={[styles.badge, invoice.status === 'paid' ? styles.badgeOk : styles.badgeWarn]}>
            {STATUS_LABELS[invoice.status]}
          </Text>
        </View>
        <View style={styles.amounts}>
          <View style={styles.amountCol}>
            <Text style={styles.amountLabel}>Brutto</Text>
            <Text style={styles.amountValue}>{formatPln(invoice.gross)}</Text>
          </View>
          <View style={styles.amountCol}>
            <Text style={styles.amountLabel}>Zapłacono</Text>
            <Text style={styles.amountValue}>{formatPln(invoice.paid)}</Text>
          </View>
          <View style={styles.amountCol}>
            <Text style={styles.amountLabel}>Pozostało</Text>
            <Text style={[styles.amountValue, remaining > 0 && styles.danger]}>{formatPln(remaining)}</Text>
          </View>
        </View>
        <Text style={styles.meta}>Wystawiono: {invoice.issueDate} · Termin: {invoice.dueDate}</Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.sectionLabel}>Pozycje</Text>
        {invoice.items.map((item, idx) => (
          <View key={idx} style={styles.itemRow}>
            <View style={styles.itemMain}>
              <Text style={styles.itemName}>{item.name}</Text>
              <Text style={styles.itemMeta}>
                {item.qty} {item.unit} · netto {formatPln(item.net)}
              </Text>
            </View>
            <Text style={styles.itemVat}>VAT {formatPln(item.vat)}</Text>
          </View>
        ))}
      </View>

      <View style={styles.card}>
        <Text style={styles.sectionLabel}>Historia</Text>
        {invoice.history.map((h, idx) => (
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
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  itemMain: { flex: 1, gap: 2 },
  itemName: { color: colors.text, fontSize: 14 },
  itemMeta: { color: colors.textMuted, fontSize: 11 },
  itemVat: { color: colors.textMuted, fontSize: 12 },
  historyRow: { flexDirection: 'row', gap: 10, paddingVertical: 6 },
  historyDate: { color: colors.textDim, fontSize: 11, width: 72 },
  historyMain: { flex: 1, gap: 2 },
  historyLabel: { color: colors.text, fontSize: 13 },
  historyAmount: { color: colors.gold, fontSize: 12 },
});
