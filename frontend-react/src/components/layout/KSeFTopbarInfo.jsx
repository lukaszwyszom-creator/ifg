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
    if (!sellerNip || !isConnected || syncBusy) return;
    setSyncBusy(true);
    setFlashMsg('');
    try {
      try {
        const payload = await ksefApi.syncPurchasesNow(false, sellerNip);
        const r = payload?.counts || {};
        const saved = Number.isFinite(Number(r.saved)) ? Number(r.saved) : 0;
        setFlashType('success');
        setFlashMsg(`+${saved}`);
      } catch (syncErr) {
        if (syncErr.response?.status === 404) {
          // Fallback: starszy async job endpoint
          const dateTo = new Date();
          const dateFrom = new Date();
          dateFrom.setDate(dateFrom.getDate() - 30);
          const fmt = (d) => {
            const y = d.getFullYear();
            const m = String(d.getMonth() + 1).padStart(2, '0');
            const day = String(d.getDate()).padStart(2, '0');
            return `${y}-${m}-${day}`;
          };
          const { job_id } = await ksefApi.syncPurchaseInvoices(sellerNip, fmt(dateFrom), fmt(dateTo));
          const MAX_POLLS = 20;
          let done = false;
          for (let i = 0; i < MAX_POLLS && !done; i++) {
            await new Promise((res) => setTimeout(res, 3000));
            const jobStatus = await ksefApi.getSyncPurchaseJobStatus(job_id);
            if (jobStatus.status === 'done') {
              done = true;
              const r = jobStatus.result || {};
              const saved = Number.isFinite(Number(r.saved)) ? Number(r.saved) : 0;
              setFlashType('success');
              setFlashMsg(`+${saved}`);
            } else if (jobStatus.status === 'failed') {
              throw new Error(jobStatus.error || 'Błąd synchronizacji');
            }
          }
          if (!done) {
            setFlashType('success');
            setFlashMsg('w tle…');
          }
        } else {
          throw syncErr;
        }
      }
      await refreshAllInvoicePools();
      window.dispatchEvent(new CustomEvent('ksef:invoices-synced'));
      await loadSyncStatus();
    } catch (err) {
      console.error('Błąd synchronizacji KSeF:', err);
      setFlashType('error');
      setFlashMsg('Błąd');
    } finally {
      setSyncBusy(false);
      setTimeout(() => setFlashMsg(''), 5000);
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
        disabled={syncBusy}
        title="Odśwież faktury zakupowe z KSeF"
      >
        {syncBusy
          ? <span className="spinner" style={{ width: 10, height: 10 }} />
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
