import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { ScreenShell } from '@/components/ScreenShell';
import { SearchBar } from '@/components/SearchBar';
import { dueLabel, formatPln, salesInvoices } from '@/data/mock';
import { colors } from '@/theme/colors';

type Filter = 'all' | 'unpaid' | 'partial' | 'paid';

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'Wszystkie' },
  { key: 'unpaid', label: 'Nieopłacone' },
  { key: 'partial', label: 'Częściowo' },
  { key: 'paid', label: 'Opłacone' },
];

export default function SalesInvoicesScreen() {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<Filter>('all');

  const items = useMemo(() => {
    return salesInvoices.filter((inv) => {
      if (filter !== 'all' && inv.status !== filter) return false;
      const q = query.trim().toLowerCase();
      if (!q) return true;
      return inv.number.toLowerCase().includes(q) || inv.contractorName.toLowerCase().includes(q);
    });
  }, [query, filter]);

  return (
    <ScreenShell title="Faktury sprzedaży" showBack scroll>
      <SearchBar value={query} onChangeText={setQuery} placeholder="Numer lub kontrahent…" />
      <View style={styles.filters}>
        {FILTERS.map((f) => (
          <Pressable
            key={f.key}
            style={[styles.chip, filter === f.key && styles.chipActive]}
            onPress={() => setFilter(f.key)}
          >
            <Text style={[styles.chipText, filter === f.key && styles.chipTextActive]}>{f.label}</Text>
          </Pressable>
        ))}
      </View>
      {items.map((inv) => (
        <Pressable key={inv.id} style={styles.row} onPress={() => router.push(`/invoice/${inv.id}`)}>
          <View style={styles.rowMain}>
            <Text style={styles.name}>{inv.contractorName}</Text>
            <Text style={styles.number}>{inv.number}</Text>
            <Text style={[styles.due, inv.status === 'unpaid' && styles.dueOver]}>{dueLabel(inv.dueDate)}</Text>
          </View>
          <Text style={styles.amount}>{formatPln(inv.gross)}</Text>
        </Pressable>
      ))}
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  filters: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: { borderColor: colors.gold, backgroundColor: colors.goldGlow },
  chipText: { color: colors.textMuted, fontSize: 12 },
  chipTextActive: { color: colors.gold, fontWeight: '600' },
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
  dueOver: { color: colors.danger },
  amount: { color: colors.text, fontSize: 15, fontWeight: '700' },
});
