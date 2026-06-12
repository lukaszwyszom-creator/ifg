import { useState, useEffect, useCallback } from 'react';
import { ksefApi, formatPurchaseSyncError, logKsefUiTriggerPurchaseSync } from '../../api/ksef';
import { settingsApi } from '../../api/settings';
import { useAppStore } from '../../store/useAppStore';
import styles from './KSeFSessionBar.module.css';

const REFRESH_EVENT = 'ksef:status-refresh';

/**
 * Pasek statusu sesji KSeF wyświetlany w AdvancedDashboard.
 * Pozwala otworzyć, sprawdzić i zamknąć sesję KSeF dla podanego NIP.
 */
export default function KSeFSessionBar() {
  const storedNip = useAppStore((s) => s.sellerNip);
  const setSellerNip = useAppStore((s) => s.setSellerNip);
  const refreshAllInvoicePools = useAppStore((s) => s.refreshAllInvoicePools);

  const [nip, setNip] = useState(storedNip);
  const [session, setSession] = useState(null);  // KSeFSessionResponse | null
  const [busy, setBusy] = useState(false);
  const [checkLoading, setCheckLoading] = useState(false);
  const [syncBusy, setSyncBusy] = useState(false);
  const [syncRunning, setSyncRunning] = useState(false);
  const [syncStatus, setSyncStatus] = useState(null);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const clearMsgs = () => { setError(''); setSuccessMsg(''); };

  const checkSession = useCallback(async (nipToCheck, { silent = false } = {}) => {
    if (!nipToCheck || nipToCheck.length !== 10) return;
    if (!silent) {
      setCheckLoading(true);
      clearMsgs();
    }
    try {
      const s = await ksefApi.getActiveSession(nipToCheck);
      setSession(s);
    } catch (err) {
      if (err.response?.status === 404) {
        setSession(null); // brak aktywnej — to normalny stan
      } else if (!silent) {
        setError('Błąd sprawdzania sesji KSeF');
      }
    } finally {
      if (!silent) {
        setCheckLoading(false);
      }
    }
  }, []);

  // Przy zmianie NIP z store sprawdź automatycznie
  useEffect(() => {
    if (storedNip?.length === 10) {
      setNip(storedNip);
      checkSession(storedNip);
    }
  }, [storedNip, checkSession]);

  const loadSyncStatus = useCallback(async () => {
    try {
      const status = await ksefApi.getPurchaseSyncStatus();
      setSyncStatus(status);
    } catch {
      // Endpoint może być chwilowo niedostępny podczas rolloutu.
      setSyncStatus(null);
    }
  }, []);

  useEffect(() => {
    loadSyncStatus();
  }, [loadSyncStatus]);

  useEffect(() => {
    if (!nip || nip.length !== 10) return undefined;

    const refreshSessionState = () => {
      checkSession(nip, { silent: true });
      loadSyncStatus();
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        refreshSessionState();
      }
    };

    const pollId = window.setInterval(refreshSessionState, 30000);
    window.addEventListener(REFRESH_EVENT, refreshSessionState);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      window.clearInterval(pollId);
      window.removeEventListener(REFRESH_EVENT, refreshSessionState);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [nip, checkSession, loadSyncStatus]);

  // Pobierz NIP z backendu jeśli store jest pusty
  useEffect(() => {
    if (storedNip) return;
    let cancelled = false;
    settingsApi.get()
      .then((s) => {
        if (!cancelled && s.seller_nip?.length === 10) {
          setSellerNip(s.seller_nip);
        }
      })
      .catch(() => { /* ignoruj — użytkownik wpisze ręcznie */ });
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleNipChange = (val) => {
    setNip(val.replace(/\D/g, '').slice(0, 10));
  };

  const handleCheck = () => {
    setSellerNip(nip);
    checkSession(nip);
  };

  const handleOpen = async () => {
    clearMsgs();
    setBusy(true);
    try {
      const s = await ksefApi.openSession(nip);
      setSession(s);
      setSellerNip(nip);
      setSuccessMsg('Sesja KSeF otwarta pomyślnie');
      ksefApi.markStatusMutation();
      window.dispatchEvent(new CustomEvent(REFRESH_EVENT));
    } catch (err) {
      if (err.response?.status === 409) {
        // Sesja już istnieje — załaduj ją i daj użytkownikowi możliwość zamknięcia
        setSellerNip(nip);
        await checkSession(nip);
        // Jeśli checkSession nie znalazło sesji (edge case) — ustaw syntetyczną
        setSession((prev) => prev ?? { nip, status: 'active', session_reference: null });
        // checkSession woła clearMsgs() — ustawiamy error po nim
        setError('Sesja KSeF jest już aktywna. Możesz ją zamknąć lub pobrać faktury.');
      } else {
        const msg =
          err.response?.data?.error?.message ??
          err.response?.data?.detail ??
          'Błąd otwierania sesji';
        setError(msg);
      }
    } finally {
      setBusy(false);
    }
  };

  const handleClose = async () => {
    if (!session) return;
    clearMsgs();
    setBusy(true);
    try {
      await ksefApi.closeSession(session.nip);
      setSession(null);
      setSuccessMsg('Sesja KSeF zamknięta');
      ksefApi.markStatusMutation();
      window.dispatchEvent(new CustomEvent(REFRESH_EVENT));
    } catch (err) {
      const msg =
        err.response?.data?.error?.message ??
        err.response?.data?.detail ??
        'Błąd zamykania sesji';
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const handleSyncPurchase = async () => {
    if (!session) return;
    clearMsgs();
    setSyncBusy(true);
    setSuccessMsg('Uruchamiam async sync…');
    logKsefUiTriggerPurchaseSync(session.nip, 'KSeFSessionBar');
    try {
      // Ścieżka sync: ksefApi.runPurchaseSync → POST /ksef-sessions/sync-purchase (async job)
      const { counts } = await ksefApi.runPurchaseSync(session.nip, {
        onStarted: () => {
          setSyncBusy(false);
          setSyncRunning(true);
          setSuccessMsg('Synchronizacja uruchomiona — trwa pobieranie faktur z KSeF…');
        },
        onProgress: (jobStatus) => {
          if (jobStatus.status === 'pending' || jobStatus.status === 'processing') {
            setSuccessMsg('Synchronizacja trwa — pobieranie faktur z KSeF…');
          }
        },
      });
      setSuccessMsg(
        `Pobrano ${counts.saved} nowych faktur` +
        ` (od KSeF: ${counts.received}, duplikaty: ${counts.skippedExisting}, błędy parsowania: ${counts.skippedParse})`,
      );
      await refreshAllInvoicePools();
      window.dispatchEvent(new CustomEvent('ksef:invoices-synced'));
      await loadSyncStatus();
    } catch (err) {
      if (err.timedOut) {
        setSuccessMsg(formatPurchaseSyncError(err, err.syncEndpoint));
        await loadSyncStatus();
        return;
      }
      setError(formatPurchaseSyncError(err, err.syncEndpoint));
    } finally {
      setSyncBusy(false);
      setSyncRunning(false);
    }
  };

  const isActive = session?.status === 'active';
  const nipValid = nip.length === 10;
  const syncStatusLabel = syncStatus?.status || 'idle';
  const syncLastSuccess = syncStatus?.last_success_at
    ? new Date(syncStatus.last_success_at).toLocaleString('pl-PL')
    : 'brak';
  const syncLastError = syncStatus?.last_error || null;

  return (
    <div className={styles.bar}>
      <div className={styles.left}>
        <span className={styles.label}>Sesja KSeF</span>

        {isActive ? (
          <div className={styles.statusStack}>
            <span className={styles.sessionInfo}>
              <span className={styles.dot} />
              Aktywna · NIP {session.nip}
              {session.session_reference && (
                <span className={styles.ref} title={session.session_reference}>
                  · ref: {session.session_reference.slice(0, 12)}…
                </span>
              )}
            </span>
            <span className={styles.syncMeta}>
              Sync zakupów: {syncStatusLabel} · Ostatni sukces: {syncLastSuccess}
            </span>
            {syncLastError && (
              <span className={styles.syncError} title={syncLastError}>
                Ostatni błąd: {syncLastError}
              </span>
            )}
          </div>
        ) : (
          <span className={styles.noSession}>Brak aktywnej sesji</span>
        )}
      </div>

      <div className={styles.right}>
        {!isActive && (
          <>
            <input
              className={`input ${styles.nipInput}`}
              type="text"
              placeholder="NIP sprzedawcy"
              maxLength={10}
              value={nip}
              onChange={(e) => handleNipChange(e.target.value)}
            />
            <button
              className="btn btn-ghost btn-sm"
              disabled={!nipValid || checkLoading}
              onClick={handleCheck}
            >
              {checkLoading ? <span className="spinner" style={{ width: 12, height: 12 }} /> : 'Sprawdź'}
            </button>
            <button
              className="btn btn-primary btn-sm"
              disabled={!nipValid || busy}
              onClick={handleOpen}
            >
              {busy ? <span className="spinner" style={{ width: 12, height: 12 }} /> : 'Otwórz sesję'}
            </button>
          </>
        )}

        {isActive && (
          <>
            <button
              className="btn btn-secondary btn-sm"
              disabled={syncBusy || syncRunning}
              onClick={handleSyncPurchase}
              title="Odśwież lokalny pool faktur zakupowych z KSeF"
            >
              {syncBusy
                ? <span className="spinner" style={{ width: 12, height: 12 }} />
                : syncRunning
                  ? 'Sync trwa…'
                  : 'Odśwież KSeF'}
            </button>
            <button
              className="btn btn-danger btn-sm"
              disabled={busy}
              onClick={handleClose}
            >
              {busy ? <span className="spinner" style={{ width: 12, height: 12 }} /> : 'Zamknij sesję'}
            </button>
          </>
        )}
      </div>

      {error      && <div className={styles.alertRow}><div className="alert alert-error">{error}</div></div>}
      {successMsg && <div className={styles.alertRow}><div className="alert alert-success">{successMsg}</div></div>}
    </div>
  );
}
