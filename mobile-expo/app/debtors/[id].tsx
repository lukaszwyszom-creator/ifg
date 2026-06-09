import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { ScreenShell } from '@/components/ScreenShell';
import { debtors, formatPln } from '@/data/mock';
import { colors } from '@/theme/colors';

export default function DebtorDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const debtor = debtors.find((d) => d.id === id) ?? debtors[0];

  return (
    <ScreenShell title={debtor.name} subtitle="Szczegóły dłużnika" showBack scroll>
      <View style={styles.summary}>
        <View style={styles.summaryCol}>
          <Text style={styles.summaryLabel}>Należność</Text>
          <Text style={styles.summaryValue}>{formatPln(debtor.totalDue)}</Text>
        </View>
        <View style={styles.summaryCol}>
          <Text style={styles.summaryLabel}>Po terminie</Text>
          <Text style={[styles.summaryValue, debtor.overdueDue > 0 && styles.danger]}>
            {formatPln(debtor.overdueDue)}
          </Text>
        </View>
        <View style={styles.summaryCol}>
          <Text style={styles.summaryLabel}>Faktury</Text>
          <Text style={styles.summaryValue}>{debtor.invoicesCount}</Text>
        </View>
      </View>

      {debtor.lastNote ? (
        <View style={styles.latestNote}>
          <Text style={styles.sectionTitle}>Ostatnia notatka</Text>
          <Text style={styles.noteDate}>{debtor.lastNote.date} · {debtor.lastNote.time}</Text>
          <Text style={styles.noteBody}>{debtor.lastNote.text}</Text>
        </View>
      ) : null}

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Faktury</Text>
        {debtor.invoices.map((inv) => (
          <Pressable
            key={inv.invoiceId}
            style={styles.invRow}
            onPress={() => router.push(`/invoice/${inv.invoiceId}`)}
          >
            <View style={styles.invMain}>
              <Text style={styles.invNumber}>{inv.number}</Text>
              <Text style={styles.invMeta}>Termin {inv.dueDate}</Text>
            </View>
            <View style={styles.invRight}>
              <Text style={styles.invAmount}>{formatPln(inv.amountDue)}</Text>
              {inv.overdueDays != null && inv.overdueDays > 0 ? (
                <Text style={styles.overdue}>{inv.overdueDays} dni po terminie</Text>
              ) : null}
            </View>
          </Pressable>
        ))}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Historia notatek</Text>
        {debtor.notes.length === 0 ? (
          <Text style={styles.empty}>Brak notatek windykacyjnych.</Text>
        ) : (
          debtor.notes.map((note) => (
            <View key={note.id} style={styles.noteRow}>
              <Text style={styles.noteRowDate}>{note.date} · {note.time}</Text>
              <Text style={styles.noteRowText}>{note.text}</Text>
            </View>
          ))
        )}
      </View>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
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
  latestNote: {
    backgroundColor: colors.goldGlow,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.goldDim,
    padding: 14,
    gap: 6,
  },
  section: { gap: 8 },
  sectionTitle: { color: colors.gold, fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  noteDate: { color: colors.goldDim, fontSize: 11 },
  noteBody: { color: colors.text, fontSize: 14, lineHeight: 20 },
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
  noteRow: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: colors.border,
    gap: 4,
  },
  noteRowDate: { color: colors.textDim, fontSize: 11 },
  noteRowText: { color: colors.textMuted, fontSize: 13, lineHeight: 18 },
  empty: { color: colors.textDim, fontSize: 12, fontStyle: 'italic' },
});
