import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { clearSession, loginWithCredentials, setSessionToken } from '@/api/auth';

type AuthContextValue = {
  isAuthenticated: boolean;
  isLoading: boolean;
  authError: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  clearAuthError: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => {
    const token = process.env.EXPO_PUBLIC_API_TOKEN;
    if (token) {
      setSessionToken(token);
      setIsAuthenticated(true);
    }
    setIsLoading(false);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    setAuthError(null);
    try {
      await loginWithCredentials(username, password);
      setIsAuthenticated(true);
      setAuthError(null);
    } catch (err) {
      clearSession();
      setIsAuthenticated(false);
      setAuthError(err instanceof Error ? err.message : 'Nie udało się zalogować');
      throw err;
    }
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setIsAuthenticated(false);
    setAuthError(null);
  }, []);

  const clearAuthError = useCallback(() => {
    setAuthError(null);
  }, []);

  const value = useMemo(
    () => ({ isAuthenticated, isLoading, authError, login, logout, clearAuthError }),
    [isAuthenticated, isLoading, authError, login, logout, clearAuthError],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return ctx;
}
