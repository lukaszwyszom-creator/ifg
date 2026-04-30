import { useState } from 'react';
import { useAppStore } from '../../store/useAppStore';
import { paymentsApi } from '../../api/payments';
import DashboardSummary from '../../components/dashboard/DashboardSummary';
import VATSummary from '../../components/dashboard/VATSummary';
import TransmissionTable from '../../components/dashboard/TransmissionTable';
import InvoiceList from '../../components/invoice/InvoiceList';
import Filters from '../../components/common/Filters';
import styles from './AdvancedDashboard.module.css';

const TABS = [
  { id: 'invoices',       label: 'Faktury sprzedaży' },
  { id: 'purchase',       label: 'Faktury zakupowe' },
  { id: 'vat',            label: 'Zestawienie VAT'  },
  { id: 'transmissions',  label: 'Transmisje KSeF'   },
];

export default function AdvancedDashboard() {
  const [tab, setTab] = useState('invoices');
  const [showSettlements, setShowSettlements] = useState(false);
  const [settlementTab, setSettlementTab] = useState('debtors');
  const [settlements, setSettlements] = useState({ debtors: [], creditors: [] });
  const [settlementsLoading, setSettlementsLoading] = useState(false);
  const [settlementsError, setSettlementsError] = useState('');
  const filters = useAppStore((s) => s.filters);
  const setFilters = useAppStore((s) => s.setFilters);
  const resetFilters = useAppStore((s) => s.resetFilters);

  const openSettlements = async () => {
    setShowSettlements(true);
    setSettlementTab('debtors');
    setSettlementsLoading(true);
    setSettlementsError('');

    try {
      const data = await paymentsApi.getSettlements({ side: 'all' });
      setSettlements({
        debtors: Array.isArray(data?.debtors) ? data.debtors : [],
        creditors: Array.isArray(data?.creditors) ? data.creditors : [],
      });
    } catch {
      setSettlementsError('Nie udało się pobrać rozrachunków.');
      setSettlements({ debtors: [], creditors: [] });
    } finally {
      setSettlementsLoading(false);
    }
  };

  const closeSettlements = () => {
    setShowSettlements(false);
    setSettlementsError('');
  };

  const fmtMoney = (value) => `${Number(value ?? 0).toFixed(2)} PLN`;
  const rows = settlementTab === 'debtors' ? settlements.debtors : settlements.creditors;

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
      <div className={styles.tabsRow}>
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
        <button className="btn btn-secondary btn-sm" onClick={openSettlements}>
          Rozrachunki
        </button>
      </div>

      {/* Zawartość */}
      <div className={styles.panel}>
        {tab === 'invoices' && (
          <InvoiceList filters={filters} direction="sale" showKsefStatus={false} />
        )}

        {tab === 'purchase' && (
          <InvoiceList filters={filters} direction="purchase" showKsefStatus={false} />
        )}

        {tab === 'vat' && (
          <VATSummary filters={filters} />
        )}

        {tab === 'transmissions' && (
          <TransmissionTable />
        )}
      </div>

      {showSettlements && (
        <div className={styles.overlay} onClick={closeSettlements}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3 className={styles.modalTitle}>Rozrachunki</h3>
              <button className="btn btn-ghost btn-sm" onClick={closeSettlements}>Zamknij</button>
            </div>

            <div className={styles.modalTabs}>
              <button
                className={`${styles.modalTab} ${settlementTab === 'debtors' ? styles.modalTabActive : ''}`}
                onClick={() => setSettlementTab('debtors')}
              >
                Dłużnicy
              </button>
              <button
                className={`${styles.modalTab} ${settlementTab === 'creditors' ? styles.modalTabActive : ''}`}
                onClick={() => setSettlementTab('creditors')}
              >
                Wierzyciele
              </button>
            </div>

            {settlementsLoading && <div className={styles.modalState}><span className="spinner" /></div>}
            {!settlementsLoading && settlementsError && <div className="alert alert-error">{settlementsError}</div>}

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
                    {rows.length === 0 && (
                      <tr>
                        <td colSpan={7} className={styles.emptyRow}>Brak danych</td>
                      </tr>
                    )}
                    {rows.map((item) => (
                      <tr key={item.invoice_id}>
                        <td>{item.contractor_name || '—'}</td>
                        <td>{item.number_local || '—'}</td>
                        <td>{item.issue_date || '—'}</td>
                        <td>{fmtMoney(item.gross_total)}</td>
                        <td>{fmtMoney(item.paid_amount)}</td>
                        <td>{fmtMoney(item.remaining_amount)}</td>
                        <td>{item.payment_status || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
