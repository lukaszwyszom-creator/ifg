import { useState, useEffect, useMemo } from 'react';
import { useAppStore } from '../../store/useAppStore';
import { formatCurrencyPLN, formatSignedCurrencyPLN } from '../../utils/amountFormatting';
import { buildPlnSummary } from './dashboardAggregation';
import { buildInvoicePoolKey, buildInvoicePoolQuery, resolveEffectiveFilters } from './dashboardQuery';
import styles from './VATSummary.module.css';

const VAT_RATES = ['23', '8', '5', '0'];

function monthLabel(prefix) {
  if (!prefix) return '';
  const [y, m] = prefix.split('-');
  const monthNames = {
    '01': 'styczeń',
    '02': 'luty',
    '03': 'marzec',
    '04': 'kwiecień',
    '05': 'maj',
    '06': 'czerwiec',
    '07': 'lipiec',
    '08': 'sierpień',
    '09': 'wrzesień',
    '10': 'październik',
    '11': 'listopad',
    '12': 'grudzień',
  };
  return `${monthNames[m] || m} ${y}`;
}

function toNum(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function toNumericRate(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }

  const text = String(value).trim();
  if (!text) return null;
  const normalized = text.replace('%', '').replace(',', '.');
  const directParsed = Number(normalized);
  if (Number.isFinite(directParsed)) return directParsed;
  const numericToken = normalized.match(/-?\d+(?:\.\d+)?/);
  if (!numericToken) return null;
  const parsed = Number(numericToken[0]);
  return Number.isFinite(parsed) ? parsed : null;
}

function resolveRate(item) {
  const rate = toNumericRate(item?.vat_rate);
  if (rate === null) return 'inne';
  if (rate >= 22.5 && rate <= 23.5) return '23';
  if (rate >= 7.5 && rate <= 8.5) return '8';
  if (rate >= 4.5 && rate <= 5.5) return '5';
  if (rate <= 0.5) return '0';
  return 'inne';
}

function createEmptyRateRow() {
  return {
    saleNet: 0,
    saleVat: 0,
    purchaseNet: 0,
    purchaseVat: 0,
  };
}

