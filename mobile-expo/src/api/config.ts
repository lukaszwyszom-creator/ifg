import Constants from 'expo-constants';

/**
 * Bazowy URL API IFG (bez `/api/v1`).
 *
 * Priorytet:
 * 1. EXPO_PUBLIC_API_BASE_URL
 * 2. app.json → expo.extra.apiBaseUrl
 * 3. http://127.0.0.1:8000
 *
 * Przykłady:
 * - Mac mini LAN/dev:  http://192.168.1.50:8000
 * - DS723+ production: https://ifg.ikonastudio.pl
 */
export function getApiBaseUrl(): string {
  const fromEnv = process.env.EXPO_PUBLIC_API_BASE_URL;
  if (fromEnv) {
    return fromEnv.replace(/\/$/, '');
  }
  const extra = Constants.expoConfig?.extra as { apiBaseUrl?: string } | undefined;
  return (extra?.apiBaseUrl ?? 'http://127.0.0.1:8000').replace(/\/$/, '');
}

export const API_V1_PREFIX = '/api/v1';
