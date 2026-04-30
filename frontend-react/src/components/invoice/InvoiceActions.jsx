import { useState } from 'react';
import { transmissionsApi } from '../../api/transmissions';
import { useAppStore } from '../../store/useAppStore';
import { resolveKsefState } from './invoiceOpenMode';
import styles from './InvoiceActions.module.css';

const REFRESH_EVENT = 'ksef:status-refresh';

/**
 * Jednoelementowy kafelek KSeF — jednocześnie wskaźnik statusu i trigger akcji.
 *
 * @param {object}   invoice      - pełny obiekt faktury
 * @param {Function} onRefresh    - callback po akcji
 */
export default function InvoiceActions({ invoice, onRefresh }) {
  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const ksefState = resolveKsefState(invoice.status, invoice);
  const ksefConnectionStatus = useAppStore((s) => s.ksefConnection.ui_status);

  const submitToKsef = async (e) => {
    e.stopPropagation();
    setBusy(true);
    setErrorMsg('');
    try {
      await transmissionsApi.submit(invoice.id);
      onRefresh?.();
    } catch (err) {
      setErrorMsg(
        err.response?.data?.error?.message ??
        err.response?.data?.detail ??
        'Błąd wysyłki do KSeF',
      );
    } finally {
      window.dispatchEvent(new CustomEvent(REFRESH_EVENT));
      setBusy(false);
    }
  };

  const showRejectedDetails = (e) => {
    e.stopPropagation();
    setErrorMsg(ksefState.tooltip ?? 'Faktura odrzucona przez KSeF');
  };

  const sendBlocked = ksefState.kind === 'send' && ksefConnectionStatus !== 'CONNECTED';
  const isDisabled =
    busy ||
    ksefState.kind === 'processing' ||
    ksefState.kind === 'upo' ||
    sendBlocked;

  const handleClick =
    ksefState.kind === 'send' ? submitToKsef :
    ksefState.kind === 'rejected' ? showRejectedDetails :
    undefined;

  const tileTitle =
    sendBlocked && !busy ? 'Aby wysłać fakturę, połącz się z KSeF' :
    ksefState.tooltip ?? undefined;

  return (
    <div className={styles.wrap}>
      <button
        className={`${styles.tile} ${styles[`kind_${ksefState.kind}`]}${busy ? ` ${styles.tileBusy}` : ''}`}
        disabled={isDisabled}
        onClick={handleClick}
        title={tileTitle}
        aria-label={ksefState.label}
      >
        {busy
          ? <span className="spinner" style={{ width: 12, height: 12 }} />
          : ksefState.label}
      </button>
      {errorMsg && (
        <span
          className={styles.err}
          title={errorMsg}
          onClick={(e) => { e.stopPropagation(); setErrorMsg(''); }}
        >
          ⚠ {errorMsg.length > 36 ? `${errorMsg.slice(0, 36)}…` : errorMsg}
        </span>
      )}
    </div>
  );
}

