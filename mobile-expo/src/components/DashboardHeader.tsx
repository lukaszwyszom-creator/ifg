import { StyleSheet, Text, View } from 'react-native';
import { Logo } from '@/components/Logo';
import { PeriodSelector } from '@/components/PeriodSelector';
import { colors } from '@/theme/colors';

type Props = {
  periodYear: number;
  periodMonth: number;
  onPeriodChange: (year: number, month: number) => void;
};

export function DashboardHeader({ periodYear, periodMonth, onPeriodChange }: Props) {
  return (
    <View style={styles.header}>
      <View style={styles.brandRow}>
        <Logo />
        <Text style={styles.subtitle}>Imperium Faktur G</Text>
      </View>
      <PeriodSelector
        fullWidth
        year={periodYear}
        month={periodMonth}
        onChange={onPeriodChange}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  header: { gap: 10, marginBottom: 4 },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  subtitle: {
    color: colors.textMuted,
    fontSize: 14,
    fontStyle: 'italic',
    fontWeight: '400',
    letterSpacing: 0.3,
    flexShrink: 1,
  },
});
