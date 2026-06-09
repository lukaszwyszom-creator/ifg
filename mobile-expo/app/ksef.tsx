import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { ScreenShell } from '@/components/ScreenShell';
import { dashboardMock, formatPln } from '@/data/mock';
import { colors } from '@/theme/colors';

export default function KsefScreen() {
  const [syncing, setSyncing] = useState(false);
  const [lastSync, setLastSync] = useState(dashboardMock.ksef.lastSyncLabel);
  const k = dashboardMock.ksef;

  const handleSync = () => {
    setSyncing(true);
    setTimeout(() => {
      setSyncing(false);
      setLastSync('właśnie teraz (demo)');
    }, 1500);
  };

  return (
    <ScreenShell title="Import KSeF" subtitle="Synchronizacja faktur zakupowych" showBack scroll>
      <View style={styles.statusCard}>
        <View style={styles.statusRow}>
          <View style={styles.statusDot} />
          <Text style={styles.statusLabel}>{k.statusLabel}</Text>
        </View>
        <Text style={styles.meta}>Sesja aktywna · NIP z ustawień IFG</Text>
        <Text style={styles.meta}>Ostatnia synchronizacja: {lastSync}</Text>
        <Text style={styles.meta}>Nowe dokumenty (ostatni sync): {k.newCount}</Text>
      </View>

      <Pressable
        style={[styles.syncBtn, syncing && styles.syncBtnDisabled]}
        onPress={handleSync}
        disabled={syncing}
      >
        <Text style={styles.syncBtnText}>{syncing ? 'Pobieranie…' : 'Pobierz faktury z KSeF'}</Text>
      </Pressable>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Ostatnio pobrane (demo)</Text>
        {dashboardMock.recentPurchases.map((p) => (
          <View key={p.id} style={styles.purchaseRow}>
            <View style={styles.purchaseMain}>
              <Text style={styles.purchaseName}>{p.supplier}</Text>
              <Text style={styles.purchaseMeta}>{p.number}</Text>
            </View>
            <Text style={styles.purchaseAmount}>{formatPln(p.gross)}</Text>
          </View>
        ))}
      </View>

      <Text style={styles.footer}>
        IFGM nie łączy się bezpośrednio z KSeF. W produkcji: POST /api/v1/ksef/sync/purchases
      </Text>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  statusCard: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.success,
    padding: 16,
    gap: 8,
  },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  statusDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: colors.success },
  statusLabel: { color: colors.success, fontSize: 18, fontWeight: '700' },
  meta: { color: colors.textMuted, fontSize: 12 },
  syncBtn: {
    backgroundColor: colors.gold,
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
  },
  syncBtnDisabled: { opacity: 0.6 },
  syncBtnText: { color: colors.bg, fontSize: 16, fontWeight: '800' },
  section: { gap: 8, marginTop: 4 },
  sectionTitle: { color: colors.text, fontSize: 14, fontWeight: '700' },
  purchaseRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  purchaseMain: { flex: 1, gap: 2 },
  purchaseName: { color: colors.text, fontSize: 14, fontWeight: '600' },
  purchaseMeta: { color: colors.textMuted, fontSize: 11 },
  purchaseAmount: { color: colors.text, fontSize: 14, fontWeight: '700' },
  footer: { color: colors.textDim, fontSize: 10, lineHeight: 14, marginTop: 8 },
});
