import { useEffect, useRef, useState } from 'react';
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
  const [popoverOpen, setPopoverOpen] = useState(false);
  const wrapRef = useRef(null);
  const ksefState = resolveKsefState(invoice.status, invoice);
  const ksefConnectionStatus = useAppStore((s) => s.ksefConnection.ui_status);

  useEffect(() => {
    if (!popoverOpen) {
      return undefined;
    }

    const scrollHost = wrapRef.current?.closest('[data-invoice-scroll-area]');

    const handlePointerDown = (event) => {
      if (!wrapRef.current) return;
      if (!wrapRef.current.contains(event.target)) {
        setPopoverOpen(false);
      }
    };

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setPopoverOpen(false);
      }
    };

    const handleScroll = () => {
      setPopoverOpen(false);
    };

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleEscape);
    scrollHost?.addEventListener('scroll', handleScroll, { passive: true });
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleEscape);
      scrollHost?.removeEventListener('scroll', handleScroll);
    };
  }, [popoverOpen]);

  const getRejectedErrorMessage = () => {
    const candidates = [
      invoice?.error_message,
      invoice?.ksef_error_message,
      invoice?.rejection_reason,
      invoice?.last_error,
      invoice?.transmission_error_message,
      invoice?.ksef_last_error,
      ksefState.tooltip,
    ];

    for (const candidate of candidates) {
      if (typeof candidate === 'string' && candidate.trim()) {
        return candidate.trim();
      }
    }

    return 'Faktura odrzucona przez KSeF.';
  };

  const submitToKsef = async (e) => {
    e.stopPropagation();
    setBusy(true);
    setErrorMsg('');
    setPopoverOpen(false);
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
    const msg = getRejectedErrorMessage();
    setErrorMsg(msg);
    setPopoverOpen((prev) => !prev);
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
    (ksefState.kind === 'rejected' ? undefined : ksefState.tooltip ?? undefined);

  return (
    <div className={styles.wrap} ref={wrapRef}>
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
      {ksefState.kind === 'rejected' && popoverOpen && errorMsg && (
        <div
          className={styles.errorPopover}
          role="dialog"
          aria-label="Szczegóły odrzucenia KSeF"
          onClick={(e) => e.stopPropagation()}
        >
          {errorMsg}
        </div>
      )}
    </div>
  );
}

