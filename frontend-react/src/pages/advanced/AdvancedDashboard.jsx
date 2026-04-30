import { useState, useEffect } from 'react';
import { useAppStore } from '../../store/useAppStore';
import { paymentsApi } from '../../api/payments';
import DashboardSummary from '../../components/dashboard/DashboardSummary';
import VATSummary from '../../components/dashboard/VATSummary';
import TransmissionTable from '../../components/dashboard/TransmissionTable';
import InvoiceList from '../../components/invoice/InvoiceList';
import Filters from '../../components/common/Filters';
import styles from './AdvancedDashboard.module.css';

const TABS = [
  { id: 'invoices',      label: 'Faktury sprzedaży' },
  { id: 'purchase',      label: 'Faktury zakupowe'  },
  { id: 'settlements',   label: 'Rozrachunki'        },
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
        console.error('[Rozrachunki] Błąd pobierania danych:', err);
        setSettlementsError('Nie udało się pobrać rozrachunków. Sprawdź połączenie z serwerem.');
        setSettlements({ debtors: [], creditors: [] });
      })
      .finally(() => {
        if (!cancelled) setSettlementsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tab, settlementsLoaded]);

  const fmtMoney = (value) => `${Number(value ?? 0).toFixed(2)} PLN`;
  const settlementRows = settlementTab === 'debtors' ? settlements.debtors : settlements.creditors;
  const sumDebt = settlements.debtors.reduce((acc, r) => acc + Number(r.remaining_amount ?? 0), 0);
  const sumCredit = settlements.creditors.reduce((acc, r) => acc + Number(r.remaining_amount ?? 0), 0);

  return (
    <div className={styles.page}>
      {/* Statystyki */}
      <DashboardSummary filters={filters} />

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

        {tab === 'settlements' && (
          <div className={styles.settlementsPanel}>
            <div className={styles.settlementTabs}>
              <button
                className={`${styles.settlementTab} ${settlementTab === 'debtors' ? styles.settlementTabActive : ''}`}
                onClick={() => setSettlementTab('debtors')}
              >
                Dłużnicy
              </button>
              <button
                className={`${styles.settlementTab} ${settlementTab === 'creditors' ? styles.settlementTabActive : ''}`}
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
                <span>Dłużnicy: <strong>{fmtMoney(sumDebt)}</strong></span>
                <span>Wierzyciele: <strong>{fmtMoney(sumCredit)}</strong></span>
              </div>
            )}

            {!settlementsLoading && !settlementsError && (
              <div className={styles.tableWrap}>
                <table className={styles.settlementTable}>
                  <thead>
                    <tr>
                      <th>Kontrahent</th>
                      <th>Numer faktury</th>
                      <th>Data</th>
                      <th>Kwota brutto</th>
                      <th>Zapłacono</th>
                      <th>Pozostało</th>
                      <th>Status płatności</th>
                    </tr>
                  </thead>
                  <tbody>
                    {settlementRows.length === 0 ? (
                      <tr>
                        <td colSpan={7} className={styles.emptyRow}>Brak rozrachunków</td>
                      </tr>
                    ) : (
                      settlementRows.map((item) => (
                        <tr key={item.invoice_id}>
                          <td>{item.contractor_name || '—'}</td>
                          <td>{item.number_local || '—'}</td>
                          <td>{item.issue_date || '—'}</td>
                          <td>{fmtMoney(item.gross_total)}</td>
                          <td>{fmtMoney(item.paid_amount)}</td>
                          <td>{fmtMoney(item.remaining_amount)}</td>
                          <td>{item.payment_status || '—'}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
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
