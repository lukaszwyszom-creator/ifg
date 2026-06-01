import { useEffect, useMemo, useRef, useState } from 'react';
import { settingsApi } from '../../api/settings';
import { ksefApi } from '../../api/ksef';
import { transmissionsApi } from '../../api/transmissions';
import { useAppStore } from '../../store/useAppStore';
import { resolveKsefState } from './invoiceOpenMode';
import styles from './InvoiceActions.module.css';

const REFRESH_EVENT = 'ksef:status-refresh';
const KSEF_STATUS_POLL_MS = 5000;
const GENERIC_REJECTION_MSG = 'Faktura odrzucona przez KSeF';
const COMPANY_SETTINGS_MSG = 'Uzupełnij dane sprzedawcy w Ustawieniach firmy.';
const KSEF_CONNECT_MSG = 'Połącz KSeF u góry strony, aby wysłać ponownie.';
const RESUBMIT_HELP_MSG =
  'KSeF odrzucił fakturę. Otwórz ją do edycji, popraw dane i kliknij „Wyślij ponownie” — szczegóły błędu pojawią się po wysyłce.';

function isGenericRejectionMessage(message) {
  const normalized = String(message || '').trim();
  return !normalized || normalized === GENERIC_REJECTION_MSG || normalized === `${GENERIC_REJECTION_MSG}.`;
}

function isCompanySettingsComplete(settings) {
  if (!settings) return false;
  const name = String(settings.seller_name || '').trim();
  const nip = String(settings.seller_nip || '').trim();
  const street = String(settings.seller_street || '').trim();
  const buildingNo = String(settings.seller_building_no || '').trim();
  const postalCode = String(settings.seller_postal_code || '').trim();
  const city = String(settings.seller_city || '').trim();
  const country = String(settings.seller_country || '').trim();
  const hasStreetLine = Boolean(street || buildingNo);
  const hasLocality = Boolean(city || postalCode);
  return Boolean(name && nip && country && hasStreetLine && hasLocality);
}

