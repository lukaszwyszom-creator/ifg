import { useState } from 'react';
import { transmissionsApi } from '../../api/transmissions';
import { useAppStore } from '../../store/useAppStore';
import { resolveKsefState } from './invoiceOpenMode';
import styles from './InvoiceActions.module.css';

const REFRESH_EVENT = 'ksef:status-refresh';

/**
 * @param {object}   invoice      - pełny obiekt faktury
 * @param {Function} onRefresh    - callback po akcji
 */
export default function InvoiceActions({ invoice, onRefresh }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const ksefState = resolveKsefState(invoice.status);
  const ksefConnectionStatus = useAppStore((s) => s.ksefConnection.ui_status);
  const sendBlocked = busy || ksefConnectionStatus !== 'CONNECTED';
  const sendBlockedTitle = sendBlocked && !busy
    ? 'Aby wysłać fakturę, połącz się z KSeF'
    : undefined;

  const submitToKsef = async (e) => {
    e.stopPropagation();
    setBusy(true);
    setMsg('');

    try {
      await transmissionsApi.submit(invoice.id);
      onRefresh?.();
    } catch (err) {
      setMsg(
        err.response?.data?.error?.message ??
        err.response?.data?.detail ??
        err.response?.data?.error?.code ??
        'Błąd wysyłki do KSeF',
      );
    } finally {
      window.dispatchEvent(new CustomEvent(REFRESH_EVENT));
      setBusy(false);
    }
  };

  return (
    <div className={styles.wrap}>
      {ksefState.kind === 'send' ? (
        <button
          className={`btn btn-sm ${styles.sendBtn}`}
          disabled={sendBlocked}
          onClick={submitToKsef}
          title={sendBlockedTitle}
        >
          {busy ? <span className="spinner" style={{ width: 12, height: 12 }} /> : ksefState.label}
        </button>
      ) : (
        <span className={`${styles.ksefBadge} ${styles[`state_${ksefState.kind}`]}`}>
          {ksefState.label}
        </span>
      )}
      {msg && (
        <span className={styles.err} title={msg}>
          ⚠ {msg.length > 36 ? `${msg.slice(0, 36)}…` : msg}
        </span>
      )}
    </div>
  );
}
