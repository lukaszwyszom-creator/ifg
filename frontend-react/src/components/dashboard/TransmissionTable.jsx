import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { transmissionsApi } from '../../api/transmissions';
import { resolveTransmissionLoadError } from '../../utils/transmissionLoadError';
import Pagination from '../common/Pagination';
import TransmissionGroup from './transmissions/TransmissionGroup';
import { MONITOR_FILTERS, filterAndSearchGroups, groupTransmissions } from './transmissions/transmissionUtils';
import styles from './transmissions/TransmissionMonitor.module.css';

const TERMINAL = new Set(['success', 'failed_permanent']);
const POLL_INTERVAL_MS = 8000;

export default function TransmissionTable() {
  const [data, setData] = useState({ items: [], total: 0 });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [actionMsg, setActionMsg] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedKeys, setExpandedKeys] = useState(() => new Set());
  const [retryBusyId, setRetryBusyId] = useState(null);
  const pollRef = useRef(null);
  const searchInputRef = useRef(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError('');
    try {
      const res = await transmissionsApi.list(page, 20, false);
      setData(res);
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
  }, [page]);

  useEffect(() => {
    load();
    return () => clearTimeout(pollRef.current);
  }, [load]);

  const groups = useMemo(() => groupTransmissions(data.items), [data.items]);
  const visibleGroups = useMemo(
    () => filterAndSearchGroups(groups, activeFilter, searchQuery),
    [groups, activeFilter, searchQuery],
  );

  const counters = data.items.reduce((acc, row) => {
    const sev = String(row.severity || '').toUpperCase();
    if (sev === 'SUCCESS') acc.success += 1;
    else if (sev === 'WARNING') acc.warning += 1;
    else if (sev === 'ERROR') acc.error += 1;
    else if (sev === 'RUNNING') acc.running += 1;
    return acc;
  }, { success: 0, warning: 0, error: 0, running: 0 });

  const toggleGroup = (key) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const handleRetry = async (transmission) => {
    setRetryBusyId(transmission.id);
    setActionMsg('');
    try {
      await transmissionsApi.retry(transmission.id);
      setActionMsg('Ponowiono transmisję');
      load(true);
    } catch (err) {
      setActionMsg(err.response?.data?.error?.message ?? 'Błąd retry');
    } finally {
      setRetryBusyId(null);
    }
  };

  return (
    <div className={styles.monitorRoot}>
      <div className={styles.toolbar}>
        <span className={styles.title}>Monitor KSeF</span>
        <div className={styles.actions}>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            disabled={loading}
            onClick={() => load()}
            title="Odśwież"
          >
            ↻ Odśwież
          </button>
        </div>
      </div>

      <div className={styles.filtersBar} role="group" aria-label="Filtry transmisji">
        {MONITOR_FILTERS.map((filter) => (
          <button
            key={filter.key}
            type="button"
            className={`${styles.filterChip} ${activeFilter === filter.key ? styles.filterChipActive : ''}`}
            onClick={() => setActiveFilter(filter.key)}
            aria-pressed={activeFilter === filter.key}
          >
            {filter.label}
          </button>
        ))}
      </div>

      <div className={styles.searchBar}>
        <span className={styles.searchIcon} aria-hidden>🔍</span>
        <input
          ref={searchInputRef}
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className={styles.searchInput}
          placeholder="🔍 Numer FV / kontrahent / KSeF / ID"
          aria-label="Szukaj transmisji"
        />
        {searchQuery.trim() && (
          <button
            type="button"
            className={styles.searchClear}
            onClick={() => {
              setSearchQuery('');
              searchInputRef.current?.focus();
            }}
            aria-label="Wyczyść wyszukiwanie"
            title="Wyczyść"
          >
            ×
          </button>
        )}
      </div>

      <div className={styles.counters}>
        <span className={styles.counterSuccess}>Sukcesy: {counters.success}</span>
        <span className={styles.counterWarning}>Ostrzeżenia: {counters.warning}</span>
        <span className={styles.counterError}>Błędy: {counters.error}</span>
        <span className={styles.counterRunning}>W toku: {counters.running}</span>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 10 }}>{error}</div>}
      {actionMsg && <div className="alert alert-success" style={{ marginBottom: 10 }}>{actionMsg}</div>}

      <div className={styles.monitor}>
        <div className={styles.headerRow} aria-hidden="true">
          <span />
          <span>Znacznik</span>
          <span>Proces</span>
          <span>Status</span>
          <span>Faktury</span>
          <span>Czas</span>
          <span />
        </div>

        {loading ? (
          <div className={styles.loading}><div className="spinner" /></div>
        ) : groups.length === 0 ? (
          <div className={styles.empty}>Brak transmisji</div>
        ) : visibleGroups.length === 0 ? (
          <div className={styles.empty}>
            {searchQuery.trim()
              ? 'Brak transmisji pasujących do wyszukiwania.'
              : 'Brak transmisji spełniających wybrane kryteria.'}
          </div>
        ) : (
          visibleGroups.map((group) => (
            <TransmissionGroup
              key={group.key}
              group={group}
              expanded={expandedKeys.has(group.key)}
              onToggle={() => toggleGroup(group.key)}
              onRetry={handleRetry}
              retryBusyId={retryBusyId}
            />
          ))
        )}
      </div>

      <Pagination page={page} total={data.total} size={20} onPage={(p) => { setPage(p); }} />
    </div>
  );
}
