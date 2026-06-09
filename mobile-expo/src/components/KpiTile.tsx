import { Pressable, StyleSheet, Text, View } from 'react-native';
import { colors } from '@/theme/colors';

type Props = {
  label: string;
  labelLine2?: string;
  primary: string;
  secondary?: string;
  accent?: string;
  overdueAmount?: string;
  danger?: boolean;
  onPress?: () => void;
  large?: boolean;
  compactLabel?: boolean;
  compactAccent?: boolean;
  heroPrimary?: boolean;
};

export function KpiTile({
  label,
  labelLine2,
  primary,
  secondary,
  accent,
  overdueAmount,
  danger,
  onPress,
  large,
  compactLabel,
  compactAccent,
  heroPrimary,
}: Props) {
  const labelStyle = [styles.label, large && styles.labelLg, compactLabel && styles.labelCompact];
  const primaryStyle = [
    styles.primary,
    large && !heroPrimary && styles.primaryLg,
    heroPrimary && styles.primaryHero,
    danger && styles.danger,
  ];

  return (
    <Pressable
      style={({ pressed }) => [styles.tile, pressed && styles.pressed]}
      onPress={onPress}
      disabled={!onPress}
    >
      {labelLine2 ? (
        <View style={styles.splitLabel}>
          <Text style={labelStyle} numberOfLines={1}>{label}</Text>
          <Text style={labelStyle} numberOfLines={1}>{labelLine2}</Text>
        </View>
      ) : (
        <Text style={labelStyle}>{label}</Text>
      )}
      <Text style={primaryStyle}>{primary}</Text>
      {secondary ? <Text style={[styles.secondary, large && styles.secondaryLg]}>{secondary}</Text> : null}
      {overdueAmount ? (
        <View style={styles.overdueBlock}>
          <Text style={[styles.overdueLabel, large && styles.overdueLabelLg]}>Po terminie</Text>
          <Text style={[styles.overdueAmount, large && styles.overdueAmountLg]}>{overdueAmount}</Text>
        </View>
      ) : null}
      {accent ? (
        <Text style={[styles.accent, large && styles.accentLg, compactAccent && styles.accentCompact]}>
          {accent}
        </Text>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  tile: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
    flex: 1,
    minWidth: '47%',
    gap: 4,
  },
  pressed: { opacity: 0.85, borderColor: colors.goldDim },
  splitLabel: { gap: 1 },
  label: { color: colors.textMuted, fontSize: 12, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5 },
  primary: { color: colors.text, fontSize: 18, fontWeight: '700' },
  secondary: { color: colors.textMuted, fontSize: 12 },
  accent: { color: colors.gold, fontSize: 12, fontWeight: '600', marginTop: 2 },
  danger: { color: colors.danger },
  labelLg: { fontSize: 17, fontWeight: '700' },
  labelCompact: { fontSize: 14, fontWeight: '700' },
  primaryLg: { fontSize: 25 },
  primaryHero: { fontSize: 20, fontWeight: '700' },
  secondaryLg: { fontSize: 18 },
  accentLg: { fontSize: 18 },
  accentCompact: { fontSize: 16 },
  overdueBlock: { marginTop: 10, gap: 2 },
  overdueLabel: { color: colors.gold, fontSize: 12, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5 },
  overdueLabelLg: { fontSize: 14 },
  overdueAmount: { color: colors.gold, fontSize: 18, fontWeight: '700' },
  overdueAmountLg: { fontSize: 22 },
});
