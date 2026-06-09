import { useMemo, useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { colors } from '@/theme/colors';

const MONTHS = [
  'styczeń', 'luty', 'marzec', 'kwiecień', 'maj', 'czerwiec',
  'lipiec', 'sierpień', 'wrzesień', 'październik', 'listopad', 'grudzień',
];

type Props = {
  year: number;
  month: number;
  onChange: (year: number, month: number) => void;
  fullWidth?: boolean;
};

export function formatPeriodLabel(year: number, month: number): string {
  return `${MONTHS[month - 1]} ${year}`;
}

export function PeriodSelector({ year, month, onChange, fullWidth }: Props) {
  const [open, setOpen] = useState(false);
  const [draftYear, setDraftYear] = useState(year);
  const [draftMonth, setDraftMonth] = useState(month);

  const label = useMemo(() => formatPeriodLabel(year, month), [year, month]);

  const openPicker = () => {
    setDraftYear(year);
    setDraftMonth(month);
    setOpen(true);
  };

  const apply = () => {
    onChange(draftYear, draftMonth);
    setOpen(false);
  };

  return (
    <>
      <Pressable
        style={[styles.chip, fullWidth && styles.chipFull]}
        onPress={openPicker}
        accessibilityRole="button"
      >
        <Text style={styles.chipText}>{label}</Text>
        <Text style={styles.chipHint}>▼</Text>
      </Pressable>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <Text style={styles.sheetTitle}>Okres</Text>

            <View style={styles.yearRow}>
              <Pressable style={styles.yearBtn} onPress={() => setDraftYear((y) => y - 1)}>
                <Text style={styles.yearBtnText}>‹</Text>
              </Pressable>
              <Text style={styles.yearValue}>{draftYear}</Text>
              <Pressable style={styles.yearBtn} onPress={() => setDraftYear((y) => y + 1)}>
                <Text style={styles.yearBtnText}>›</Text>
              </Pressable>
            </View>

            <View style={styles.monthGrid}>
              {MONTHS.map((name, idx) => {
                const m = idx + 1;
                const active = draftMonth === m;
                return (
                  <Pressable
                    key={name}
                    style={[styles.monthChip, active && styles.monthChipActive]}
                    onPress={() => setDraftMonth(m)}
                  >
                    <Text style={[styles.monthText, active && styles.monthTextActive]}>
                      {name.slice(0, 3)}
                    </Text>
                  </Pressable>
                );
              })}
            </View>

            <Pressable style={styles.applyBtn} onPress={apply}>
              <Text style={styles.applyText}>Zastosuj</Text>
            </Pressable>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.surface,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipFull: {
    width: '100%',
    justifyContent: 'space-between',
  },
  chipText: { color: colors.gold, fontSize: 18, fontWeight: '600' },
  chipHint: { color: colors.goldDim, fontSize: 12 },
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center',
    padding: 24,
  },
  sheet: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 18,
    gap: 14,
  },
  sheetTitle: { color: colors.text, fontSize: 21, fontWeight: '700', textAlign: 'center' },
  yearRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 20 },
  yearBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.surfaceElevated,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  yearBtnText: { color: colors.gold, fontSize: 24, fontWeight: '600' },
  yearValue: { color: colors.text, fontSize: 24, fontWeight: '700', minWidth: 64, textAlign: 'center' },
  monthGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, justifyContent: 'center' },
  monthChip: {
    width: '30%',
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: colors.surfaceElevated,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
  },
  monthChipActive: { borderColor: colors.gold, backgroundColor: colors.goldGlow },
  monthText: { color: colors.textMuted, fontSize: 15, fontWeight: '600' },
  monthTextActive: { color: colors.gold },
  applyBtn: {
    backgroundColor: colors.gold,
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 4,
  },
  applyText: { color: colors.bg, fontSize: 18, fontWeight: '800' },
});
