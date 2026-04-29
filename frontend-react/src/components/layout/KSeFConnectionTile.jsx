import { useEffect } from 'react';
import { ksefApi } from '../../api/ksef';
import { settingsApi } from '../../api/settings';
import { useAppStore } from '../../store/useAppStore';
import styles from './KSeFConnectionTile.module.css';

const REFRESH_EVENT = 'ksef:status-refresh';
const SHOW_DEBUG_ERRORS = import.meta.env.DEV;

const UI_CONFIG = {
  DISCONNECTED: {
    label: 'niepołączony',
    dotClass: styles.gray,
    actionLabel: 'Połącz',
  },
  CONNECTING: {
    label: 'łączenie...',
    dotClass: styles.orange,
    actionLabel: null,
  },
  CONNECTED: {
    label: 'połączony',
    dotClass: styles.green,
    actionLabel: null,
  },
  ERROR: {
    label: 'błąd',
    dotClass: styles.red,
    actionLabel: 'Spróbuj ponownie',
  },
};

function disconnectedPayload(reason = 'NO_SESSION', lastError = null) {
  return {
    ui_status: 'DISCONNECTED',
    details: {
      reason,
      has_session: false,
      session_expires_at: null,
      last_error: lastError,
    },
  };
}

function getFriendlyReason(reason) {
  switch (reason) {
    case 'NO_SESSION':
      return 'Brak aktywnej sesji';
    case 'SESSION_EXPIRED':
      return 'Sesja wygasła';
    case 'NETWORK_ERROR':
      return 'Brak połączenia z KSeF';
    case 'AUTH_ERROR':
      return 'Błąd autoryzacji';
    case 'KSEF_UNAVAILABLE':
      return 'KSeF niedostępny';
    default:
      return 'Nieznany błąd';
  }
}

function buildTooltip(details) {
  const reasonText = getFriendlyReason(details?.reason);
  const lastError = details?.last_error;
  if (!lastError || !SHOW_DEBUG_ERRORS) {
    return reasonText;
  }

  const compactError = lastError.length > 96 ? `${lastError.slice(0, 96)}...` : lastError;
  return `${reasonText}\n${compactError}`;
}

export default function KSeFConnectionTile() {
  const sellerNip = useAppStore((s) => s.sellerNip);
  const setSellerNip = useAppStore((s) => s.setSellerNip);
  const status = useAppStore((s) => s.ksefConnection);
  const setKsefConnection = useAppStore((s) => s.setKsefConnection);

  const applyStatus = (nextStatus) => {
    setKsefConnection(nextStatus);
  };

  useEffect(() => {
    let cancelled = false;

    const ensureSellerNip = async () => {
      if (sellerNip?.length === 10) {
        return sellerNip;
      }

      try {
        const settings = await settingsApi.get();
        if (settings.seller_nip?.length === 10) {
          setSellerNip(settings.seller_nip);
          return settings.seller_nip;
        }
      } catch {
        return '';
      }

      return '';
    };

    const refreshKsefStatus = async () => {
      try {
        const nextStatus = await ksefApi.getStatus();
        if (!nextStatus || cancelled) {
          return;
        }
        applyStatus(nextStatus);
      } catch (error) {
        if (cancelled) {
          return;
        }
        applyStatus({
          ui_status: 'ERROR',
          details: {
            reason: 'UNKNOWN',
            has_session: false,
            session_expires_at: null,
            last_error:
              error?.response?.data?.error?.message ??
              error?.message ??
              'Nie udało się pobrać statusu KSeF.',
          },
        });
      }
    };

    const handleOnline = () => {
      void refreshKsefStatus();
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        void refreshKsefStatus();
      }
    };

    const handleRefreshEvent = () => {
      void refreshKsefStatus();
    };

    ensureSellerNip().finally(refreshKsefStatus);
    const pollId = window.setInterval(refreshKsefStatus, 30000);
    window.addEventListener('online', handleOnline);
    window.addEventListener(REFRESH_EVENT, handleRefreshEvent);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      cancelled = true;
      window.clearInterval(pollId);
      window.removeEventListener('online', handleOnline);
      window.removeEventListener(REFRESH_EVENT, handleRefreshEvent);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [sellerNip, setSellerNip]);

  const handleClick = async () => {
    if (status.ui_status === 'CONNECTING') {
      return;
    }

    if (status.ui_status === 'CONNECTED') {
      return;
    }

    let nipToUse = sellerNip;
    if (!nipToUse || nipToUse.length !== 10) {
      try {
        const settings = await settingsApi.get();
        nipToUse = settings.seller_nip ?? '';
        if (nipToUse.length === 10) {
          setSellerNip(nipToUse);
        }
      } catch (error) {
        ksefApi.markStatusMutation();
        applyStatus({
          ui_status: 'ERROR',
          details: {
            reason: 'UNKNOWN',
            has_session: false,
            session_expires_at: null,
            last_error: error?.response?.data?.error?.message ?? 'Nie udało się pobrać NIP sprzedawcy.',
          },
        });
        return;
      }
    }

    if (!nipToUse || nipToUse.length !== 10) {
      ksefApi.markStatusMutation();
      applyStatus({
        ui_status: 'ERROR',
        details: {
          reason: 'UNKNOWN',
          has_session: false,
          session_expires_at: null,
          last_error: 'Brak poprawnego NIP sprzedawcy w ustawieniach.',
        },
      });
      return;
    }

    ksefApi.markStatusMutation();
    applyStatus({
      ui_status: 'CONNECTING',
      details: {
        reason: 'UNKNOWN',
        has_session: false,
        session_expires_at: null,
        last_error: null,
      },
    });

    try {
      const session = await ksefApi.openSession(nipToUse);
      ksefApi.markStatusMutation();
      applyStatus({
        ui_status: 'CONNECTED',
        details: {
          reason: 'UNKNOWN',
          has_session: true,
          session_expires_at: session.expires_at,
          last_error: null,
        },
      });
    } catch (error) {
      ksefApi.markStatusMutation();
      applyStatus({
        ui_status: 'ERROR',
        details: {
          reason: error?.response?.status === 502 ? 'AUTH_ERROR' : 'UNKNOWN',
          has_session: false,
          session_expires_at: null,
          last_error:
            error?.response?.data?.error?.message ??
            error?.response?.data?.detail ??
            'Nie udało się połączyć z KSeF.',
        },
      });
    }
  };

  const config = UI_CONFIG[status.ui_status] ?? UI_CONFIG.DISCONNECTED;
  const tooltip = buildTooltip(status.details);

  return (
    <button
      type="button"
      className={styles.tile}
      onClick={handleClick}
      disabled={status.ui_status === 'CONNECTING'}
      title={tooltip}
    >
      <span className={styles.brand}>KSeF</span>
      <span className={`${styles.ksefDot} ${config.dotClass}`} aria-hidden="true" />
      <span className={styles.statusText}>{config.label}</span>
      {config.actionLabel ? <span className={styles.action}>{config.actionLabel}</span> : null}
    </button>
  );
}