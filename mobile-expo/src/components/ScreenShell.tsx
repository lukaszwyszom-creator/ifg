import { ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { colors } from '@/theme/colors';

type Props = {
  title?: string;
  subtitle?: string;
  showBack?: boolean;
  scroll?: boolean;
  children: ReactNode;
  footer?: ReactNode;
};

export function ScreenShell({ title, subtitle, showBack, scroll = true, children, footer }: Props) {
  const router = useRouter();
  const body = scroll ? (
    <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
      {children}
    </ScrollView>
  ) : (
    <View style={styles.body}>{children}</View>
  );

  return (
    <SafeAreaView style={styles.safe} edges={['top', 'left', 'right']}>
      {(title || showBack) && (
        <View style={styles.header}>
          {showBack ? (
            <Pressable onPress={() => router.back()} style={styles.backBtn} hitSlop={12}>
              <Text style={styles.backText}>← Wróć</Text>
            </Pressable>
          ) : (
            <View style={styles.backPlaceholder} />
          )}
          <View style={styles.headerTitles}>
            {title ? <Text style={styles.title}>{title}</Text> : null}
            {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
          </View>
        </View>
      )}
      {body}
      {footer}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg, maxWidth: 390, alignSelf: 'center', width: '100%' },
  header: { paddingHorizontal: 16, paddingTop: 4, paddingBottom: 8, gap: 4 },
  backBtn: { alignSelf: 'flex-start', marginBottom: 4 },
  backText: { color: colors.gold, fontSize: 15, fontWeight: '600' },
  backPlaceholder: { height: 0 },
  headerTitles: { gap: 2 },
  title: { color: colors.text, fontSize: 22, fontWeight: '700' },
  subtitle: { color: colors.textMuted, fontSize: 13 },
  scroll: { paddingHorizontal: 16, paddingBottom: 32, gap: 12 },
  body: { flex: 1, paddingHorizontal: 16 },
});
