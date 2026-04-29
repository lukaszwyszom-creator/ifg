import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth';
import { useAuthStore } from '../store/useAuthStore';
import styles from './LoginPage.module.css';
import logo from '../assets/logo-ifg.png';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const setAuth = useAuthStore((s) => s.setAuth);
  const navigate = useNavigate();

  const mapBackendMessage = (message) => {
    if (!message) return '';
    const normalized = String(message).trim().toLowerCase();
    if (normalized === 'nieprawidlowy login lub haslo.') return 'Nieprawidłowy login lub hasło.';
    if (normalized === 'konto uzytkownika jest nieaktywne.') return 'Konto użytkownika jest nieaktywne.';
    if (normalized === 'nieprawidlowy token dostepu.') return 'Nieprawidłowy token dostępu.';
    if (normalized === 'uzytkownik nie istnieje lub jest nieaktywny.') {
      return 'Użytkownik nie istnieje lub jest nieaktywny.';
    }
    return message;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await authApi.login(username, password);
      setAuth(data.access_token, { username });
      navigate('/invoices', { replace: true });
    } catch (err) {
      const backendMessage = err?.response?.data?.error?.message;
      if (backendMessage) {
        setError(mapBackendMessage(backendMessage));
      } else if (err?.response?.status === 401) {
        setError('Nieprawidłowy login lub hasło.');
      } else {
        setError('Nie udało się zalogować. Sprawdź połączenie i spróbuj ponownie.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.box}>
        <div className={styles.header}>
          <img src={logo} alt="IFG" className={styles.logo} />
          <h1 className={styles.title}>Imperium Faktur G</h1>
          <p className={styles.sub}>Zaloguj się, aby kontynuować</p>
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        <form className={styles.form} onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Login</label>
            <input
              className="input"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">Hasło</label>
            <div className={styles.passwordFieldWrap}>
              <input
                className={`input ${styles.passwordInput}`}
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                className={styles.passwordEyeButton}
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? 'Ukryj hasło' : 'Pokaż hasło'}
                title={showPassword ? 'Ukryj hasło' : 'Pokaż hasło'}
              >
                {showPassword ? (
                  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                    <path d="M3 3l18 18" />
                    <path d="M10.58 10.58a2 2 0 0 0 2.83 2.83" />
                    <path d="M9.36 5.37A10.94 10.94 0 0 1 12 5c5.05 0 9.27 3.11 10 7-0.3 1.59-1.26 3.04-2.68 4.2" />
                    <path d="M6.26 6.26C4.12 7.51 2.56 9.59 2 12c0.73 3.89 4.95 7 10 7a10.9 10.9 0 0 0 3.74-.66" />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                    <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </div>
          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: '100%', justifyContent: 'center' }}
            disabled={loading}
          >
            {loading ? <span className="spinner" /> : 'Zaloguj'}
          </button>
        </form>
      </div>
    </div>
  );
}
