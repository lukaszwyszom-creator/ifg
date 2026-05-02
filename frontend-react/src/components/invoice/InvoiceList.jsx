import { useState, useEffect, useMemo, useCallback } from 'react';
import { useAppStore } from '../../store/useAppStore';
import { buildInvoicePoolKey, buildInvoicePoolQuery, filterInvoicesFromPool } from '../dashboard/dashboardQuery';
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
  emptyMsg,
  sourceItems,
  onItemsChange,
  onOpenInvoice,
}) {
  const [page, setPage] = useState(1);
  const loadInvoicePool = useAppStore((s) => s.loadInvoicePool);

  const size = limit ?? 20;

  const poolQuery = useMemo(
    () => buildInvoicePoolQuery(filters, direction, { defaultToCurrentMonth: false }),
    [filters, direction]
  );
  const poolKey = useMemo(() => buildInvoicePoolKey(poolQuery), [poolQuery]);

  const poolEntry = useAppStore((s) => s.invoicePool?.[direction]?.[poolKey]);
  const poolLoading = useAppStore((s) => Boolean(s.invoicePoolLoading?.[`${direction}:${poolKey}`]));

  useEffect(() => {
    if (Array.isArray(sourceItems)) return;
    loadInvoicePool({ direction, filters, options: { defaultToCurrentMonth: false } }).catch(() => null);
  }, [sourceItems, loadInvoicePool, direction, filters, poolKey]);

  const baseItems = useMemo(
    () => (Array.isArray(sourceItems)
      ? sourceItems
      : (Array.isArray(poolEntry?.items) ? poolEntry.items : [])),
    [sourceItems, poolEntry]
  );

  const filteredItems = useMemo(
    () => filterInvoicesFromPool(baseItems, filters, { defaultToCurrentMonth: false }),
    [baseItems, filters]
  );

  const pagedItems = useMemo(() => {
    if (hidePager) return filteredItems.slice(0, size);
    const offset = (page - 1) * size;
    return filteredItems.slice(offset, offset + size);
  }, [filteredItems, hidePager, page, size]);

  const loading = !Array.isArray(sourceItems) && poolLoading && !poolEntry;

  const reload = useCallback(() => {
    if (Array.isArray(sourceItems)) return Promise.resolve(sourceItems);
    return loadInvoicePool({ direction, filters, options: { defaultToCurrentMonth: false }, force: true });
  }, [sourceItems, loadInvoicePool, direction, filters]);

  useEffect(() => {
    if (!onItemsChange) return;
    onItemsChange(filteredItems);
  }, [onItemsChange, filteredItems]);

  useEffect(() => {
    setPage(1);
  }, [filters, direction]);

  return (
    <div>
      <InvoiceCardList
        items={pagedItems}
        direction={direction}
        showKsefStatus={showKsefStatus}
        loading={loading}
        onRefresh={reload}
        onOpenInvoice={onOpenInvoice}
        emptyMsg={emptyMsg ?? 'Brak faktur'}
      />
      {!hidePager && (
        <Pagination page={page} total={filteredItems.length} size={size} onPage={setPage} />
      )}
    </div>
  );
}
