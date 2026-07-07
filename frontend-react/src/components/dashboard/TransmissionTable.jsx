import { useState, useEffect, useCallback, useRef } from 'react';
import { transmissionsApi } from '../../api/transmissions';
import { resolveTransmissionLoadError } from '../../utils/transmissionLoadError';
import Table from '../common/Table';
import StatusBadge from '../common/StatusBadge';
import Pagination from '../common/Pagination';
import styles from './TransmissionTable.module.css';

const TERMINAL = new Set(['success', 'failed_permanent']);
const POLL_INTERVAL_MS = 8000;

/** Znacznik czasu transmisji: ddmmyyyyggmmss (gg = godzina). */
function formatTransmissionMarker(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  const pad = (n) => String(n).padStart(2, '0');
  return (
    `${pad(d.getDate())}${pad(d.getMonth() + 1)}${d.getFullYear()}`
    + `${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
  );
}

function RetryBtn({ transmission, onDone, onError }) {
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      await transmissionsApi.retry(transmission.id);
      onDone();
    } catch (err) {
      onError(err.response?.data?.error?.message ?? 'Błąd retry');
    } finally {
      setBusy(false);
    }
  };
  return (
    <button className="btn btn-secondary btn-sm" disabled={busy} onClick={run}>
      {busy ? <span className="spinner" style={{ width: 12, height: 12 }} /> : 'Ponów'}
    </button>
  );
}

export default function TransmissionTable() {
  const [data, setData] = useState({ items: [], total: 0 });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [actionMsg, setActionMsg] = useState('');
  const [warningsOnly, setWarningsOnly] = useState(false);
  const pollRef = useRef(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError('');
    try {
      const res = await transmissionsApi.list(page, 20, warningsOnly);
      setData(res);
      // Zaplanuj następne odświeżenie jeśli są aktywne transmisje
      const hasActive = res.items.some((t) => !TERMINAL.has(t.status));
      if (hasActive) {
        clearTimeout(pollRef.current);
        pollRef.current = setTimeout(() => load(true), POLL_INTERVAL_MS);
      }
    } catch (err) {
      setError(resolveTransmissionLoadError(err));
    } finally {
      if (!silent) setLoading(false);
    }
  }, [page, warningsOnly]);

  useEffect(() => {
    load();
    return () => clearTimeout(pollRef.current);
  }, [load]);

  const counters = data.items.reduce((acc, row) => {
    const sev = String(row.severity || '').toUpperCase();
    if (sev === 'SUCCESS') acc.success += 1;
    else if (sev === 'WARNING') acc.warning += 1;
    else if (sev === 'ERROR') acc.error += 1;
    else if (sev === 'RUNNING') acc.running += 1;
    return acc;
  }, { success: 0, warning: 0, error: 0, running: 0 });

  const renderMetadata = (value) => {
    if (!value || typeof value !== 'object') return <span className={styles.dash}>—</span>;
    return (
      <details>
        <summary className={styles.metaSummary}>Szczegóły</summary>
        <pre className={styles.metaPre}>{JSON.stringify(value, null, 2)}</pre>
      </details>
    );
  };

  const columns = [
    {
      key: 'created_at',
      label: 'Znacznik',
      width: 130,
      render: (v) => <span className={styles.mono}>{formatTransmissionMarker(v)}</span>,
    },
    {
      key: 'operation_type',
      label: 'Operacja',
      width: 170,
      render: (v) => v
        ? <span className={styles.badge}>{v}</span>
        : <span className={styles.dash}>—</span>,
    },
    {
      key: 'severity',
      label: 'Severity',
      width: 110,
      render: (v) => v
        ? <StatusBadge status={String(v).toLowerCase()} />
        : <span className={styles.dash}>—</span>,
    },
    {
      key: 'invoice_number_local',
      label: 'Faktura',
      width: 160,
      render: (v) => v
        ? <span className={styles.mono}>{v}</span>
        : <span className={styles.dash}>—</span>,
    },
    {
      key: 'status',
      label: 'Status',
      width: 150,
      render: (v) => <StatusBadge status={v} />,
    },
    {
      key: 'attempt_no',
      label: 'Próby',
      width: 60,
      render: (v) => v ?? '—',
    },
    {
      key: 'ksef_reference_number',
      label: 'Ref KSeF',
      width: 170,
      render: (v) => v ? <span className={styles.mono}>{v}</span> : <span className={styles.dash}>—</span>,
    },
    {
      key: 'job_id',
      label: 'Job',
      width: 130,
      render: (v) => v ? <span className={styles.mono}>{String(v).slice(0, 8)}</span> : <span className={styles.dash}>—</span>,
    },
    {
      key: 'correlation_id',
      label: 'Correlation',
      width: 130,
      render: (v) => v ? <span className={styles.mono}>{String(v).slice(0, 8)}</span> : <span className={styles.dash}>—</span>,
    },
    {
      key: 'error_message',
      label: 'Błąd',
      render: (v) => v
        ? <span className={styles.errText} title={v}>{v.length > 50 ? v.slice(0, 50) + '…' : v}</span>
        : <span className={styles.dash}>—</span>,
    },
    {
      key: 'metadata_json',
      label: 'Metadata',
      render: (v) => renderMetadata(v),
    },
    {
      key: '_actions',
      label: '',
      width: 80,
      render: (_, row) =>
        row.status === 'failed_retryable' ? (
          <RetryBtn
            transmission={row}
            onDone={() => { setActionMsg('Ponowiono transmisję'); load(true); }}
            onError={(m) => setActionMsg(m)}
          />
        ) : null,
    },
  ];

  return (
    <div>
      <div className={styles.toolbar}>
        <span className={styles.title}>Monitor KSeF</span>
        <div className={styles.actions}>
          <label className={styles.filterToggle}>
            <input
              type="checkbox"
              checked={warningsOnly}
              onChange={(e) => {
                setWarningsOnly(e.target.checked);
                setPage(1);
              }}
            />
            Tylko błędy i ostrzeżenia
          </label>
          <button
            className="btn btn-ghost btn-sm"
            disabled={loading}
            onClick={() => load()}
            title="Odśwież"
          >
            ↻ Odśwież
          </button>
        </div>
      </div>
      <div className={styles.counters}>
        <span className={styles.counterSuccess}>Sukcesy: {counters.success}</span>
        <span className={styles.counterWarning}>Ostrzeżenia: {counters.warning}</span>
        <span className={styles.counterError}>Błędy: {counters.error}</span>
        <span className={styles.counterRunning}>W toku: {counters.running}</span>
      </div>

      {error    && <div className="alert alert-error"   style={{ marginBottom: 10 }}>{error}</div>}
      {actionMsg && <div className="alert alert-success" style={{ marginBottom: 10 }}>{actionMsg}</div>}

      <Table
        columns={columns}
        rows={data.items}
        loading={loading}
        emptyMsg="Brak transmisji"
      />
      <Pagination page={page} total={data.total} size={20} onPage={(p) => { setPage(p); }} />
    </div>
  );
}
