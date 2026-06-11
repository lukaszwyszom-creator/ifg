import { useState, useEffect, useCallback } from 'react';
import { ksefApi } from '../../api/ksef';
import { useAppStore } from '../../store/useAppStore';
import styles from './KSeFTopbarInfo.module.css';

const REFRESH_EVENT = 'ksef:status-refresh';

/**
 * Kompaktowe info o sesji KSeF + przycisk "Odśwież KSeF" w topbarze.
 * Renderuje się tylko gdy ui_status === 'CONNECTED'.
 */
export default function KSeFTopbarInfo() {
  const sellerNip = useAppStore((s) => s.sellerNip);
  const ksefStatus = useAppStore((s) => s.ksefConnection);
  const refreshAllInvoicePools = useAppStore((s) => s.refreshAllInvoicePools);

  const [syncStatus, setSyncStatus] = useState(null);
  const [sessionRef, setSessionRef] = useState(null);
  const [syncBusy, setSyncBusy] = useState(false);
  const [syncRunning, setSyncRunning] = useState(false);
  const [flashMsg, setFlashMsg] = useState('');
  const [flashType, setFlashType] = useState('success'); // 'success' | 'error'

  const isConnected = ksefStatus.ui_status === 'CONNECTED';

  const loadSyncStatus = useCallback(async () => {
    try {
      const status = await ksefApi.getPurchaseSyncStatus();
      setSyncStatus(status);
    } catch {
      setSyncStatus(null);
    }
  }, []);

  const loadSessionRef = useCallback(async () => {
    if (!sellerNip || sellerNip.length !== 10) return;
    try {
      const s = await ksefApi.getActiveSession(sellerNip);
      setSessionRef(s?.session_reference ?? null);
    } catch {
      setSessionRef(null);
    }
  }, [sellerNip]);

  useEffect(() => {
    if (!isConnected) {
      setSessionRef(null);
      return undefined;
    }

    loadSyncStatus();
    loadSessionRef();

    const refreshAll = () => {
      loadSyncStatus();
      loadSessionRef();
    };

    const handleVisibility = () => {
      if (document.visibilityState === 'visible') refreshAll();
    };

    const pollId = window.setInterval(refreshAll, 30000);
    window.addEventListener(REFRESH_EVENT, refreshAll);
    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      window.clearInterval(pollId);
      window.removeEventListener(REFRESH_EVENT, refreshAll);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [isConnected, loadSyncStatus, loadSessionRef]);

  const handleSyncPurchase = async () => {
    if (!sellerNip || !isConnected || syncBusy || syncRunning) return;
    setSyncBusy(true);
    setFlashMsg('');
    try {
      // Ścieżka sync: ksefApi.runPurchaseSync → POST /ksef-sessions/sync-purchase (async job)
      const { counts } = await ksefApi.runPurchaseSync(sellerNip, {
        onStarted: () => {
          setSyncBusy(false);
          setSyncRunning(true);
          setFlashType('success');
          setFlashMsg('Synchronizacja uruchomiona…');
        },
        onProgress: (jobStatus) => {
          if (jobStatus.status === 'pending' || jobStatus.status === 'processing') {
            setFlashType('success');
            setFlashMsg('Synchronizacja trwa…');
          }
        },
      });
      setFlashType('success');
      setFlashMsg(`+${counts.saved}`);
      await refreshAllInvoicePools();
      window.dispatchEvent(new CustomEvent('ksef:invoices-synced'));
      await loadSyncStatus();
    } catch (err) {
      console.error('Błąd synchronizacji KSeF:', err);
      setFlashType('error');
      if (err.timedOut) {
        setFlashMsg('Trwa zbyt długo — sprawdź status');
      } else {
        setFlashMsg('Błąd');
      }
    } finally {
      setSyncBusy(false);
      setSyncRunning(false);
      setTimeout(() => setFlashMsg(''), 8000);
    }
  };

  if (!isConnected) return null;

  const syncLastSuccess = syncStatus?.last_success_at
    ? new Date(syncStatus.last_success_at).toLocaleString('pl-PL', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
    : 'brak';

  return (
    <div className={styles.wrap}>
      {sessionRef && (
        <>
          <span className={styles.sep}>|</span>
          <span className={`${styles.metaItem} ${styles.refItem}`} title={sessionRef}>
            Ref: {sessionRef.slice(0, 12)}&hellip;
          </span>
        </>
      )}
      <span className={styles.sep}>|</span>
      <span className={styles.metaItem} title={`Ostatnia synchronizacja zakupów: ${syncLastSuccess}`}>
        Sync: {syncLastSuccess}
      </span>
      <span className={styles.sep}>|</span>
      <button
        type="button"
        className={styles.refreshBtn}
        onClick={handleSyncPurchase}
        disabled={syncBusy || syncRunning}
        title="Odśwież faktury zakupowe z KSeF"
      >
        {syncBusy
          ? <span className="spinner" style={{ width: 10, height: 10 }} />
          : syncRunning
            ? 'Sync…'
            : 'Odśwież KSeF'}
      </button>
      {flashMsg && (
        <span className={`${styles.flashMsg} ${flashType === 'error' ? styles.flashError : styles.flashSuccess}`}>
          {flashMsg}
        </span>
      )}
    </div>
  );
}
