import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { useState } from 'react';
import { Logo } from '@/components/Logo';
import { ScreenShell } from '@/components/ScreenShell';
import { useAuth } from '@/auth/AuthContext';
import { colors } from '@/theme/colors';

export default function LoginScreen() {
  const { login, authError, isLoading } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const onSubmit = async () => {
    if (!username.trim() || !password || submitting) {
      setLocalError('Nieprawidłowy login lub hasło');
      return;
    }
    setLocalError(null);
    setSubmitting(true);
    try {
      await login(username.trim(), password);
    } catch {
      // authError ustawiane w kontekście — użytkownik zostaje na ekranie logowania
    } finally {
      setSubmitting(false);
    }
  };

  const displayError = authError ?? localError;

  if (isLoading) {
    return (
      <ScreenShell scroll={false}>
        <View style={styles.center}>
          <ActivityIndicator color={colors.gold} size="large" />
        </View>
      </ScreenShell>
    );
  }

  return (
    <ScreenShell scroll={false}>
      <View style={styles.container}>
        <View style={styles.brandRow}>
          <Logo />
          <Text style={styles.subtitle}>Imperium Faktur G</Text>
        </View>

        <View style={styles.form}>
          <Text style={styles.label}>Login</Text>
          <TextInput
            style={styles.input}
            value={username}
            onChangeText={setUsername}
            autoCapitalize="none"
            autoCorrect={false}
            placeholderTextColor={colors.textDim}
            placeholder="admin"
          />

          <Text style={styles.label}>Hasło</Text>
          <TextInput
            style={styles.input}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            placeholderTextColor={colors.textDim}
            placeholder="••••••••"
          />

          {displayError ? <Text style={styles.error}>{displayError}</Text> : null}

          <Pressable
            style={[styles.button, submitting && styles.buttonDisabled]}
            onPress={onSubmit}
            disabled={submitting}
          >
            <Text style={styles.buttonText}>{submitting ? 'Logowanie…' : 'Zaloguj'}</Text>
          </Pressable>
        </View>
      </View>
    </ScreenShell>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  container: { flex: 1, justifyContent: 'center', gap: 32, paddingVertical: 24 },
  brandRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10 },
  subtitle: {
    color: colors.textMuted,
    fontSize: 14,
    fontStyle: 'italic',
    letterSpacing: 0.3,
  },
  form: { gap: 10 },
  label: { color: colors.textMuted, fontSize: 14, fontWeight: '600' },
  input: {
    backgroundColor: colors.surface,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.text,
    fontSize: 16,
    paddingHorizontal: 12,
    paddingVertical: 12,
  },
  error: { color: colors.danger, fontSize: 15, marginTop: 4 },
  button: {
    backgroundColor: colors.gold,
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 8,
  },
  buttonDisabled: { opacity: 0.7 },
  buttonText: { color: colors.bg, fontSize: 16, fontWeight: '800' },
});
