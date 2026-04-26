import React, { useState } from 'react';
import { invoicesApi } from '../../api/invoices';
import InvoiceActions from './InvoiceActions';
import styles from './InvoiceCardList.module.css';

const COLUMN_LABELS = [
  'Numer',
  'Data',
  'Nabywca',
  'Brutto',
  'Termin',
  'Pozostało',
  'Status KSeF',
  'PDF',
];

const DIRECT_REMAINING_FIELDS = [
  'remaining_amount',
  'amount_remaining',
  'unpaid_amount',
  'balance_due',
  'outstanding_amount',
  'payment_remaining',
];

const GROSS_FIELDS = ['gross_total', 'total_gross', 'amount_gross'];
const PAID_FIELDS = ['paid_amount'];

const DEFAULT_MONTH = '01';
const DEFAULT_YEAR = '1970';

const pad2 = (num) => String(num).padStart(2, '0');

const toAmount = (value) => {
  if (value === null || value === undefined || value === '') return null;
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
};

const resolveFieldAmount = (invoice, fields) => {
  for (const field of fields) {
    const amount = toAmount(invoice[field]);
    if (amount !== null) {
      return { amount, source: field };
    }
  }
  return null;
};

const getIssueDateParts = (invoice) => {
  const issue = String(invoice.issue_date || '').trim();
  const iso = issue.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (iso) {
    return { year: iso[1], month: iso[2] };
  }

  const parsedDate = new Date(issue);
  if (!Number.isNaN(parsedDate.getTime())) {
    return {
      year: String(parsedDate.getFullYear()),
      month: pad2(parsedDate.getMonth() + 1),
    };
  }

  return { year: DEFAULT_YEAR, month: DEFAULT_MONTH };
};

