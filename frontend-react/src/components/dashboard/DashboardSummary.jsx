import { useState, useEffect, useMemo } from 'react';
import {
  AreaChart, Area,
  XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
} from 'recharts';
import { invoicesApi } from '../../api/invoices';
import { buildPlnSummary } from './dashboardAggregation';
import styles from './DashboardSummary.module.css';

const fmtPln = (n) => `${n.toLocaleString('pl-PL', { minimumFractionDigits: 2 })} PLN`;

// ---- helpers ----
function currentMonthPrefix() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  return `${y}-${m}`;
}

function toSlashDate(isoDate) {
  if (!isoDate || typeof isoDate !== 'string' || isoDate.length < 10) return '...';
  const y = isoDate.slice(0, 4);
  const m = isoDate.slice(5, 7);
  const d = isoDate.slice(8, 10);
  return `${d}/${m}/${y}`;
}

function parseIsoDate(dateStr) {
  const dt = new Date(`${dateStr}T00:00:00`);
  return Number.isNaN(dt.getTime()) ? null : dt;
}

function buildDateRange(fromDate, toDate) {
  const start = parseIsoDate(fromDate);
  const end = parseIsoDate(toDate);
  if (!start || !end || start > end) return [];

  const dates = [];
  const cursor = new Date(start);
  while (cursor <= end) {
    const y = cursor.getFullYear();
    const m = String(cursor.getMonth() + 1).padStart(2, '0');
    const d = String(cursor.getDate()).padStart(2, '0');
    dates.push(`${y}-${m}-${d}`);
    cursor.setDate(cursor.getDate() + 1);
  }
  return dates;
}

function buildDailyMap(invoices) {
  // Zlicza wyłącznie faktury w PLN, pomijając odrzucone.
  const map = {};
  for (const inv of invoices) {
    if ((inv.status ?? '') === 'rejected') continue;
    const d = (inv.issue_date ?? '').toString().slice(0, 10);
    if (!d) continue;
    const currency = (inv.currency ?? 'PLN').toUpperCase();
    if (currency !== 'PLN') continue;
    const net = parseFloat(inv.total_net ?? 0) || 0;
    if (!net) continue;
    map[d] = (map[d] ?? 0) + net;
  }
  return map;
}

function buildXAxisTicks(data, maxTicks = 12) {
  if (!Array.isArray(data) || data.length === 0) return [];
  if (data.length <= maxTicks) return data.map((d) => d.fullDate);

  const ticks = [];
  const lastIndex = data.length - 1;
  const segments = Math.max(1, maxTicks - 1);

  for (let i = 0; i <= segments; i += 1) {
    const idx = Math.round((i * lastIndex) / segments);
    ticks.push(data[idx].fullDate);
  }

  return [...new Set(ticks)];
}

function formatXAxisTick(fullDate, firstFullDate, lastFullDate, spansMultipleMonths) {
  if (!fullDate || typeof fullDate !== 'string') return '';

  const day = fullDate.slice(8, 10);
  const month = fullDate.slice(5, 7);
  if (spansMultipleMonths && (fullDate === firstFullDate || fullDate === lastFullDate)) {
    return `${day}.${month}`;
  }
  return day;
}

function buildCombinedData(saleMap, purchaseMap, fromDate, toDate) {
  const allDays = buildDateRange(fromDate, toDate);
  let cumSale = 0;
  let cumPurchase = 0;
  return allDays.map((date) => {
    cumSale     = +(cumSale     + (saleMap[date]     ?? 0)).toFixed(2);
    cumPurchase = +(cumPurchase + (purchaseMap[date] ?? 0)).toFixed(2);
    return {
      date:         date.slice(8, 10),
      fullDate:     date,
      cumSale,
      cumPurchase,
      dailySale:     +((saleMap[date]     ?? 0).toFixed(2)),
      dailyPurchase: +((purchaseMap[date] ?? 0).toFixed(2)),
    };
  });
}

// ---- tooltip łączony ----
function CombinedTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const pt = payload[0].payload;
  const formatDaily = (value) => {
    const num = Number(value || 0);
    if (num === 0) return '0,00';
    return `${num > 0 ? '+' : ''}${num.toLocaleString('pl-PL', { minimumFractionDigits: 2 })}`;
  };

  const saleDeltaClass = pt.dailySale === 0 ? styles.tooltipDeltaNeutral : styles.tooltipDeltaSale;
  const purchaseDeltaClass = pt.dailyPurchase === 0 ? styles.tooltipDeltaNeutral : styles.tooltipDeltaPurchase;

  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipDate}>do dnia {toSlashDate(pt.fullDate)} Netto:</div>
      <div className={styles.tooltipValue}>
        Sprzedaż: {pt.cumSale.toLocaleString('pl-PL', { minimumFractionDigits: 2 })} PLN
        <span className={`${styles.tooltipSubInline} ${saleDeltaClass}`}> ({formatDaily(pt.dailySale)})</span>
      </div>
      <div className={styles.tooltipValueBlue}>
        Zakupy: {pt.cumPurchase.toLocaleString('pl-PL', { minimumFractionDigits: 2 })} PLN
        <span className={`${styles.tooltipSubInline} ${purchaseDeltaClass}`}> ({formatDaily(pt.dailyPurchase)})</span>
      </div>
    </div>
  );
}

