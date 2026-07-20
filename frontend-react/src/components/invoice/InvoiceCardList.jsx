import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import JSZip from 'jszip';
import { invoicesApi } from '../../api/invoices';
import { formatAmountByCurrency } from '../../utils/amountFormatting';
import InvoiceActions from './InvoiceActions';
import { getInvoiceOpenMode } from './invoiceOpenMode';
import { getPurchaseDisplayNumber } from '../../utils/purchaseInvoiceDisplay';
import { extractBuyerContactLines, formatContractorPopupTitle } from './buyerContact';
import styles from './InvoiceCardList.module.css';

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

const formatMoney = (amount, currency) => formatAmountByCurrency(amount, currency);

const formatDateDDMMYYYY = (dateStr) => {
  if (!dateStr) return '—';
  const iso = String(dateStr).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (iso) {
    return `${iso[3]}-${iso[2]}-${iso[1]}`;
  }
  const parsed = new Date(dateStr);
  if (!Number.isNaN(parsed.getTime())) {
    return `${pad2(parsed.getDate())}-${pad2(parsed.getMonth() + 1)}-${parsed.getFullYear()}`;
  }
  return '—';
};

const getGrossAmount = (invoice) => {
  const gross = resolveFieldAmount(invoice, GROSS_FIELDS);
  return gross ? gross.amount : 0;
};

const getContractorName = (invoice, direction) => {
  if (direction === 'purchase') {
    return (
      invoice.seller_snapshot?.name
      ?? invoice.contractor_snapshot?.name
      ?? invoice.buyer_snapshot?.name
      ?? '—'
    );
  }
  return invoice.buyer_snapshot?.name ?? '—';
};

const getContractorNip = (invoice, direction) => {
  if (direction === 'purchase') {
    return (
      invoice.seller_snapshot?.nip
      ?? invoice.contractor_snapshot?.nip
      ?? invoice.buyer_snapshot?.nip
      ?? '—'
    );
  }
  return invoice.buyer_snapshot?.nip ?? '—';
};

/** Snapshot kontrahenta — ten sam rekord, z którego bierze się nazwę. */
const getContractorSnapshot = (invoice, direction) => {
  if (direction === 'purchase') {
    return (
      invoice.seller_snapshot
      ?? invoice.contractor_snapshot
      ?? invoice.buyer_snapshot
    );
  }
  return invoice.buyer_snapshot;
};

function ContractorNameWithPopup({ name, snapshot }) {
  const contactLines = extractBuyerContactLines(snapshot);
  const popupTitle = formatContractorPopupTitle(name, snapshot);
  const wrapRef = useRef(null);
  const hideTimerRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0, maxWidth: 360 });

  const clearHideTimer = () => {
    if (hideTimerRef.current != null) {
      clearTimeout(hideTimerRef.current);
      hideTimerRef.current = null;
    }
  };

  const updatePosition = () => {
    const el = wrapRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const maxWidth = Math.min(360, Math.max(200, window.innerWidth - 24));
    let left = rect.left;
    if (left + maxWidth > window.innerWidth - 12) {
      left = Math.max(12, window.innerWidth - maxWidth - 12);
    }
    setCoords({
      top: rect.bottom + 6,
      left,
      maxWidth,
    });
  };

  const showPopup = () => {
    clearHideTimer();
    updatePosition();
    setOpen(true);
  };

  const scheduleHide = () => {
    clearHideTimer();
    hideTimerRef.current = setTimeout(() => setOpen(false), 140);
  };

  useEffect(() => () => clearHideTimer(), []);

  useEffect(() => {
    if (!open) return undefined;
    const onScrollOrResize = () => updatePosition();
    window.addEventListener('scroll', onScrollOrResize, true);
    window.addEventListener('resize', onScrollOrResize);
    return () => {
      window.removeEventListener('scroll', onScrollOrResize, true);
      window.removeEventListener('resize', onScrollOrResize);
    };
  }, [open]);

  if (!name || name === '—') {
    return <span className={`${styles.value} ${styles.buyerValue}`}>{name || '—'}</span>;
  }

  const popup = open
    ? createPortal(
      <span
        className={`${styles.buyerPopup} ${styles.buyerPopupFixed}`}
        role="tooltip"
        data-buyer-popup="true"
        data-contractor-popup="true"
        style={{ top: coords.top, left: coords.left, maxWidth: coords.maxWidth }}
        onMouseEnter={showPopup}
        onMouseLeave={scheduleHide}
      >
        <span className={styles.buyerPopupName}>{popupTitle}</span>
        {contactLines.length > 0 ? (
          <span className={styles.buyerPopupContacts}>
            {contactLines.map((line) => (
              <span key={line} className={styles.buyerPopupContact}>{line}</span>
            ))}
          </span>
        ) : null}
      </span>,
      document.body,
    )
    : null;

  return (
    <>
      <span
        ref={wrapRef}
        className={styles.buyerHoverWrap}
        data-buyer-hover-trigger="true"
        data-contractor-hover-trigger="true"
        onMouseEnter={showPopup}
        onMouseLeave={scheduleHide}
        onFocus={showPopup}
        onBlur={scheduleHide}
      >
        <span className={`${styles.value} ${styles.buyerValue}`}>{name}</span>
      </span>
      {popup}
    </>
  );
}