function isSellerSnapshotComplete(snapshot) {
  if (!snapshot) return false;
  const name = String(snapshot.name || '').trim();
  const nip = String(snapshot.nip || '').trim();
  const street = String(snapshot.street || '').trim();
  const buildingNo = String(snapshot.building_no || '').trim();
  const postalCode = String(snapshot.postal_code || '').trim();
  const city = String(snapshot.city || '').trim();
  const country = String(snapshot.country || '').trim();
  const hasStreetLine = Boolean(street || buildingNo || String(snapshot.address || '').trim());
  const hasLocality = Boolean(city || postalCode);
  return Boolean(name && nip && country && hasStreetLine && hasLocality);
}

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
  const [companySettings, setCompanySettings] = useState(null);
  const wrapRef = useRef(null);
  const ksefState = resolveKsefState(invoice.status, invoice);
  const ksefConnectionStatus = useAppStore((s) => s.ksefConnection.ui_status);
  const setKsefConnection = useAppStore((s) => s.setKsefConnection);
  const sellerNip = useAppStore((s) => s.sellerNip);
  const isSaleInvoice = (invoice.direction || 'sale') === 'sale';
  const isResubmit = ksefState.kind === 'rejected' && isSaleInvoice;

  useEffect(() => {
    setErrorMsg('');
    setPopoverOpen(false);
  }, [invoice.id, invoice.status]);

  useEffect(() => {
    if (!isSaleInvoice) {
      setCompanySettings(null);
      return undefined;
    }

    let cancelled = false;
    settingsApi
      .get()
      .then((data) => {
        if (!cancelled) setCompanySettings(data);
      })
      .catch(() => {
        if (!cancelled) setCompanySettings(null);
      });

    return () => {
      cancelled = true;
    };
  }, [isSaleInvoice, invoice.id]);

  useEffect(() => {
    if (!isSaleInvoice) {
      return undefined;
    }

    let cancelled = false;
    ksefApi
      .getStatus(sellerNip?.length === 10 ? sellerNip : null)
      .then((data) => {
        if (!cancelled) setKsefConnection(data);
      })
      .catch(() => null);

    return () => {
      cancelled = true;
    };
  }, [isSaleInvoice, sellerNip, setKsefConnection]);

  useEffect(() => {
    if (!popoverOpen) {
      return undefined;
    }

    const scrollHost = wrapRef.current?.closest('[data-invoice-scroll-area]');

    const handlePointerDown = (event) => {
      if (wrapRef.current?.contains(event.target)) return;
      setPopoverOpen(false);
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

  const isInFlight = ksefState.kind === 'processing';

  useEffect(() => {
    if (!isInFlight || !onRefresh) {
      return undefined;
    }

    let cancelled = false;
    const poll = () => {
      if (cancelled) return;
      Promise.resolve(onRefresh()).catch(() => null);
      window.dispatchEvent(new CustomEvent(REFRESH_EVENT));
    };

    poll();
    const pollId = window.setInterval(poll, KSEF_STATUS_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(pollId);
    };
  }, [isInFlight, invoice.id, onRefresh]);

  const canSubmitToKsef = ksefState.kind === 'send' || (ksefState.kind === 'rejected' && isSaleInvoice);

  const companyIssue = useMemo(() => {
    if (!isSaleInvoice || !canSubmitToKsef) return null;
    if (companySettings) {
      return isCompanySettingsComplete(companySettings) ? null : COMPANY_SETTINGS_MSG;
    }
    return isSellerSnapshotComplete(invoice.seller_snapshot) ? null : COMPANY_SETTINGS_MSG;
  }, [canSubmitToKsef, companySettings, invoice.seller_snapshot, isSaleInvoice]);

  const getRejectedErrorMessage = () => {
    const fromInvoice = String(invoice?.ksef_last_error || '').trim();
    if (fromInvoice) {
      return fromInvoice;
    }

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
    if (companyIssue) {
      setErrorMsg(companyIssue);
      return;
    }
    if (ksefConnectionStatus !== 'CONNECTED') {
      setErrorMsg(KSEF_CONNECT_MSG);
      return;
    }

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

  const sendBlocked =
    canSubmitToKsef &&
    !isResubmit &&
    (ksefConnectionStatus !== 'CONNECTED' || Boolean(companyIssue));
  const sendingNow = busy && canSubmitToKsef;
  const displayKind = sendingNow ? 'processing' : ksefState.kind;
  const displayLabel = sendingNow
    ? 'W toku'
    : (isResubmit ? 'Wyślij ponownie' : ksefState.label);
  const isDisabled =
    busy ||
    ksefState.kind === 'processing' ||
    ksefState.kind === 'upo' ||
    sendBlocked;

  const resubmitStatusMessage = useMemo(() => {
    if (!isResubmit) return null;
    if (companyIssue) return companyIssue;
    if (ksefConnectionStatus !== 'CONNECTED') return KSEF_CONNECT_MSG;

    const rejectionMessage = getRejectedErrorMessage();
    if (isGenericRejectionMessage(rejectionMessage)) {
      return RESUBMIT_HELP_MSG;
    }
    return rejectionMessage;
  }, [
    companyIssue,
    invoice,
    isResubmit,
    ksefConnectionStatus,
    ksefState.tooltip,
  ]);

  const handleClick =
    canSubmitToKsef ? submitToKsef :
    ksefState.kind === 'rejected' ? showRejectedDetails :
    undefined;

  const tileTitle =
    companyIssue ??
    (sendBlocked && !busy ? KSEF_CONNECT_MSG :
    (isResubmit ? resubmitStatusMessage ?? undefined : ksefState.tooltip ?? undefined));

  const inlineError =
    companyIssue ??
    (canSubmitToKsef && errorMsg ? errorMsg : null) ??
    (ksefState.kind === 'rejected' && !isSaleInvoice && popoverOpen && errorMsg ? errorMsg : null);

  const statusMessage = inlineError || resubmitStatusMessage;
  const isHintMessage = Boolean(
    resubmitStatusMessage &&
    !inlineError &&
    ksefConnectionStatus === 'CONNECTED' &&
    !companyIssue,
  );

  return (
    <div
      className={`${styles.wrap}${statusMessage ? ` ${styles.wrapStack}` : ''}`}
      ref={wrapRef}
    >
      <button
        className={`${styles.tile} ${styles[`kind_${displayKind}`]}${busy ? ` ${styles.tileBusy}` : ''}`}
        disabled={isDisabled}
        onClick={handleClick}
        title={tileTitle}
        aria-label={displayLabel}
      >
        {displayLabel}
      </button>
      {statusMessage && (
        <div
          className={`${styles.inlineError}${isHintMessage ? ` ${styles.inlineHint}` : ''}`}
          role={inlineError ? 'alert' : 'status'}
          onClick={(e) => e.stopPropagation()}
        >
          {statusMessage}
        </div>
      )}
    </div>
  );
}