// Mapowanie wartości filtrów na etykiety po polsku
const STATUS_LABELS = {
  ready_for_submission:  'gotowa',
  sending:               'wysyłanie',
  accepted:              'zaakceptowana',
  rejected:              'odrzucona',
};

export default function DashboardSummary({ filters }) {

  // Jeden atomowy stan wykresu — eliminuje race-condition między
  // setAllSale/setAllPurchase (.then) a setChartLoading (.finally)
  const [chart, setChart] = useState({
    loading:         true,
    saleInvoices:    [],
    purchaseInvoices: [],
  });

  // Wyznacz prefix miesiąca z filtrów lub bieżący miesiąc
  // Zakres dat z pola miesiąca (fallback na bieżący miesiąc)
  const prefix    = filters?.month || currentMonthPrefix();
  const monthFrom = `${prefix}-01`;
  const monthTo   = (() => {
    const [y, m] = prefix.split('-').map(Number);
    const last = new Date(y, m, 0).getDate();
    return `${prefix}-${String(last).padStart(2, '0')}`;
  })();

  // Ręczny zakres dat (nadpisuje miesiąc)
  const dateFrom        = filters?.issue_date_from || '';
  const dateTo          = filters?.issue_date_to   || '';
  const contractor = (filters?.contractor || '').trim();
  const contractorFilter = contractor.length >= 3 ? contractor : '';
  const dateRangeActive = !!(dateFrom || dateTo);
  const useImplicitMonthRange = !dateRangeActive && !contractorFilter;

  // Efektywny zakres dat do fetchowania
  const effectFrom = useImplicitMonthRange ? monthFrom : dateFrom;
  const effectTo   = useImplicitMonthRange ? monthTo   : dateTo;

  // Etykieta okresu do prawego górnego rogu
  const periodLabel = `${toSlashDate(effectFrom)} - ${toSlashDate(effectTo)}`;

  // Etykieta opcji (status + kontrahent)
  const optsLabel = [
    filters?.status     ? (STATUS_LABELS[filters.status] || filters.status) : '',
    filters?.contractor || '',
  ].filter(Boolean).join(', ');

  // Dane wykresu — efektywny zakres + aktywne filtry
  const status     = filters?.status     || '';
  useEffect(() => {
    let cancelled = false;
    setChart(prev => ({ ...prev, loading: true }));

    const baseParams = {
      size: 100, page: 1,
      issue_date_from: effectFrom,
      issue_date_to:   effectTo,
      ...(status     && { status }),
      ...(contractorFilter && { number_filter: contractorFilter }),
    };

    Promise.all([
      invoicesApi.list({ ...baseParams, direction: 'sale'     }),
      invoicesApi.list({ ...baseParams, direction: 'purchase' }),
    ])
      .then(([saleRes, purchaseRes]) => {
        if (cancelled) return;
        const sales     = saleRes.items     ?? [];
        const purchases = purchaseRes.items ?? [];

        // Jeden setState = jeden render, brak race-condition
        setChart({ loading: false, saleInvoices: sales, purchaseInvoices: purchases });
      })
      .catch(() => {
        if (!cancelled)
          setChart({ loading: false, saleInvoices: [], purchaseInvoices: [] });
      });
    return () => { cancelled = true; };
  }, [effectFrom, effectTo, status, contractorFilter]);

  const combinedData = useMemo(() => {
    const saleMap     = buildDailyMap(chart.saleInvoices);
    const purchaseMap = buildDailyMap(chart.purchaseInvoices);
    return buildCombinedData(saleMap, purchaseMap, effectFrom, effectTo);
  }, [chart.saleInvoices, chart.purchaseInvoices, effectFrom, effectTo]);

  const xAxisTicks = useMemo(() => buildXAxisTicks(combinedData, 12), [combinedData]);
  const firstFullDate = combinedData[0]?.fullDate ?? '';
  const lastFullDate = combinedData[combinedData.length - 1]?.fullDate ?? '';
  const spansMultipleMonths =
    firstFullDate && lastFullDate && firstFullDate.slice(0, 7) !== lastFullDate.slice(0, 7);

  const saleSummary     = useMemo(() => buildPlnSummary(chart.saleInvoices),     [chart.saleInvoices]);
  const purchaseSummary = useMemo(() => buildPlnSummary(chart.purchaseInvoices), [chart.purchaseInvoices]);

  return (
    <div className={styles.root}>
      {/* ---- Wykres narastający sprzedaż vs zakupy ---- */}
      <div className={styles.chartWrap}>
        <div className={styles.chartHeader}>
          <h3 className={styles.chartTitle}>
            Sprzedaż i zakupy narastająco (Netto)
          </h3>
          <div className={styles.chartCorner}>
            <span className={styles.chartTopLine}>
              <span className={styles.periodPrefix}>wybrany okres: </span>
              <span className={styles.periodAccent}>{periodLabel}</span>
            </span>
            {optsLabel && (
              <span className={styles.wybranoLabel}>wybrane opcje: {optsLabel}</span>
            )}
          </div>
        </div>
        {chart.loading ? (
          <div className={styles.chartEmpty}><span className="spinner" /></div>
        ) : combinedData.length === 0 ? (
          <div className={styles.chartEmpty}>Brak faktur w wybranym okresie</div>
        ) : (
          <div className={styles.chartInner}>
            <ResponsiveContainer width="100%" height={175}>
              <AreaChart data={combinedData} margin={{ top: 8, right: 24, bottom: 0, left: 8 }}>
                <defs>
                  <linearGradient id="gradSale" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#d4a017" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#d4a017" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradPurchase" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.20} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#2e2e2e" strokeDasharray="4 4" vertical={false} />
                <XAxis
                  dataKey="fullDate"
                  ticks={xAxisTicks}
                  tickFormatter={(value) => formatXAxisTick(value, firstFullDate, lastFullDate, spansMultipleMonths)}
                  tick={{ fill: '#a0a0a0', fontSize: 12 }}
                  axisLine={{ stroke: '#2e2e2e' }}
                  tickLine={false}
                  interval={0}
                />
                <YAxis
                  tick={{ fill: '#a0a0a0', fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v) => v.toLocaleString('pl-PL')}
                  width={72}
                />
                <Tooltip
                  content={<CombinedTooltip />}
                  cursor={{ stroke: '#555', strokeWidth: 1, strokeDasharray: '4 4' }}
                />
                <Area
                  type="monotone"
                  dataKey="cumSale"
                  name="Sprzedaż"
                  stroke="#d4a017"
                  strokeWidth={2}
                  fill="url(#gradSale)"
                  dot={{ r: 5, fill: '#be9015', strokeWidth: 0 }}
                  activeDot={{ r: 7, fill: '#be9015', strokeWidth: 0 }}
                  isAnimationActive={false}
                />
                <Area
                  type="monotone"
                  dataKey="cumPurchase"
                  name="Zakupy"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  fill="url(#gradPurchase)"
                  dot={{ r: 5, fill: '#3575dd', strokeWidth: 0 }}
                  activeDot={{ r: 7, fill: '#3575dd', strokeWidth: 0 }}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
        {!chart.loading && (
          <div className={styles.summaryWrap}>
            <div className={styles.summaryHeading}>W wybranym okresie:</div>
            <div className={styles.summaryBar}>
              <span className={styles.summarySale}>SPRZEDAŻ</span>
              {' — '}
              <span className={styles.summaryNetLabel}>Netto:</span>
              {' '}
              <span className={`${styles.summaryValue} ${styles.summaryValueBold} ${styles.summaryNetValueSale}`}>{fmtPln(saleSummary.netto)}</span>
              {' | '}
              <span className={styles.summarySecondaryLabel}>VAT:</span>
              {' '}
              <span className={`${styles.summaryValue} ${styles.summarySecondaryValue}`}>{fmtPln(saleSummary.vat)}</span>
              {' | '}
              <span className={styles.summarySecondaryLabel}>Brutto:</span>
              {' '}
              <span className={`${styles.summaryValue} ${styles.summarySecondaryValue}`}>{fmtPln(saleSummary.brutto)}</span>
              {' / '}
              <span className={styles.summaryPurchase}>ZAKUP</span>
              {' — '}
              <span className={styles.summaryNetLabel}>Netto:</span>
              {' '}
              <span className={`${styles.summaryValue} ${styles.summaryValueBold} ${styles.summaryNetValuePurchase}`}>{fmtPln(purchaseSummary.netto)}</span>
              {' | '}
              <span className={styles.summarySecondaryLabel}>VAT:</span>
              {' '}
              <span className={`${styles.summaryValue} ${styles.summarySecondaryValue}`}>{fmtPln(purchaseSummary.vat)}</span>
              {' | '}
              <span className={styles.summarySecondaryLabel}>Brutto:</span>
              {' '}
              <span className={`${styles.summaryValue} ${styles.summarySecondaryValue}`}>{fmtPln(purchaseSummary.brutto)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
