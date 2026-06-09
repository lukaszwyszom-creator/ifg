import { Pressable, StyleSheet, Text, View } from 'react-native';
import { ScreenShell } from '@/components/ScreenShell';
import { formatPln, unassignedPayments } from '@/data/mock';
import { colors } from '@/theme/colors';

export default function PaymentsUnassignedScreen() {
  return (
    <ScreenShell
      title="Płatności do przypisania"
      subtitle={`${unassignedPayments.length} transakcji · ${formatPln(unassignedPayments.reduce((s, p) => s + p.amount, 0))}`}
      showBack
      scroll
    >
      {unassignedPayments.map((p) => (
        <Pressable key={p.id} style={styles.card}>
          <View style={styles.cardTop}>
            <Text style={styles.counterparty}>{p.counterparty}</Text>
            <Text style={styles.amount}>{formatPln(p.amount)}</Text>
          </View>
          <Text style={styles.title}>{p.title}</Text>
          <Text style={styles.date}>{p.date}</Text>
          <View style={styles.actions}>
            <Text style={styles.actionBtn}>Przypisz do faktury →</Text>
          </View>
        </Pressable>
      ))}
      <Text style={styles.hint}>Prototyp — przypisanie bez akcji backendowej.</Text>
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
    gap: 6,
  },
  cardTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  counterparty: { color: colors.text, fontSize: 16, fontWeight: '700', flex: 1 },
  amount: { color: colors.gold, fontSize: 17, fontWeight: '800' },
  title: { color: colors.textMuted, fontSize: 13 },
  date: { color: colors.textDim, fontSize: 11 },
  actions: { marginTop: 6, paddingTop: 8, borderTopWidth: 1, borderTopColor: colors.border },
  actionBtn: { color: colors.gold, fontSize: 13, fontWeight: '600' },
  hint: { color: colors.textDim, fontSize: 11, textAlign: 'center', marginTop: 8 },
});
