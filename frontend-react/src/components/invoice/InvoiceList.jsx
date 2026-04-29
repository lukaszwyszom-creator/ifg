import { useState, useEffect, useCallback } from 'react';
import { invoicesApi } from '../../api/invoices';
import Pagination from '../common/Pagination';
import InvoiceCardList from './InvoiceCardList';


/**
 * @param {object}  filters    - aktywne filtry
 * @param {string}  direction  - 'sale' | 'purchase' (domyślnie 'sale')
 * @param {number}  limit      - max wierszy (Simple mode: 10)
 * @param {bool}    hidePager  - ukryj paginację
 */
export default function InvoiceList({
  filters = {},
  direction = 'sale',
  showKsefStatus = true,
  limit,
  hidePager = false,
  onItemsChange,
  onOpenInvoice,
}) {
  const [data, setData] = useState({ items: [], total: 0 });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  const size = limit ?? 20;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const contractorFilter = String(filters.contractor || '').trim();

      // Wyznacz daty z filtra miesiąca (jeśli nie podano własnych dat)
      let dateFrom = filters.issue_date_from || '';
      let dateTo   = filters.issue_date_to   || '';
      if (filters.month && !dateFrom && !dateTo && contractorFilter.length < 3) {
        const [y, m] = filters.month.split('-').map(Number);
        const last = new Date(y, m, 0).getDate();
        dateFrom = `${filters.month}-01`;
        dateTo   = `${filters.month}-${String(last).padStart(2, '0')}`;
      }
      const params = {
        page,
        size,
        direction,
        ...(filters.status  && { status: filters.status }),
        ...(dateFrom        && { issue_date_from: dateFrom }),
        ...(dateTo          && { issue_date_to: dateTo }),
        ...(contractorFilter.length >= 3 && { number_filter: contractorFilter }),
      };
      const res = await invoicesApi.list(params);
      setData(res);
      if (onItemsChange) {
        onItemsChange(Array.isArray(res?.items) ? res.items : []);
      }
    } finally {
      setLoading(false);
    }
  }, [page, size, filters, direction, onItemsChange]);

  useEffect(() => { load(); }, [load]);

  // Odśwież listę zakupowych po synchronizacji z KSeF
  useEffect(() => {
    if (direction !== 'purchase') return;
    const handler = () => load();
    window.addEventListener('ksef:invoices-synced', handler);
    return () => window.removeEventListener('ksef:invoices-synced', handler);
  }, [direction, load]);

  // Eksponuj reload przez ref (opcjonalnie) — proste triggery

  return (
    <div>
      <InvoiceCardList
        items={data.items}
        direction={direction}
        showKsefStatus={showKsefStatus}
        loading={loading}
        onRefresh={load}
        onOpenInvoice={onOpenInvoice}
        emptyMsg="Brak faktur"
      />
      {!hidePager && (
        <Pagination page={page} total={data.total} size={size} onPage={setPage} />
      )}
    </div>
  );
}
