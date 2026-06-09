import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { ScreenShell } from '@/components/ScreenShell';
import { debtors, formatPln } from '@/data/mock';
import { colors } from '@/theme/colors';

export default function DebtorsListScreen() {
  const router = useRouter();
  const sorted = [...debtors].sort((a, b) => b.overdueDue - a.overdueDue || b.totalDue - a.totalDue);

  return (
    <ScreenShell title="Dłużnicy" subtitle="Należności po kontrahentach" showBack scroll>
      {sorted.map((d) => (
        <Pressable key={d.id} style={styles.card} onPress={() => router.push(`/debtors/${d.id}`)}>
          <View style={styles.cardHeader}>
            <Text style={styles.name}>{d.name}</Text>
            <Text style={styles.amount}>{formatPln(d.totalDue)}</Text>
          </View>
          <Text style={styles.meta}>
            {d.invoicesCount} faktur
            {d.overdueDue > 0 ? ` · po terminie ${formatPln(d.overdueDue)}` : ''}
          </Text>
          {d.lastNote ? (
            <View style={styles.notePreview}>
              <Text style={styles.noteDate}>{d.lastNote.date} {d.lastNote.time}</Text>
              <Text style={styles.noteText} numberOfLines={2}>{d.lastNote.text}</Text>
            </View>
          ) : (
            <Text style={styles.noNote}>Brak notatek</Text>
          )}
        </Pressable>
      ))}
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
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  name: { color: colors.text, fontSize: 16, fontWeight: '700', flex: 1, marginRight: 8 },
  amount: { color: colors.text, fontSize: 16, fontWeight: '700' },
  meta: { color: colors.textMuted, fontSize: 12 },
  notePreview: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: 8,
    padding: 10,
    borderLeftWidth: 3,
    borderLeftColor: colors.gold,
    gap: 4,
  },
  noteDate: { color: colors.goldDim, fontSize: 10, fontWeight: '600' },
  noteText: { color: colors.textMuted, fontSize: 12, lineHeight: 17 },
  noNote: { color: colors.textDim, fontSize: 11, fontStyle: 'italic' },
});