const parseBackendNumber = (numberLocal) => {
  if (!numberLocal) return null;
  const normalized = String(numberLocal).replace(/^FV\//i, '').trim();
  const parts = normalized.split('/');
  if (parts.length < 3) return null;

  const seq = Number(parts[0]);
  const month = String(parts[1]).padStart(2, '0');
  const year = String(parts[2]);

  if (!Number.isFinite(seq) || seq <= 0) return null;
  if (!/^\d{2}$/.test(month) || !/^\d{4}$/.test(year)) return null;

  return { seq, month, year };
};

const getRemainingAmountInfo = (invoice) => {
  const directRemaining = resolveFieldAmount(invoice, DIRECT_REMAINING_FIELDS);
  if (directRemaining) {
    return {
      amount: Math.max(0, directRemaining.amount),
      source: `direct:${directRemaining.source}`,
    };
  }

  const gross = resolveFieldAmount(invoice, GROSS_FIELDS);
  if (!gross) {
    return { amount: 0, source: 'missing_gross' };
  }

  const paid = resolveFieldAmount(invoice, PAID_FIELDS);
  if (paid) {
    return {
      amount: Math.max(0, gross.amount - paid.amount),
      source: `computed:${gross.source}-paid_amount`,
    };
  }

  return {
    amount: Math.max(0, gross.amount),
    source: `assumption:${gross.source}_as_remaining_no_paid_amount`,
  };
};

const formatMoney = (amount, currency) => `${amount.toFixed(2)} ${currency || 'PLN'}`;

const getGrossAmount = (invoice) => {
  const gross = resolveFieldAmount(invoice, GROSS_FIELDS);
  return gross ? gross.amount : 0;
};

/**
 * Render listy faktur jako kafelków zamiast tabeli.
 * @param {Array}       items      - faktury do wyświetlenia
 * @param {bool}        loading    - stan ładowania
 * @param {Function}    onRefresh  - callback przeładowania
 * @param {Function}    onUpdate   - callback aktualizacji pojedynczej faktury
 * @param {string}      emptyMsg   - wiadomość gdy brak danych
 */
export default function InvoiceCardList({
  items = [],
  loading = false,
  onRefresh,
  onUpdate,
  emptyMsg = 'Brak faktur',
}) {
  const [pdfLoadingId, setPdfLoadingId] = useState(null);

  const preparedItems = React.useMemo(() => {
    const entries = items.map((invoice, idx) => {
      const dateTs = Number.isNaN(new Date(invoice.issue_date).getTime())
        ? Number.MAX_SAFE_INTEGER
        : new Date(invoice.issue_date).getTime();
      const backendNumber = parseBackendNumber(invoice.number_local);
      const issueParts = getIssueDateParts(invoice);
      const month = backendNumber?.month ?? issueParts.month;
      const year = backendNumber?.year ?? issueParts.year;

      return {
        invoice,
        idx,
        dateTs,
        month,
        year,
        backendSeq: backendNumber?.seq ?? null,
      };
    });

    const groups = new Map();
    for (const entry of entries) {
      const groupKey = `${entry.year}-${entry.month}`;
      if (!groups.has(groupKey)) groups.set(groupKey, []);
      groups.get(groupKey).push(entry);
    }

    const groupKeys = Array.from(groups.keys()).sort();
    const result = [];

    for (const groupKey of groupKeys) {
      const group = groups.get(groupKey) || [];
      group.sort((a, b) => {
        if (a.dateTs !== b.dateTs) return a.dateTs - b.dateTs;
        return a.idx - b.idx;
      });

      const used = new Set(group.filter((e) => e.backendSeq !== null).map((e) => e.backendSeq));
      let nextSeq = 1;
      const withDisplay = group.map((entry) => {
        let sequence = entry.backendSeq;
        let numberSource = 'backend:number_local';

        if (sequence === null) {
          while (used.has(nextSeq)) nextSeq += 1;
          sequence = nextSeq;
          used.add(sequence);
          nextSeq += 1;
          numberSource = 'ui:temporary_sequence';
        }

        return {
          ...entry,
          sequence,
          numberSource,
          displayNumber: `${pad2(sequence)}/${entry.month}/${entry.year}`,
        };
      });

      withDisplay.sort((a, b) => {
        if (a.sequence !== b.sequence) return a.sequence - b.sequence;
        if (a.dateTs !== b.dateTs) return a.dateTs - b.dateTs;
        return a.idx - b.idx;
      });

      result.push(...withDisplay);
    }

    return result;
  }, [items]);

  const getPaymentTermLabel = (invoice) => {
    const raw =
      invoice.payment_terms_days ??
      invoice.payment_terms ??
      invoice.payment_days ??
      invoice.days_to_payment ??
      invoice.days ??
      invoice.buyer_snapshot?.payment_terms_days ??
      invoice.buyer_snapshot?.payment_terms ??
      null;

    if (raw === null || raw === undefined || raw === '') return '—';

    if (typeof raw === 'number' && Number.isFinite(raw)) {
      return `${raw} dni`;
    }

    const asText = String(raw).trim();
    if (!asText) return '—';
    if (/^\d+$/.test(asText)) return `${asText} dni`;
    return asText;
  };

  // Download PDF
  const handleDownloadPdf = async (e, invoice) => {
    e.stopPropagation();
    setPdfLoadingId(invoice.id);
    try {
      const arrayBuffer = await invoicesApi.getPdf(invoice.id);
      const blob = new Blob([arrayBuffer], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `faktura-${invoice.number_local || invoice.id}.pdf`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    } catch (err) {
      console.error('Błąd generowania PDF:', err);
    } finally {
      setPdfLoadingId(null);
    }
  };

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loadingState}>
          <span className="spinner" />
        </div>
      </div>
    );
  }

  if (!preparedItems.length) {
    return (
      <div className={styles.container}>
        <div className={styles.emptyState}>{emptyMsg}</div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.headerRow}>
        {COLUMN_LABELS.map((label) => (
          <div key={label} className={styles.headerCell}>
            {label}
          </div>
        ))}
      </div>

      <div className={styles.scrollArea}>
        {preparedItems.map((item) => {
          const invoice = item.invoice;
          const grossAmount = getGrossAmount(invoice);

          return (
            <div key={invoice.id} className={styles.card}>
              {/* TODO: enable row navigation when invoice detail/edit routes are implemented */}
              <div className={styles.cardContent}>
                <div className={styles.cell}>
                  <span className={styles.label}>Numer</span>
                  <span className={styles.value} title={`Źródło numeru: ${item.numberSource}`}>
                    {item.displayNumber}
                  </span>
                </div>

                <div className={styles.cell}>
                  <span className={styles.label}>Data</span>
                  <span className={styles.value}>{invoice.issue_date}</span>
                </div>

                <div className={styles.cell}>
                  <span className={styles.label}>Nabywca</span>
                  <span className={`${styles.value} ${styles.buyerValue}`}>
                    {invoice.buyer_snapshot?.name ?? '—'}
                  </span>
                </div>

                <div className={styles.cell}>
                  <span className={styles.label}>Brutto</span>
                  <span className={styles.value}>
                    {formatMoney(grossAmount, invoice.currency)}
                  </span>
                </div>

                <div className={styles.cell}>
                  <span className={styles.label}>Termin</span>
                  <span className={styles.value}>{getPaymentTermLabel(invoice)}</span>
                </div>

                <div className={styles.cell}>
                  <span className={styles.label}>Pozostało</span>
                  {(() => {
                    const remaining = getRemainingAmountInfo(invoice);
                    if (remaining.amount > 0) {
                      return (
                        <span
                          className={`${styles.value} ${styles.remainingAmountDue}`}
                          title={`Źródło: ${remaining.source}`}
                        >
                          {formatMoney(remaining.amount, invoice.currency)}
                        </span>
                      );
                    }

                    return <span className={`${styles.value} ${styles.remainingAmountZero}`}>-,--</span>;
                  })()}
                </div>

                <div className={`${styles.cell} ${styles.ksefCell}`}>
                  <span className={styles.label}>Status KSeF</span>
                  <InvoiceActions invoice={invoice} onRefresh={onRefresh} onUpdate={onUpdate} />
                </div>

                <div className={`${styles.cell} ${styles.pdfCell}`}>
                  <span className={styles.label}>PDF</span>
                  <button
                    className={`btn btn-sm ${styles.pdfButton}`}
                    disabled={pdfLoadingId === invoice.id}
                    onClick={(e) => handleDownloadPdf(e, invoice)}
                    title="Pobierz PDF"
                  >
                    {pdfLoadingId === invoice.id ? (
                      <span className="spinner" style={{ width: 12, height: 12 }} />
                    ) : (
                      'PDF ↓'
                    )}
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
