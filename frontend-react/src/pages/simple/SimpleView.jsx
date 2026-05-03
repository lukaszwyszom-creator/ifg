import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { invoicesApi } from '../../api/invoices';
import { useAppStore } from '../../store/useAppStore';
import { buildInvoicePoolKey, buildInvoicePoolQuery } from '../../components/dashboard/dashboardQuery';
import InvoiceForm from '../../components/invoice/InvoiceForm';
import InvoiceList from '../../components/invoice/InvoiceList';
import styles from './SimpleView.module.css';

const GROSS_FIELDS = ['total_gross', 'gross_total', 'amount_gross'];
const NET_FIELDS = ['total_net', 'net_total', 'amount_net'];
const VAT_FIELDS = ['total_vat', 'vat_total', 'amount_vat'];

const currentMonthKey = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
};

const MONTH_LABELS = [
  'styczeń', 'luty', 'marzec', 'kwiecień', 'maj', 'czerwiec',
  'lipiec', 'sierpień', 'wrzesień', 'październik', 'listopad', 'grudzień',
];

const MONTH_LABELS_LOCATIVE = [
  'styczniu', 'lutym', 'marcu', 'kwietniu', 'maju', 'czerwcu',
  'lipcu', 'sierpniu', 'wrześniu', 'październiku', 'listopadzie', 'grudniu',
];

const isMonthKey = (value) => /^\d{4}-\d{2}$/.test(String(value || ''));

const formatMonthYearLocative = (monthKey) => {
  const [yearRaw, monthRaw] = String(monthKey).split('-');
  const year = Number(yearRaw);
  const monthIdx = Number(monthRaw) - 1;
  const monthName = MONTH_LABELS_LOCATIVE[monthIdx] ?? '';
  return `${monthName} ${year}`.trim();
};

const toNumber = (value) => {
  if (value === null || value === undefined || value === '') return null;
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
};

const resolveAmount = (invoice, fields) => {
  for (const field of fields) {
    const value = toNumber(invoice?.[field]);
    if (value !== null) return value;
  }
  return null;
};

const formatPln = (amount) => `${new Intl.NumberFormat('pl-PL', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
}).format(amount)} PLN`;

const calculateStrictSum = (invoices, fields) => {
  let total = 0;
  for (const invoice of invoices) {
    const value = resolveAmount(invoice, fields);
    if (value === null) {
      return { available: false, value: null };
    }
    total += value;
  }
  return { available: true, value: total };
};

