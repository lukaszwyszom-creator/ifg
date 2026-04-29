import { useEffect, useState } from 'react';
import { invoicesApi } from '../../api/invoices';
import styles from './Filters.module.css';

const INVOICE_STATUSES = [
  { value: '', label: 'Wszystkie statusy' },
  { value: 'ready_for_submission', label: 'Gotowa' },
  { value: 'sending', label: 'Wysyłanie' },
  { value: 'accepted', label: 'Zaakceptowana' },
  { value: 'rejected', label: 'Odrzucona' },
];

function buildYearOptions() {
  const cur = new Date().getFullYear();
  return [cur - 2, cur - 1, cur, cur + 1].map((y) => ({ value: String(y), label: String(y) }));
}

const YEAR_OPTIONS = buildYearOptions();

const MONTHS_OF_YEAR = [
  { value: '01', label: 'styczeń' },
  { value: '02', label: 'luty' },
  { value: '03', label: 'marzec' },
  { value: '04', label: 'kwiecień' },
  { value: '05', label: 'maj' },
  { value: '06', label: 'czerwiec' },
  { value: '07', label: 'lipiec' },
  { value: '08', label: 'sierpień' },
  { value: '09', label: 'wrzesień' },
  { value: '10', label: 'październik' },
  { value: '11', label: 'listopad' },
  { value: '12', label: 'grudzień' },
];

/**
 * @param {object}   filters   - { month, status, issue_date_from, issue_date_to, contractor }
 * @param {Function} onChange  - (patch) => void
 * @param {Function} onReset   - () => void
 * @param {bool}     compact   - ukryj contractor
 */
export default function Filters({ filters, onChange, onReset, compact = false }) {
  const [contractorHints, setContractorHints] = useState([]);
  const contractorQuery = String(filters.contractor || '').trim();

  const now = new Date();
  const nowYear  = now.getFullYear();
  const nowMonth = now.getMonth() + 1; // 1-12

  const [filterYear, filterMonth] = (filters.month ?? '').split('-');
  const selectedYear = filterYear ? Number(filterYear) : null;

  // Jeśli wybrany rok jest przyszłyś i aktualnie wybrany miesiąc jeszcze nie
  // nastąpił, automatycznie korygujemy na bieżący miesiąc.
  const handleYear = (e) => {
    const yr = e.target.value;
    if (!yr) { onChange({ month: '', issue_date_from: '', issue_date_to: '' }); return; }
    const yrNum = Number(yr);
    let m = filterMonth || String(nowMonth).padStart(2, '0');
    if (yrNum > nowYear || (yrNum === nowYear && Number(m) > nowMonth)) {
      m = String(nowMonth).padStart(2, '0');
    }
    onChange({ month: `${yr}-${m}`, issue_date_from: '', issue_date_to: '' });
  };
  const handleMonth = (e) => onChange({ month: `${filterYear || nowYear}-${e.target.value}`, issue_date_from: '', issue_date_to: '' });
  const handleDateFrom = (e) => onChange({ issue_date_from: e.target.value, month: '' });
  const handleDateTo   = (e) => onChange({ issue_date_to: e.target.value, month: '' });

  useEffect(() => {
    if (compact || contractorQuery.length < 3) {
      setContractorHints([]);
      return;
    }

    let cancelled = false;
    const timerId = setTimeout(() => {
      invoicesApi
        .list({ page: 1, size: 30, number_filter: contractorQuery })
        .then((res) => {
          if (cancelled) return;

          const values = new Set();
          for (const inv of res.items ?? []) {
            const buyerName = String(inv.buyer_snapshot?.name || '').trim();
            const sellerName = String(inv.seller_snapshot?.name || '').trim();
            const buyerNip = String(inv.buyer_snapshot?.nip || '').trim();
            const sellerNip = String(inv.seller_snapshot?.nip || '').trim();
            if (buyerName) values.add(buyerName);
            if (sellerName) values.add(sellerName);
            if (buyerNip) values.add(buyerNip);
            if (sellerNip) values.add(sellerNip);
          }

          setContractorHints(Array.from(values).slice(0, 12));
        })
        .catch(() => {
          if (!cancelled) setContractorHints([]);
        });
    }, 220);

    return () => {
      cancelled = true;
      clearTimeout(timerId);
    };
  }, [compact, contractorQuery]);

  return (
    <div className={styles.bar}>
      <div className={styles.row}>
        <div className="form-group">
          <label className="form-label">Rok</label>
          <select
            className="select"
            value={filterYear ?? ''}
            onChange={handleYear}
            style={{ minWidth: 90 }}
          >
            <option value="">---</option>
            {YEAR_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Miesiąc</label>
          <select
            className="select"
            value={filterMonth ?? ''}
            onChange={handleMonth}
            style={{ minWidth: 140 }}
          >
            <option value="">---</option>
            {MONTHS_OF_YEAR.map((o) => {
              const isFuture = selectedYear !== null && (
                selectedYear > nowYear ||
                (selectedYear === nowYear && Number(o.value) > nowMonth)
              );
              return (
                <option
                  key={o.value}
                  value={o.value}
                  style={isFuture ? { color: '#888', fontStyle: 'italic' } : undefined}
                >
                  {o.label}
                </option>
              );
            })}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Status</label>
          <select
            className="select"
            value={filters.status}
            onChange={(e) => onChange({ status: e.target.value })}
            style={{ minWidth: 160 }}
          >
            {INVOICE_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Data od</label>
          <input
            type="date"
            className="input"
            value={filters.issue_date_from}
            onChange={handleDateFrom}
            style={{ width: 150 }}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Data do</label>
          <input
            type="date"
            className="input"
            value={filters.issue_date_to}
            onChange={handleDateTo}
            style={{ width: 150 }}
          />
        </div>

        {!compact && (
          <div className="form-group">
            <label className="form-label">Kontrahent (NIP/fragment nazwy)</label>
            <input
              type="text"
              className="input"
              list="contractor-hints"
              placeholder="min. 3 znaki..."
              value={filters.contractor}
              onChange={(e) => onChange({ contractor: e.target.value })}
              style={{ minWidth: 200 }}
            />
            <datalist id="contractor-hints">
              {contractorHints.map((hint) => (
                <option key={hint} value={hint} />
              ))}
            </datalist>
          </div>
        )}
      </div>

      <button className="btn btn-ghost btn-sm" onClick={onReset}>
        ✕ Wyczyść
      </button>
    </div>
  );
}
