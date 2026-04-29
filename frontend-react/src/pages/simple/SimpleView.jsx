import { useCallback, useMemo, useState } from 'react';
import { invoicesApi } from '../../api/invoices';
import InvoiceForm from '../../components/invoice/InvoiceForm';
import InvoiceList from '../../components/invoice/InvoiceList';
import styles from './SimpleView.module.css';

const EMPTY_FILTERS = Object.freeze({});
const GROSS_FIELDS = ['total_gross', 'gross_total', 'amount_gross'];
const NET_FIELDS = ['total_net', 'net_total', 'amount_net'];
const VAT_FIELDS = ['total_vat', 'vat_total', 'amount_vat'];

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

const toMonthKey = (dateValue) => {
  const parsed = new Date(dateValue);
  if (Number.isNaN(parsed.getTime())) return null;
  return `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, '0')}`;
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
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [visibleInvoices, setVisibleInvoices] = useState([]);
  const [activeInvoice, setActiveInvoice] = useState(null);
  const [activeMode, setActiveMode] = useState('preview');
  const [previewHtml, setPreviewHtml] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);

  const handleItemsChange = useCallback((items) => {
    setVisibleInvoices(Array.isArray(items) ? items : []);
  }, []);

  const monthlySummary = useMemo(() => {
    const currentMonth = toMonthKey(new Date());
    const monthInvoices = visibleInvoices.filter((invoice) => toMonthKey(invoice.issue_date) === currentMonth);

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
  }, [visibleInvoices]);

  const netText = monthlySummary.net.available ? formatPln(monthlySummary.net.value) : '—';
  const vatText = monthlySummary.vat.available ? formatPln(monthlySummary.vat.value) : '—';
  const grossText = monthlySummary.gross.available ? formatPln(monthlySummary.gross.value) : '—';

  const handleCreate = async (payload) => {
    setSaving(true);
    try {
      const inv = await invoicesApi.create(payload);
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
        <div className={styles.monthSummary}>
          <span className={styles.monthSummaryPrefix}>Suma sprzedaży w miesiącu - </span>
          <span className={styles.monthSummaryLabel}>Netto:</span>{' '}
          <span className={styles.monthSummaryValue}>{netText}</span>
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
            key={refreshKey}
            limit={10}
            hidePager
            filters={EMPTY_FILTERS}
            onItemsChange={handleItemsChange}
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
              <div className={styles.sub}>Status: Analiza - edycja zablokowana</div>
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