export default function VATSummary({ filters }) {
  const loadInvoicePool = useAppStore((s) => s.loadInvoicePool);
  const [rows, setRows] = useState([]);
  const [totals, setTotals] = useState({ saleNet: 0, saleVat: 0, purchaseNet: 0, purchaseVat: 0 });
  const [loading, setLoading] = useState(false);

  const { monthPrefix: periodPrefix } = resolveEffectiveFilters(filters);

  const saleQuery = buildInvoicePoolQuery(filters, 'sale', { defaultToCurrentMonth: true });
  const purchaseQuery = buildInvoicePoolQuery(filters, 'purchase', { defaultToCurrentMonth: true });
  const salePoolKey = buildInvoicePoolKey(saleQuery);
  const purchasePoolKey = buildInvoicePoolKey(purchaseQuery);

  const saleEntry = useAppStore((s) => s.invoicePool?.sale?.[salePoolKey]);
  const purchaseEntry = useAppStore((s) => s.invoicePool?.purchase?.[purchasePoolKey]);
  const saleLoading = useAppStore((s) => Boolean(s.invoicePoolLoading?.[`sale:${salePoolKey}`]));
  const purchaseLoading = useAppStore((s) => Boolean(s.invoicePoolLoading?.[`purchase:${purchasePoolKey}`]));

  const saleInvoices = useMemo(
    () => (Array.isArray(saleEntry?.items) ? saleEntry.items : []),
    [saleEntry]
  );
  const purchaseInvoices = useMemo(
    () => (Array.isArray(purchaseEntry?.items) ? purchaseEntry.items : []),
    [purchaseEntry]
  );

  const delta = totals.saleVat - totals.purchaseVat;
  const deltaLabel = delta > 0
    ? 'VAT należny (do zapłaty):'
    : delta < 0
      ? 'VAT naliczony (do odliczenia/zwrotu):'
      : 'VAT do rozliczenia:';

  useEffect(() => {
    let cancelled = false;

    setLoading(true);

    Promise.all([
      loadInvoicePool({ direction: 'sale', filters, options: { defaultToCurrentMonth: true } }),
      loadInvoicePool({ direction: 'purchase', filters, options: { defaultToCurrentMonth: true } }),
    ])
      .catch(() => null)
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [filters, loadInvoicePool, salePoolKey, purchasePoolKey]);

  useEffect(() => {
    if (saleLoading || purchaseLoading) {
      setLoading(true);
      return;
    }

    const rateMap = {
      '23': createEmptyRateRow(),
      '8': createEmptyRateRow(),
      '5': createEmptyRateRow(),
      '0': createEmptyRateRow(),
      inne: createEmptyRateRow(),
    };

    const aggregateInto = (invoices, side) => {
      for (const inv of invoices) {
        if ((inv.status ?? '') === 'rejected') continue;
        if ((inv.currency ?? 'PLN').toUpperCase() !== 'PLN') continue;
        for (const item of inv.items || []) {
          const rate = resolveRate(item);
          const row = rateMap[rate] || (rateMap.inne = createEmptyRateRow());
          const net = toNum(item.net_total);
          const vat = rate === '0' ? 0 : toNum(item.vat_total);

          if (side === 'sale') {
            row.saleNet += net;
            row.saleVat += vat;
          } else {
            row.purchaseNet += net;
            row.purchaseVat += vat;
          }
        }
      }
    };

    aggregateInto(saleInvoices, 'sale');
    aggregateInto(purchaseInvoices, 'purchase');

    const orderedRates = [...VAT_RATES];
    if (
      rateMap.inne.saleNet > 0
      || rateMap.inne.saleVat > 0
      || rateMap.inne.purchaseNet > 0
      || rateMap.inne.purchaseVat > 0
    ) {
      orderedRates.push('inne');
    }

    const finalRows = orderedRates.map((rate) => {
      const row = rateMap[rate];
      return {
        rate,
        saleNet: +row.saleNet.toFixed(2),
        saleVat: +row.saleVat.toFixed(2),
        purchaseNet: +row.purchaseNet.toFixed(2),
        purchaseVat: +row.purchaseVat.toFixed(2),
        deltaVat: +(row.purchaseVat - row.saleVat).toFixed(2),
      };
    });

    const saleSummary = buildPlnSummary(saleInvoices);
    const purchaseSummary = buildPlnSummary(purchaseInvoices);

    setRows(finalRows);
    setTotals({
      saleNet: saleSummary.netto,
      saleVat: saleSummary.vat,
      purchaseNet: purchaseSummary.netto,
      purchaseVat: purchaseSummary.vat,
    });
    setLoading(false);
  }, [saleInvoices, purchaseInvoices, saleLoading, purchaseLoading]);

  if (loading) return <div className={styles.card}><span className="spinner" /></div>;

  const tableDelta = totals.purchaseVat - totals.saleVat;

  return (
    <div className={styles.card}>
      <div className="card-header">
        <span className={`card-title ${styles.monthTitle}`}>Zestawienie VAT - {monthLabel(periodPrefix)}</span>
        <span className={`${styles.deltaBadge} ${delta > 0 ? styles.deltaDue : delta < 0 ? styles.deltaDeductible : styles.deltaNeutral}`}>
          {deltaLabel} {formatCurrencyPLN(Math.abs(delta))}
        </span>
      </div>

      <table className={styles.table}>
        <thead>
          <tr>
            <th rowSpan={2}>Stawka VAT</th>
            <th className={styles.groupTitle} colSpan={2}>Sprzedaż</th>
            <th className={styles.groupTitle} colSpan={2}>Zakup</th>
            <th rowSpan={2}>Różnica VAT</th>
          </tr>
          <tr>
            <th className={styles.netCol}>Netto</th>
            <th className={styles.vatCol}>VAT</th>
            <th className={`${styles.netCol} ${styles.sectionSep}`}>Netto</th>
            <th className={styles.vatCol}>VAT</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={6} className={styles.empty}>Brak danych</td>
            </tr>
          )}
          {rows.map((r) => (
            <tr key={r.rate}>
              <td className={styles.rate}>{r.rate === 'inne' ? 'inne' : `${r.rate}%`}</td>
              <td className={styles.netCol}>{formatCurrencyPLN(r.saleNet)}</td>
              <td className={styles.vatCol}>{formatCurrencyPLN(r.saleVat)}</td>
              <td className={`${styles.netCol} ${styles.sectionSep}`}>{formatCurrencyPLN(r.purchaseNet)}</td>
              <td className={styles.vatCol}>{formatCurrencyPLN(r.purchaseVat)}</td>
              <td className={r.deltaVat >= 0 ? styles.deltaDue : styles.deltaDeductible}>{formatSignedCurrencyPLN(r.deltaVat)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className={styles.totalRow}>
            <td>SUMA</td>
            <td className={styles.netCol}>{formatCurrencyPLN(totals.saleNet)}</td>
            <td className={styles.vatCol}>{formatCurrencyPLN(totals.saleVat)}</td>
            <td className={`${styles.netCol} ${styles.sectionSep}`}>{formatCurrencyPLN(totals.purchaseNet)}</td>
            <td className={styles.vatCol}>{formatCurrencyPLN(totals.purchaseVat)}</td>
            <td className={tableDelta >= 0 ? styles.deltaDue : styles.deltaDeductible}>{formatSignedCurrencyPLN(tableDelta)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
