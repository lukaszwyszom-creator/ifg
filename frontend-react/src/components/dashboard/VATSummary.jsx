import { useState, useEffect } from 'react';
import { invoicesApi } from '../../api/invoices';
import styles from './VATSummary.module.css';

const VAT_RATES = ['23', '8', '5', '0'];

function currentMonthPrefix() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  return `${y}-${m}`;
}

function monthRange(prefix) {
  const [y, m] = String(prefix || currentMonthPrefix()).split('-').map(Number);
  const lastDay = new Date(y, m, 0).getDate();
  const month = String(m).padStart(2, '0');
  return {
    from: `${y}-${month}-01`,
    to: `${y}-${month}-${String(lastDay).padStart(2, '0')}`,
  };
}

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

function signedAmount(value) {
  const n = Number(value || 0);
  const abs = Math.abs(n).toFixed(2);
  if (n > 0) return `+${abs}`;
  if (n < 0) return `-${abs}`;
  return abs;
}

function resolveRate(item) {
  const rate = toNum(item?.vat_rate);
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

async function fetchAllInvoices(params) {
  let page = 1;
  const size = 100;
  let total = 0;
  const items = [];

  do {
    const res = await invoicesApi.list({ ...params, page, size });
    total = Number(res.total || 0);
    items.push(...(res.items || []));
    page += 1;
  } while (items.length < total);

  return items;
}

export default function VATSummary({ filters }) {
  const [rows, setRows] = useState([]);
  const [totals, setTotals] = useState({ saleNet: 0, saleVat: 0, purchaseNet: 0, purchaseVat: 0 });
  const [loading, setLoading] = useState(false);

  const periodPrefix = filters?.month || currentMonthPrefix();
  const { from, to } = monthRange(periodPrefix);

  const delta = totals.saleVat - totals.purchaseVat;
  const deltaLabel = delta > 0
    ? 'Należny (do zapłaty)'
    : delta < 0
      ? 'Naliczony (do odliczenia)'
      : 'VAT do rozliczenia: 0,00';

  useEffect(() => {
    let cancelled = false;

    setLoading(true);
    Promise.all([
      fetchAllInvoices({ direction: 'sale', issue_date_from: from, issue_date_to: to }),
      fetchAllInvoices({ direction: 'purchase', issue_date_from: from, issue_date_to: to }),
    ])
      .then(([saleInvoices, purchaseInvoices]) => {
        if (cancelled) return;

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
            for (const item of inv.items || []) {
              const rate = resolveRate(item);
              const row = rateMap[rate] || (rateMap.inne = createEmptyRateRow());
              const net = toNum(item.net_total);
              const vat = toNum(item.vat_total);

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

        const totalSaleNet = finalRows.reduce((sum, r) => sum + r.saleNet, 0);
        const totalSaleVat = finalRows.reduce((sum, r) => sum + r.saleVat, 0);
        const totalPurchaseNet = finalRows.reduce((sum, r) => sum + r.purchaseNet, 0);
        const totalPurchaseVat = finalRows.reduce((sum, r) => sum + r.purchaseVat, 0);

        setRows(finalRows);
        setTotals({
          saleNet: +totalSaleNet.toFixed(2),
          saleVat: +totalSaleVat.toFixed(2),
          purchaseNet: +totalPurchaseNet.toFixed(2),
          purchaseVat: +totalPurchaseVat.toFixed(2),
        });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [from, to]);

  if (loading) return <div className={styles.card}><span className="spinner" /></div>;

  const tableDelta = totals.purchaseVat - totals.saleVat;

  return (
    <div className={styles.card}>
      <div className="card-header">
        <span className={`card-title ${styles.monthTitle}`}>Zestawienie VAT - miesiąc {monthLabel(periodPrefix)}</span>
        <span className={`${styles.deltaBadge} ${delta > 0 ? styles.deltaDue : delta < 0 ? styles.deltaDeductible : styles.deltaNeutral}`}>
          {deltaLabel}: {Math.abs(delta).toFixed(2)}
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
            <th className={styles.netCol}>Netto</th>
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
              <td className={styles.netCol}>{r.saleNet.toFixed(2)}</td>
              <td className={styles.vatCol}>{r.saleVat.toFixed(2)}</td>
              <td className={styles.netCol}>{r.purchaseNet.toFixed(2)}</td>
              <td className={styles.vatCol}>{r.purchaseVat.toFixed(2)}</td>
              <td className={r.deltaVat >= 0 ? styles.deltaDue : styles.deltaDeductible}>{signedAmount(r.deltaVat)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className={styles.totalRow}>
            <td>SUMA</td>
            <td className={styles.netCol}>{totals.saleNet.toFixed(2)}</td>
            <td className={styles.vatCol}>{totals.saleVat.toFixed(2)}</td>
            <td className={styles.netCol}>{totals.purchaseNet.toFixed(2)}</td>
            <td className={styles.vatCol}>{totals.purchaseVat.toFixed(2)}</td>
            <td className={tableDelta >= 0 ? styles.deltaDue : styles.deltaDeductible}>{signedAmount(tableDelta)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
