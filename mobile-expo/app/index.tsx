import { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { getApiBaseUrl } from '@/api/config';

type HealthResponse = {
  status: string;
  app_name?: string;
  version?: string;
};

export default function HomeScreen() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch(`${getApiBaseUrl()}/health`);
        const data = (await response.json()) as HealthResponse;
        if (!cancelled) {
          setHealth(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Błąd połączenia');
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>IFG Mobile</Text>
      <Text style={styles.subtitle}>Szkielet Expo — branch feature/mobile-expo</Text>
      <Text style={styles.api}>API: {getApiBaseUrl()}</Text>
      {error ? (
        <Text style={styles.error}>{error}</Text>
      ) : health ? (
        <Text style={styles.ok}>
          {health.app_name ?? 'IFG'} — {health.status} ({health.version ?? '?'})
        </Text>
      ) : (
        <ActivityIndicator />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 24,
    justifyContent: 'center',
    gap: 12,
    backgroundColor: '#f8fafc',
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
  },
  subtitle: {
    color: '#64748b',
  },
  api: {
    fontFamily: 'Menlo',
    fontSize: 12,
    color: '#334155',
  },
  ok: {
    color: '#15803d',
  },
  error: {
    color: '#b91c1c',
  },
});
