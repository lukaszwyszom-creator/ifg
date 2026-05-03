import { useState, useEffect, useMemo } from 'react';
import {
  AreaChart, Area,
  XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
} from 'recharts';
import { useAppStore } from '../../store/useAppStore';
import { buildPlnSummary } from './dashboardAggregation';
import { buildInvoicePoolKey, buildInvoicePoolQuery, resolveEffectiveFilters } from './dashboardQuery';
import { formatCurrencyPLN, formatSignedCurrencyPLN } from '../../utils/amountFormatting';
import styles from './DashboardSummary.module.css';

// ---- helpers ----
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
    if (num === 0) return '0,00 zł';
    return formatSignedCurrencyPLN(num);
  };

  const saleDeltaClass = pt.dailySale === 0 ? styles.tooltipDeltaNeutral : styles.tooltipDeltaSale;
  const purchaseDeltaClass = pt.dailyPurchase === 0 ? styles.tooltipDeltaNeutral : styles.tooltipDeltaPurchase;

  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipDate}>do dnia {toSlashDate(pt.fullDate)} Netto:</div>
      <div className={styles.tooltipValue}>
        Sprzedaż: {formatCurrencyPLN(pt.cumSale)}
        <span className={`${styles.tooltipSubInline} ${saleDeltaClass}`}> ({formatDaily(pt.dailySale)})</span>
      </div>
      <div className={styles.tooltipValueBlue}>
        Zakupy: {formatCurrencyPLN(pt.cumPurchase)}
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
  const loadInvoicePool = useAppStore((s) => s.loadInvoicePool);

  // Jeden atomowy stan wykresu — eliminuje race-condition między
  // setAllSale/setAllPurchase (.then) a setChartLoading (.finally)
  const [chartLoading, setChartLoading] = useState(true);

  // Wyznacz prefix miesiąca z filtrów lub bieżący miesiąc
  // Zakres/filtrowanie zawsze liczone wspólną logiką (spójnie z VATSummary)
  const { from: effectFrom, to: effectTo, status, contractorFilter } = resolveEffectiveFilters(filters);

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

  // Etykieta okresu do prawego górnego rogu
  const periodLabel = `${toSlashDate(effectFrom)} - ${toSlashDate(effectTo)}`;

  // Etykieta opcji (status + kontrahent)
  const optsLabel = [
    filters?.status     ? (STATUS_LABELS[filters.status] || filters.status) : '',
    filters?.contractor || '',
  ].filter(Boolean).join(', ');

  // Dane wykresu — efektywny zakres + aktywne filtry
  useEffect(() => {
    let cancelled = false;
    setChartLoading(true);

    Promise.all([
      loadInvoicePool({ direction: 'sale', filters, options: { defaultToCurrentMonth: true } }),
      loadInvoicePool({ direction: 'purchase', filters, options: { defaultToCurrentMonth: true } }),
    ])
      .catch(() => null)
      .finally(() => {
        if (!cancelled) setChartLoading(false);
      });
    return () => { cancelled = true; };
  }, [loadInvoicePool, effectFrom, effectTo, status, contractorFilter, filters, salePoolKey, purchasePoolKey]);

  const chartBusy = chartLoading || saleLoading || purchaseLoading;

  const combinedData = useMemo(() => {
    const saleMap     = buildDailyMap(saleInvoices);
    const purchaseMap = buildDailyMap(purchaseInvoices);
    return buildCombinedData(saleMap, purchaseMap, effectFrom, effectTo);
  }, [saleInvoices, purchaseInvoices, effectFrom, effectTo]);

  const xAxisTicks = useMemo(() => buildXAxisTicks(combinedData, 12), [combinedData]);
  const firstFullDate = combinedData[0]?.fullDate ?? '';
  const lastFullDate = combinedData[combinedData.length - 1]?.fullDate ?? '';
  const spansMultipleMonths =
    firstFullDate && lastFullDate && firstFullDate.slice(0, 7) !== lastFullDate.slice(0, 7);

  const saleSummary     = useMemo(() => buildPlnSummary(saleInvoices),     [saleInvoices]);
  const purchaseSummary = useMemo(() => buildPlnSummary(purchaseInvoices), [purchaseInvoices]);

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
        {chartBusy ? (
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
        {!chartBusy && (
          <div className={styles.summaryWrap}>
            <div className={styles.summaryHeading}>W wybranym okresie:</div>
            <div className={styles.summaryBar}>
              <span className={styles.summarySale}>SPRZEDAŻ</span>
              {' — '}
              <span className={styles.summaryNetLabel}>Netto:</span>
              {' '}
              <span className={`${styles.summaryValue} ${styles.summaryValueBold} ${styles.summaryNetValueSale}`}>{formatCurrencyPLN(saleSummary.netto)}</span>
              {' | '}
              <span className={styles.summarySecondaryLabel}>VAT:</span>
              {' '}
              <span className={`${styles.summaryValue} ${styles.summarySecondaryValue}`}>{formatCurrencyPLN(saleSummary.vat)}</span>
              {' | '}
              <span className={styles.summarySecondaryLabel}>Brutto:</span>
              {' '}
              <span className={`${styles.summaryValue} ${styles.summarySecondaryValue}`}>{formatCurrencyPLN(saleSummary.brutto)}</span>
              {' / '}
              <span className={styles.summaryPurchase}>ZAKUP</span>
              {' — '}
              <span className={styles.summaryNetLabel}>Netto:</span>
              {' '}
              <span className={`${styles.summaryValue} ${styles.summaryValueBold} ${styles.summaryNetValuePurchase}`}>{formatCurrencyPLN(purchaseSummary.netto)}</span>
              {' | '}
              <span className={styles.summarySecondaryLabel}>VAT:</span>
              {' '}
              <span className={`${styles.summaryValue} ${styles.summarySecondaryValue}`}>{formatCurrencyPLN(purchaseSummary.vat)}</span>
              {' | '}
              <span className={styles.summarySecondaryLabel}>Brutto:</span>
              {' '}
              <span className={`${styles.summaryValue} ${styles.summarySecondaryValue}`}>{formatCurrencyPLN(purchaseSummary.brutto)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
