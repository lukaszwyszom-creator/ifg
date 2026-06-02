import Constants from 'expo-constants';

/** Bazowy URL API IFG — domyślnie z app.json extra; nadpisz przez EXPO_PUBLIC_API_BASE_URL. */
export function getApiBaseUrl(): string {
  const fromEnv = process.env.EXPO_PUBLIC_API_BASE_URL;
  if (fromEnv) {
    return fromEnv.replace(/\/$/, '');
  }
  const extra = Constants.expoConfig?.extra as { apiBaseUrl?: string } | undefined;
  return (extra?.apiBaseUrl ?? 'http://127.0.0.1:8000').replace(/\/$/, '');
}

export const API_V1_PREFIX = '/api/v1';