export default function SimpleView() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialMonthFromUrl = searchParams.get('month');
  const [selectedMonth, setSelectedMonth] = useState(
    isMonthKey(initialMonthFromUrl) ? initialMonthFromUrl : currentMonthKey()
  );
  const [monthsWithData, setMonthsWithData] = useState(() => new Set());
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [activeInvoice, setActiveInvoice] = useState(null);
  const [activeMode, setActiveMode] = useState('preview');
  const [previewHtml, setPreviewHtml] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  const loadInvoicePool = useAppStore((s) => s.loadInvoicePool);
  const refreshAllInvoicePools = useAppStore((s) => s.refreshAllInvoicePools);

  const selectedYear = Number(String(selectedMonth).slice(0, 4)) || new Date().getFullYear();
  const yearFilters = useMemo(() => ({
    issue_date_from: `${selectedYear}-01-01`,
    issue_date_to: `${selectedYear}-12-31`,
  }), [selectedYear]);
  const yearQuery = useMemo(
    () => buildInvoicePoolQuery(yearFilters, 'sale', { defaultToCurrentMonth: false }),
    [yearFilters]
  );
  const yearPoolKey = useMemo(() => buildInvoicePoolKey(yearQuery), [yearQuery]);
  const yearPoolEntry = useAppStore((s) => s.invoicePool?.sale?.[yearPoolKey]);
  const yearPoolItems = useMemo(
    () => (Array.isArray(yearPoolEntry?.items) ? yearPoolEntry.items : []),
    [yearPoolEntry]
  );

  useEffect(() => {
    loadInvoicePool({ direction: 'sale', filters: yearFilters, options: { defaultToCurrentMonth: false } }).catch(() => null);
  }, [loadInvoicePool, yearPoolKey, yearFilters]);

  const handleMonthSelect = useCallback((monthKey) => {
    setSelectedMonth(monthKey);
    const next = new URLSearchParams(window.location.search);
    next.set('month', monthKey);
    setSearchParams(next, { replace: true });
  }, [setSearchParams]);

  useEffect(() => {
    const months = new Set();
    for (const inv of yearPoolItems) {
      const key = String(inv?.issue_date || '').slice(0, 7);
      if (isMonthKey(key)) months.add(key);
    }
    setMonthsWithData(months);
  }, [yearPoolItems]);

  const monthInvoices = useMemo(() => {
    const month = String(selectedMonth);
    return yearPoolItems.filter((inv) => String(inv?.issue_date || '').slice(0, 7) === month);
  }, [yearPoolItems, selectedMonth]);

  const monthlySummary = useMemo(() => {
    // Dodatkowy guard UI: podsumowanie liczymy tylko z wybranego miesiąca.
    // Chroni przed ewentualnymi starymi danymi w buforze listy.

    const gross = calculateStrictSum(monthInvoices, GROSS_FIELDS);
    const net = calculateStrictSum(monthInvoices, NET_FIELDS);
    const vat = calculateStrictSum(monthInvoices, VAT_FIELDS);

    const missing = [];
    if (!net.available) missing.push(`netto: ${NET_FIELDS.join(', ')}`);
    if (!vat.available) missing.push(`VAT: ${VAT_FIELDS.join(', ')}`);

    return {
      gross,
      net,
      vat,
      missing,
    };
  }, [monthInvoices]);

  const selectedMonthLocative = useMemo(
    () => formatMonthYearLocative(selectedMonth),
    [selectedMonth]
  );

  const saleMonthFilters = useMemo(
    () => ({ month: selectedMonth }),
    [selectedMonth]
  );

  const monthOptions = useMemo(() => {
    const year = selectedYear;
    return MONTH_LABELS.map((label, idx) => {
      const month = String(idx + 1).padStart(2, '0');
      const key = `${year}-${month}`;
      return {
        key,
        label,
        hasData: monthsWithData.has(key),
      };
    });
  }, [monthsWithData, selectedYear]);

  const netText = monthlySummary.net.available ? formatPln(monthlySummary.net.value) : '—';
  const vatText = monthlySummary.vat.available ? formatPln(monthlySummary.vat.value) : '—';
  const grossText = monthlySummary.gross.available ? formatPln(monthlySummary.gross.value) : '—';

  const handleCreate = async (payload) => {
    setSaving(true);
    try {
      const inv = await invoicesApi.create(payload);
      await refreshAllInvoicePools({ force: true });
      setSaved(inv);
      setShowForm(false);
      setRefreshKey((k) => k + 1);
    } finally {
      setSaving(false);
    }
  };

  const handleOpenInvoice = useCallback(async (invoice, mode) => {
    setSaved(null);
    setShowForm(false);
    setActiveInvoice(invoice);
    setActiveMode(mode);
    setPreviewHtml('');

    if (mode === 'preview') {
      setPreviewLoading(true);
      try {
        const html = await invoicesApi.getPreview(invoice.id);
        setPreviewHtml(html);
      } finally {
        setPreviewLoading(false);
      }
    }
  }, []);

  const handleCloseActive = useCallback(() => {
    setActiveInvoice(null);
    setPreviewHtml('');
    setActiveMode('preview');
  }, []);

  const handleUpdate = async (payload) => {
    if (!activeInvoice) return;
    setSaving(true);
    try {
      const updated = await invoicesApi.update(activeInvoice.id, payload);
      await refreshAllInvoicePools({ force: true });
      setSaved(updated);
      setActiveInvoice(null);
      setRefreshKey((k) => k + 1);
    } finally {
      setSaving(false);
    }
  };

  const handleDownloadPdf = async () => {
    if (!activeInvoice) return;
    setPdfLoading(true);
    try {
      const arrayBuffer = await invoicesApi.getPdf(activeInvoice.id);
      const blob = new Blob([arrayBuffer], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `faktura-${activeInvoice.number_local || activeInvoice.id}.pdf`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    } finally {
      setPdfLoading(false);
    }
  };

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.monthPills}>
          {monthOptions.map((opt) => {
            const active = opt.key === selectedMonth;
            const cls = [
              styles.monthPill,
              active ? styles.monthPillActive : '',
              !opt.hasData ? styles.monthPillEmpty : '',
            ].join(' ').trim();

            return (
              <button
                key={opt.key}
                type="button"
                className={cls}
                onClick={() => handleMonthSelect(opt.key)}
              >
                {opt.label}
              </button>
            );
          })}
        </div>

        <div className={styles.summaryRow}>
          <div className={styles.monthSummary}>
            <span className={styles.monthSummaryTitleMain}>Suma sprzedaży wybranego miesiąca:</span>
            <span className={styles.monthSummaryLabel}>Netto:</span>{' '}
            <span className={`${styles.monthSummaryValue} ${styles.monthSummaryValueStrong}`}>{netText}</span>
            <span className={styles.monthSummarySeparator}> | </span>
            <span className={styles.monthSummaryLabel}>VAT:</span>{' '}
            <span className={styles.monthSummaryValue}>{vatText}</span>
            <span className={styles.monthSummarySeparator}> | </span>
            <span className={styles.monthSummaryLabel}>Brutto:</span>{' '}
            <span className={styles.monthSummaryValue}>{grossText}</span>
            {monthlySummary.missing.length > 0 && (
              <>
                <span className={styles.monthSummarySeparator}> | </span>
                <span className={styles.monthSummaryMissing}>
                  brak pól: {monthlySummary.missing.join('; ')}
                </span>
              </>
            )}
          </div>

          <button
            className={`btn btn-primary ${styles.newInvoiceBtn}`}
            onClick={() => { setShowForm((v) => !v); setSaved(null); }}
          >
            {showForm ? '✕ Anuluj' : '+ Nowa faktura'}
          </button>
        </div>
      </div>

      {/* Komunikat o sukcesie */}
      {saved && !showForm && (
        <div className="alert alert-success">
          Faktura <strong>{saved.number_local ?? saved.id.slice(0, 8)}</strong> zapisana
          i gotowa do wysyłki.
        </div>
      )}

      {/* Formularz */}
      {showForm && (
        <div className={styles.formWrap}>
          <InvoiceForm onSubmit={handleCreate} loading={saving} />
        </div>
      )}

      {/* Lista faktur */}
      {!showForm && (
        <div className={styles.section}>
          <InvoiceList
            key={`${refreshKey}-${selectedMonth}`}
            limit={10}
            hidePager
            filters={saleMonthFilters}
            sourceItems={monthInvoices}
            emptyMsg={`Brak faktur sprzedaży w ${selectedMonthLocative}`}
            onOpenInvoice={handleOpenInvoice}
          />
        </div>
      )}

      {!!activeInvoice && (
        <div className={styles.formWrap}>
          <div className={styles.header}>
            <div className={styles.sub}>
              {activeMode === 'edit' ? 'Edycja faktury' : 'Podgląd faktury'}
            </div>
            <button className="btn btn-ghost" onClick={handleCloseActive}>Zamknij</button>
          </div>

          {activeMode === 'edit' ? (
            <InvoiceForm initial={activeInvoice} onSubmit={handleUpdate} loading={saving} />
          ) : (
            <div className={styles.section}>
              <div className={styles.sub}>Status: W toku / zaakceptowana – edycja zablokowana</div>
              <div className={styles.header}>
                <button
                  className="btn btn-primary"
                  onClick={handleDownloadPdf}
                  disabled={pdfLoading}
                >
                  {pdfLoading ? 'Pobieranie PDF...' : 'Pobierz PDF'}
                </button>
              </div>

              {previewLoading ? (
                <div className={styles.sub}>Ładowanie podglądu...</div>
              ) : (
                <iframe
                  title="Podgląd faktury"
                  srcDoc={previewHtml}
                  style={{ width: '100%', minHeight: 520, border: '1px solid var(--color-border)' }}
                />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
