import { useState } from 'react';
import { invoicesApi } from '../../api/invoices';
import { transmissionsApi } from '../../api/transmissions';
import styles from './InvoiceActions.module.css';

/**
 * @param {object}   invoice      - pełny obiekt faktury
 * @param {Function} onRefresh    - callback po akcji
 */
const UNSENT_STATUSES = new Set([
  '',
  'draft',
  'ready_for_submission',
  'ready',
  'gotowa',
  'szkic',
]);

const PROCESSING_STATUSES = new Set([
  'sending',
  'in_progress',
  'processing',
  'queued',
  'submitted',
  'waiting_status',
  'failed_temporary',
]);

const REJECTED_STATUSES = new Set([
  'rejected',
  'failed_permanent',
  'failed_retryable',
]);

const UPO_STATUSES = new Set([
  'accepted',
  'upo_received',
  'delivered',
  'success',
]);

function resolveKsefState(status) {
  const normalized = (status ?? '').toString().trim().toLowerCase();

  if (UNSENT_STATUSES.has(normalized)) {
    return { kind: 'send', label: 'Wyślij' };
  }
  if (PROCESSING_STATUSES.has(normalized)) {
    return { kind: 'processing', label: 'W przetwarzaniu' };
  }
  if (REJECTED_STATUSES.has(normalized)) {
    return { kind: 'rejected', label: 'Odrzucona' };
  }
  if (UPO_STATUSES.has(normalized)) {
    return { kind: 'upo', label: 'Odebrano UPO' };
  }

  return { kind: 'send', label: 'Wyślij' };
}

export default function InvoiceActions({ invoice, onRefresh }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const ksefState = resolveKsefState(invoice.status);

  const submitToKsef = async (e) => {
    e.stopPropagation();
    setBusy(true);
    setMsg('');

    try {
      if ((invoice.status ?? '').toString().trim().toLowerCase() === 'draft') {
        await invoicesApi.markReady(invoice.id);
      }

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
      setBusy(false);
    }
  };

  return (
    <div className={styles.wrap}>
      {ksefState.kind === 'send' ? (
        <button
          className={`btn btn-sm ${styles.sendBtn}`}
          disabled={busy}
          onClick={submitToKsef}
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
