import { apiClient } from './client';
import { AuthError } from './auth-error';

type TokenResponse = {
  access_token: string;
};

export { AuthError } from './auth-error';

export function hasSession(): boolean {
  return apiClient.getToken() !== null;
}

export function setSessionToken(token: string | null): void {
  apiClient.setToken(token);
}

const INVALID_CREDENTIALS_MSG = 'Nieprawidłowy login lub hasło';
const LOGIN_FAILED_MSG = 'Nie udało się zalogować. Sprawdź połączenie z serwerem.';

export async function loginWithCredentials(username: string, password: string): Promise<void> {
  if (!username.trim() || !password) {
    throw new AuthError(INVALID_CREDENTIALS_MSG);
  }

  let res: TokenResponse | null = null;
  try {
    res = await apiClient.post<TokenResponse>('/auth/login', { username, password });
  } catch (err) {
    if (err instanceof AuthError) {
      throw new AuthError(INVALID_CREDENTIALS_MSG);
    }
    if (err instanceof Error) {
      const msg = err.message.toLowerCase();
      if (msg.includes('cloudflare') || msg.includes('html zamiast json')) {
        throw new AuthError(err.message);
      }
      if (msg.includes('login') || msg.includes('hasło') || msg.includes('haslo') || msg.includes('401')) {
        throw new AuthError(INVALID_CREDENTIALS_MSG);
      }
      throw new AuthError(LOGIN_FAILED_MSG);
    }
    throw new AuthError(LOGIN_FAILED_MSG);
  }

  const token = res?.access_token;
  if (typeof token !== 'string' || !token.trim()) {
    throw new AuthError(INVALID_CREDENTIALS_MSG);
  }

  setSessionToken(token.trim());
}

export function clearSession(): void {
  setSessionToken(null);
}

export function ensureApiAuth(): void {
  if (!hasSession()) {
    throw new AuthError('Brak uwierzytelnienia');
  }
}

export function isAuthFailure(err: unknown): boolean {
  if (err instanceof AuthError) {
    return true;
  }
  if (err instanceof Error) {
    const msg = err.message.toLowerCase();
    return (
      msg.includes('login') ||
      msg.includes('hasło') ||
      msg.includes('haslo') ||
      msg.includes('uwierzytelnienia') ||
      msg.includes('unauthorized')
    );
  }
  return false;
}
