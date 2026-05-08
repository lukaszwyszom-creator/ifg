import { useState, useEffect } from 'react';
import { useAppStore } from '../../store/useAppStore';
import { paymentsApi } from '../../api/payments';
import { invoicesApi } from '../../api/invoices';
import DashboardSummary from '../../components/dashboard/DashboardSummary';
import KSeFSessionBar from '../../components/dashboard/KSeFSessionBar';
import VATSummary from '../../components/dashboard/VATSummary';
import TransmissionTable from '../../components/dashboard/TransmissionTable';
import InvoiceList from '../../components/invoice/InvoiceList';
import Filters from '../../components/common/Filters';
import { formatCurrencyPLN } from '../../utils/amountFormatting';
import OpenInvoicesPanel from './OpenInvoicesPanel';
import styles from './AdvancedDashboard.module.css';

const TABS = [
  { id: 'invoices',      label: 'Faktury sprzedaży' },
  { id: 'purchase',      label: 'Faktury zakupowe'  },
  { id: 'open',          label: 'Otwarte'           },
  { id: 'settlements',   label: 'Rozrachunki'       },
  { id: 'vat',           label: 'Zestawienie VAT'   },
  { id: 'transmissions', label: 'Transmisje KSeF'   },
];

export default function AdvancedDashboard() {
  const [tab, setTab] = useState('invoices');
  const [settlementTab, setSettlementTab] = useState('debtors');
  const [settlements, setSettlements] = useState({ debtors: [], creditors: [] });
  const [settlementsLoading, setSettlementsLoading] = useState(false);
  const [settlementsError, setSettlementsError] = useState('');
  const [settlementsLoaded, setSettlementsLoaded] = useState(false);
  const [openInvoices, setOpenInvoices] = useState([]);
  const [openSummary, setOpenSummary] = useState(null);
  const [openLoading, setOpenLoading] = useState(false);
  const [openError, setOpenError] = useState('');
  const [openLoaded, setOpenLoaded] = useState(false);
  const filters = useAppStore((s) => s.filters);
  const setFilters = useAppStore((s) => s.setFilters);
  const resetFilters = useAppStore((s) => s.resetFilters);

  useEffect(() => {
    if (tab !== 'settlements') return;
    if (settlementsLoaded) return;
    let cancelled = false;
    setSettlementsLoading(true);
    setSettlementsError('');
    paymentsApi
      .getSettlements({ side: 'all' })
      .then((data) => {
        if (cancelled) return;
        setSettlements({
          debtors: Array.isArray(data?.debtors) ? data.debtors : [],
          creditors: Array.isArray(data?.creditors) ? data.creditors : [],
        });
        setSettlementsLoaded(true);
      })
      .catch((err) => {
        if (cancelled) return;
        const status = err?.response?.status;
        const data = err?.response?.data;
        const url = err?.config?.url ?? '/payments/settlements';
        const authHeader = err?.config?.headers?.Authorization;
        console.error('[Rozrachunki] Błąd pobierania danych:', {
          url,
          status,
          responseData: data,
          authHeaderPresent: !!authHeader,
          authHeaderPrefix: authHeader ? authHeader.slice(0, 15) + '…' : 'brak',
          err,
        });
        const hint = status === 401 ? ' (brak autoryzacji)' : status === 404 ? ' (endpoint nie znaleziony)' : status ? ` (HTTP ${status})` : '';
        setSettlementsError(`Nie udało się pobrać rozrachunków${hint}. Sprawdź połączenie z serwerem.`);
        setSettlements({ debtors: [], creditors: [] });
      })
      .finally(() => {
        if (!cancelled) setSettlementsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tab, settlementsLoaded]);

  useEffect(() => {
    if (tab !== 'open') return;
    if (openLoaded) return;
    let cancelled = false;
    setOpenLoading(true);
    setOpenError('');
    invoicesApi
      .list({ view: 'open', size: 100 })
      .then((data) => {
        if (cancelled) return;
        setOpenInvoices(Array.isArray(data?.items) ? data.items : []);
        setOpenSummary(data?.summary ?? null);
        setOpenLoaded(true);
      })
      .catch((err) => {
        if (cancelled) return;
        const status = err?.response?.status;
        const hint = status ? ` (HTTP ${status})` : '';
        setOpenError(`Nie udało się pobrać otwartych faktur${hint}.`);
        setOpenInvoices([]);
        setOpenSummary(null);
      })
      .finally(() => {
        if (!cancelled) setOpenLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tab, openLoaded]);

  const fmtDate = (iso) => {
    if (!iso) return '—';
    const [y, m, d] = iso.split('-');
    if (!y || !m || !d) return '—';
    return `${d}.${m}.${y}`;
  };
  const fmtInvoiceNumber = (numberLocal, ksefReferenceNumber) => {
    const local = String(numberLocal || '').trim();
    if (local) {
      const withoutPrefix = local.replace(/^FV[\s\/-]*/i, '').trim();
      return withoutPrefix || local;
    }
    if (ksefReferenceNumber) {
      return `[KSeF] ${ksefReferenceNumber}`;
    }
    return '—';
  };
  const termInfo = (dueDateIso) => {
    if (!dueDateIso) {
      return { text: '—', cls: '' };
    }
    const due = new Date(dueDateIso);
    if (Number.isNaN(due.getTime())) {
      return { text: '—', cls: '' };
    }
    const today = new Date();
    due.setHours(0, 0, 0, 0);
    today.setHours(0, 0, 0, 0);
    const diffDays = Math.floor((due.getTime() - today.getTime()) / 86400000);
    if (diffDays > 0) {
      return { text: `+${diffDays} dni`, cls: styles.termAhead };
    }
    if (diffDays < 0) {
      return { text: `${diffDays} dni`, cls: styles.termOverdue };
    }
    return { text: '0 dni', cls: styles.termToday };
  };
  const settlementRows = settlementTab === 'debtors' ? settlements.debtors : settlements.creditors;
  const sumDebt = settlements.debtors.reduce((acc, r) => acc + Number(r.remaining_amount ?? 0), 0);
  const sumCredit = settlements.creditors.reduce((acc, r) => acc + Number(r.remaining_amount ?? 0), 0);

  return (
    <div className={styles.page}>
      {/* Statystyki */}
      <DashboardSummary filters={filters} />

      {/* Pasek sesji KSeF (otwieranie/zamykanie + pobieranie zakupowych) */}
      <KSeFSessionBar />

      {/* Filtry */}
      <Filters
        filters={filters}
        onChange={setFilters}
        onReset={resetFilters}
        vatMode={tab === 'vat'}
      />

      {/* Tabsy */}
      <div className={styles.tabs}>
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`${styles.tab} ${tab === t.id ? styles.tabActive : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Zawartość */}
      <div className={styles.panel}>
        {tab === 'invoices' && (
          <InvoiceList filters={filters} direction="sale" showKsefStatus={false} />
        )}

        {tab === 'purchase' && (
          <InvoiceList filters={filters} direction="purchase" showKsefStatus={false} />
        )}

        {tab === 'open' && (
          <OpenInvoicesPanel
            invoices={openInvoices}
            summary={openSummary}
            loading={openLoading}
            error={openError}
            loaded={openLoaded}
          />
        )}

        {tab === 'settlements' && (
          <div className={`${styles.settlementsPanel} ${styles.settlementsPanelSticky}`}>
            <div className={styles.settlementTabs}>
              <button
                className={`${styles.settlementTab} ${settlementTab === 'debtors' ? `${styles.settlementTabActive} ${styles.settlementTabDebtorsActive}` : ''}`}
                onClick={() => setSettlementTab('debtors')}
              >
                Dłużnicy
              </button>
              <button
                className={`${styles.settlementTab} ${settlementTab === 'creditors' ? `${styles.settlementTabActive} ${styles.settlementTabCreditorsActive}` : ''}`}
                onClick={() => setSettlementTab('creditors')}
              >
                Wierzyciele
              </button>
            </div>

            {settlementsLoading && (
              <div className={styles.settlementState}><span className="spinner" /></div>
            )}

            {!settlementsLoading && settlementsError && (
              <div className="alert alert-error">{settlementsError}</div>
            )}

            {!settlementsLoading && !settlementsError && settlementsLoaded && (
              <div className={styles.settlementsSummary}>
                <span className={styles.settlementSummaryItem}>
                  <span className={styles.settlementSummaryLabel}>Dłużnicy:</span>{' '}
                  <span className={styles.settlementDebtAmount}>{formatCurrencyPLN(sumDebt)}</span>
                </span>
                <span className={styles.settlementSummaryItem}>
                  <span className={styles.settlementSummaryLabel}>Wierzyciele:</span>{' '}
                  <span className={styles.settlementCreditAmount}>{formatCurrencyPLN(sumCredit)}</span>
                </span>
              </div>
            )}

            {!settlementsLoading && !settlementsError && (
              <div className={styles.tableWrap}>
                <div className={styles.settlementTable}>
                  <div className={styles.settlementHeader}>
                    <div className={styles.settlementRow}>
                      <div className={`${styles.settlementCell} ${styles.settlementHeadCell} ${styles.contractorCol}`}>Kontrahent</div>
                      <div className={`${styles.settlementCell} ${styles.settlementHeadCell} ${styles.invoiceNumberCol}`}>
                        <span className={styles.headerTwoLine}><span>Numer</span><span>faktury</span></span>
                      </div>
                      <div className={`${styles.settlementCell} ${styles.settlementHeadCell} ${styles.issueDateCol}`}>
                        <span className={styles.headerTwoLine}><span>Data</span><span>wystawienia</span></span>
                      </div>
                      <div className={`${styles.settlementCell} ${styles.settlementHeadCell} ${styles.dueDateCol}`}>
                        <span className={styles.headerTwoLine}><span>Data</span><span>płatności</span></span>
                      </div>
                      <div className={`${styles.settlementCell} ${styles.settlementHeadCell} ${styles.termCol}`}>Termin</div>
                      <div className={`${styles.settlementCell} ${styles.settlementHeadCell} ${styles.grossCol}`}>
                        <span className={styles.headerTwoLine}><span>Kwota</span><span>brutto</span></span>
                      </div>
                      <div className={`${styles.settlementCell} ${styles.settlementHeadCell} ${styles.paidCol}`}>Zapłacono</div>
                      <div className={`${styles.settlementCell} ${styles.settlementHeadCell} ${styles.remainingCol}`}>Pozostało</div>
                    </div>
                  </div>

                  <div className={styles.settlementBody}>
                    {settlementRows.length === 0 ? (
                      <div className={styles.settlementRow}>
                        <div className={`${styles.settlementCell} ${styles.emptyRow}`}>Brak rozrachunków</div>
                      </div>
                    ) : (
                      settlementRows.map((item) => {
                        const remaining = Number(item.remaining_amount ?? 0);
                        const paidAmount = Number(item.paid_amount ?? 0);
                        const hasPaid = paidAmount > 0;
                        const hasRemaining = remaining > 0;
                        const term = termInfo(item.due_date);
                        return (
                          <div className={styles.settlementRow} key={item.invoice_id}>
                            <div className={`${styles.settlementCell} ${styles.contractorCol} ${styles.contractorCell}`} title={item.contractor_name || '—'}>
                              <span className={styles.contractorText}>{item.contractor_name || '—'}</span>
                            </div>
                            <div className={`${styles.settlementCell} ${styles.invoiceNumberCol}`}>{fmtInvoiceNumber(item.number_local, item.ksef_reference_number)}</div>
                            <div className={`${styles.settlementCell} ${styles.issueDateCol}`}>{fmtDate(item.issue_date)}</div>
                            <div className={`${styles.settlementCell} ${styles.dueDateCol}`}>{fmtDate(item.due_date)}</div>
                            <div className={`${styles.settlementCell} ${styles.termCol} ${term.cls}`.trim()}>{term.text}</div>
                            <div className={`${styles.settlementCell} ${styles.grossCol}`}>{formatCurrencyPLN(item.gross_total)}</div>
                            <div className={`${styles.settlementCell} ${styles.paidCol} ${hasPaid ? styles.amountPaid : ''}`.trim()}>{formatCurrencyPLN(item.paid_amount)}</div>
                            <div className={`${styles.settlementCell} ${styles.remainingCol} ${hasPaid ? styles.amountPaid : (hasRemaining ? styles.amountDue : '')}`.trim()}>
                              {formatCurrencyPLN(item.remaining_amount)}
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {tab === 'vat' && (
          <VATSummary filters={filters} />
        )}

        {tab === 'transmissions' && (
          <TransmissionTable />
        )}
      </div>

    </div>
  );
}