/**
 * Render listy faktur jako kafelków zamiast tabeli.
 * @param {Array}       items      - faktury do wyświetlenia
 * @param {string}      direction  - 'sale' | 'purchase'
 * @param {bool}        loading    - stan ładowania
 * @param {string}      emptyMsg   - wiadomość gdy brak danych
 */
export default function InvoiceCardList({
  items = [],
  direction = 'sale',
  showKsefStatus = true,
  loading = false,
  onRefresh,
  onOpenInvoice,
  emptyMsg = 'Brak faktur',
}) {
  const [pdfLoadingId, setPdfLoadingId] = useState(null);
  const [previewLoadingId, setPreviewLoadingId] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);
  const contractorHeader = direction === 'purchase' ? 'Sprzedawca' : 'Nabywca';

  const preparedItems = React.useMemo(() => {
    if (direction === 'purchase') {
      return items
        .map((invoice, idx) => {
          const dateTs = Number.isNaN(new Date(invoice.issue_date).getTime())
            ? 0
            : new Date(invoice.issue_date).getTime();
          const { displayNumber, numberSource } = getPurchaseDisplayNumber(invoice);
          return {
            invoice,
            idx,
            dateTs,
            displayNumber,
            numberSource,
          };
        })
        .sort((a, b) => {
          if (a.dateTs !== b.dateTs) return b.dateTs - a.dateTs;
          return a.idx - b.idx;
        });
    }

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
  }, [items, direction]);

  // Intersection: zachowaj tylko zaznaczenia faktur nadal widocznych w items.
  useEffect(() => {
    const visibleIds = new Set(items.map((inv) => inv.id));
    setSelected((prev) => {
      const next = new Set([...prev].filter((id) => visibleIds.has(id)));
      return next.size === prev.size ? prev : next;
    });
  }, [items]);

  const allVisibleIds = preparedItems.map((e) => e.invoice.id);
  const allSelected = allVisibleIds.length > 0 && allVisibleIds.every((id) => selected.has(id));
  const someSelected = selected.size > 0 && !allSelected;

  const handleSelectAll = () => {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(allVisibleIds));
    }
  };

  const toggleSelected = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleBulkSave = async () => {
    if (selected.size === 0) return;
    setBulkBusy(true);
    const invoices = [...selected]
      .map((id) => preparedItems.find((e) => e.invoice.id === id)?.invoice)
      .filter(Boolean);
    const zip = new JSZip();
    for (const invoice of invoices) {
      try {
        const arrayBuffer = await invoicesApi.getPdf(invoice.id);
        const rawName = invoice.number_local || invoice.id;
        const safeName = String(rawName).replace(/[/\\:*?"<>|]/g, '_');
        zip.file(`${safeName}.pdf`, arrayBuffer);
      } catch (err) {
        console.error('Błąd pobierania PDF:', err);
      }
    }
    try {
      const blob = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const today = new Date().toISOString().slice(0, 10);
      a.download = `faktury-zakupowe-${today}.zip`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    } catch (err) {
      console.error('Błąd tworzenia ZIP:', err);
    }
    setBulkBusy(false);
  };

  const handleBulkPrint = async () => {
    setBulkBusy(true);
    const invoices = [...selected]
      .map((id) => preparedItems.find((e) => e.invoice.id === id)?.invoice)
      .filter(Boolean);
    // Otwieramy okna synchronicznie (w kontekście user-gesture) zanim pojawi się pierwszy await,
    // co pozwala uniknąć blokowania popupów przez przeglądarkę.
    const windows = invoices.map(() => {
      const w = window.open('about:blank', '_blank');
      if (w) {
        w.opener = null;
        w.document.write('<p>Ładowanie podglądu do druku\u2026</p>');
        w.document.close();
      }
      return w;
    });
    await Promise.allSettled(
      invoices.map(async (invoice, i) => {
        const win = windows[i];
        try {
          const html = await invoicesApi.getPreview(invoice.id);
          const blob = new Blob([html], { type: 'text/html' });
          const url = URL.createObjectURL(blob);
          if (win) {
            win.addEventListener('load', () => {
              try { win.print(); } catch { /* ignoruj błąd print */ }
              setTimeout(() => URL.revokeObjectURL(url), 60000);
            }, { once: true });
            win.location.href = url;
          } else {
            URL.revokeObjectURL(url);
          }
        } catch (err) {
          console.error('Błąd drukowania faktury:', err);
          if (win) win.close();
        }
      }),
    );
    setBulkBusy(false);
  };

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

  const handleOpenPreview = async (e, invoice) => {
    e.stopPropagation();
    setPreviewLoadingId(invoice.id);
    const previewWindow = window.open('about:blank', '_blank');
    if (previewWindow) {
      previewWindow.opener = null;
      previewWindow.document.write('<p>Ładowanie podglądu...</p>');
      previewWindow.document.close();
    }

    try {
      const html = await invoicesApi.getPreview(invoice.id);
      const blob = new Blob([html], { type: 'text/html' });
      const url = URL.createObjectURL(blob);

      if (previewWindow) {
        previewWindow.location.href = url;
      } else {
        window.open(url, '_blank', 'noopener,noreferrer');
      }

      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      console.error('Błąd podglądu faktury:', err);
      if (previewWindow) {
        previewWindow.document.open();
        previewWindow.document.write('<p>Nie udało się otworzyć podglądu faktury.</p>');
        previewWindow.document.close();
      }
    } finally {
      setPreviewLoadingId(null);
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
    <div className={`${styles.container} ${showKsefStatus ? '' : styles.noKsef} ${direction === 'purchase' ? styles.withCheckbox : ''}${direction === 'purchase' ? ` ${styles.purchaseNumberColumn}` : ''}`}>
      {direction === 'purchase' && selected.size > 0 && (
        <div className={styles.bulkBar}>
          <span className={styles.bulkCount}>Zaznaczono: {selected.size}</span>
          <button
            className="btn btn-sm"
            onClick={handleBulkPrint}
            disabled={bulkBusy}
            title="Otwórz podgląd zaznaczonych faktur do druku"
          >
            {bulkBusy ? <span className="spinner" style={{ width: 12, height: 12 }} /> : 'Drukuj zaznaczone'}
          </button>
          <button
            className="btn btn-sm"
            onClick={handleBulkSave}
            disabled={bulkBusy}
            title="Pobierz PDF zaznaczonych faktur"
          >
            Zapisz zaznaczone
          </button>
        </div>
      )}
      <div className={`${styles.headerRow} ${styles.invoiceGrid}`}>
        {direction === 'purchase' && (
          <div className={styles.invoiceCellCheck}>
            <input
              type="checkbox"
              disabled={preparedItems.length === 0}
              checked={allSelected}
              ref={(el) => { if (el) el.indeterminate = someSelected; }}
              onChange={handleSelectAll}
              aria-label="Zaznacz wszystkie faktury zakupowe"
            />
          </div>
        )}
        <div className={`${styles.headerCell} ${styles.invoiceCellNumber}`}>Numer</div>
        <div className={`${styles.headerCell} ${styles.invoiceCellDate}`}>Data</div>
        <div className={`${styles.headerCell} ${styles.invoiceCellBuyer}`}>{contractorHeader}</div>
        <div className={`${styles.headerCell} ${styles.invoiceCellNip}`}>NIP</div>
        <div
          className={`${styles.headerCell} ${styles.invoiceHeaderAmount} ${styles.invoiceCellGross}`}
        >
          Brutto
        </div>
        <div className={`${styles.headerCell} ${styles.invoiceCellTerm}`}>Termin</div>
        <div
          className={`${styles.headerCell} ${styles.invoiceHeaderAmount} ${styles.invoiceCellRemaining}`}
        >
          Pozostało
        </div>
        {showKsefStatus && <div className={`${styles.headerCell} ${styles.invoiceCellKsef}`}>Status KSeF</div>}
        <div className={`${styles.headerCell} ${styles.invoiceCellPdf}`}>PDF</div>
      </div>

      <div className={styles.scrollArea} data-invoice-scroll-area>
        {preparedItems.map((item) => {
          const invoice = item.invoice;
          const grossAmount = getGrossAmount(invoice);
          const contractorName = getContractorName(invoice, direction);

          return (
            <div key={invoice.id} className={styles.card}>
              <div
                className={`${styles.cardContent} ${styles.invoiceGrid}`}
                role={onOpenInvoice ? 'button' : undefined}
                tabIndex={onOpenInvoice ? 0 : undefined}
                onClick={() => onOpenInvoice?.(invoice, getInvoiceOpenMode(invoice.status))}
                onKeyDown={(e) => {
                  if (!onOpenInvoice) return;
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onOpenInvoice(invoice, getInvoiceOpenMode(invoice.status));
                  }
                }}
              >
                {direction === 'purchase' && (
                  <div className={styles.invoiceCellCheck} onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selected.has(invoice.id)}
                      onChange={() => toggleSelected(invoice.id)}
                      aria-label={`Zaznacz fakturę ${item.displayNumber}`}
                    />
                  </div>
                )}
                <div className={`${styles.cell} ${styles.invoiceCellNumber}`}>
                  <span className={styles.label}>Numer</span>
                  <span
                    className={`${styles.value}${direction === 'purchase' ? ` ${styles.purchaseNumberValue}` : ''}`}
                    title={
                      direction === 'purchase' && item.displayNumber !== 'brak numeru'
                        ? item.displayNumber
                        : undefined
                    }
                  >
                    {item.displayNumber}
                  </span>
                </div>

                <div className={`${styles.cell} ${styles.invoiceCellDate}`}>
                  <span className={styles.label}>Data</span>
                  <span className={styles.value}>{formatDateDDMMYYYY(invoice.issue_date)}</span>
                </div>

                <div className={`${styles.cell} ${styles.invoiceCellBuyer}`}>
                  <span className={styles.label}>{contractorHeader}</span>
                  <ContractorNameWithPopup
                    name={contractorName}
                    snapshot={getContractorSnapshot(invoice, direction)}
                  />
                </div>

                <div className={`${styles.cell} ${styles.invoiceCellNip}`}>
                  <span className={styles.label}>NIP</span>
                  <span className={styles.value}>{getContractorNip(invoice, direction)}</span>
                </div>

                <div
                  className={`${styles.cell} ${styles.invoiceCellAmount} ${styles.invoiceCellGross}`}
                >
                  <span className={styles.label}>Brutto</span>
                  <span className={styles.value}>
                    {formatMoney(grossAmount, invoice.currency)}
                  </span>
                </div>

                <div className={`${styles.cell} ${styles.invoiceCellTerm}`}>
                  <span className={styles.label}>Termin</span>
                  <span className={styles.value}>
                    {invoice.due_date
                      ? formatDateDDMMYYYY(invoice.due_date)
                      : getPaymentTermLabel(invoice)}
                  </span>
                </div>

                <div
                  className={`${styles.cell} ${styles.invoiceCellAmount} ${styles.invoiceCellRemaining}`}
                >
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

                {showKsefStatus && (
                  <div
                    className={`${styles.cell} ${styles.invoiceCellKsef} ${styles.ksefCell}`}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <span className={styles.label}>Status KSeF</span>
                    <InvoiceActions invoice={invoice} onRefresh={onRefresh} />
                  </div>
                )}

                <div className={`${styles.cell} ${styles.invoiceCellPdf} ${styles.pdfCell}`}>
                  <span className={styles.label}>PDF</span>
                  <div className={styles.pdfActions}>
                    <button
                      className={`btn btn-sm ${styles.pdfButton}`}
                      onClick={(e) => handleOpenPreview(e, invoice)}
                      disabled={previewLoadingId === invoice.id}
                      title="Podgląd faktury"
                    >
                      {previewLoadingId === invoice.id ? (
                        <span className="spinner" style={{ width: 12, height: 12 }} />
                      ) : (
                        'Podgląd'
                      )}
                    </button>
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
            </div>
          );
        })}
      </div>
    </div>
  );
}
