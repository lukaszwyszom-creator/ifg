// Wydzielony panel widoku "Otwarte" — używa danych z props.
// Logika fetch + zarządzanie stanem pozostają w kontenerze (AdvancedDashboard).
import { formatAmountByCurrency, formatAmountNeutral } from '../../utils/amountFormatting';
import styles from './AdvancedDashboard.module.css';

function calculateOverdueDays(dueDate) {
  if (!dueDate) return null;
  const due = new Date(dueDate);
  if (Number.isNaN(due.getTime())) return null;
  const today = new Date();
  due.setHours(0, 0, 0, 0);
  today.setHours(0, 0, 0, 0);
  if (today <= due) return 0;
  return Math.floor((today - due) / 86400000);
}

function contractorLabel(invoice) {
  const direction = invoice?.direction || 'sale';
  const snap = direction === 'purchase' ? invoice?.seller_snapshot : invoice?.buyer_snapshot;
  return snap?.name || snap?.nip || '—';
}

function remainingFor(invoice) {
  // Backend liczy remaining_amount = total_gross - sum(allocations).
  // Fallback (gdyby pole było null): unpaid → brutto, paid → 0, partially_paid → null.
  if (invoice?.remaining_amount != null) return Number(invoice.remaining_amount);
  if (invoice?.payment_status === 'unpaid') return Number(invoice.total_gross ?? 0);
  if (invoice?.payment_status === 'paid') return 0;
  return null;
}

export default function OpenInvoicesPanel({ invoices, summary, loading, error, loaded }) {
  const rows = invoices.map((inv) => ({
    invoice: inv,
    overdueDays: typeof inv.overdue_days === 'number' ? inv.overdue_days : calculateOverdueDays(inv.due_date),
    remaining: remainingFor(inv),
  }));
  // Sumy liczy backend (summary.total_receivables / total_payables).
  const totalRecover = summary?.total_receivables ?? '0.00';
  const totalToPay = summary?.total_payables ?? '0.00';
  const overdue0to30 = summary?.overdue_0_30 ?? '0.00';
  const overdue30to60 = summary?.overdue_30_60 ?? '0.00';
  const overdue60plus = summary?.overdue_60_plus ?? '0.00';

  return (
    <div className={styles.settlementsPanel}>
      {loading && (
        <div className={styles.settlementState}><span className="spinner" /></div>
      )}

      {!loading && error && (
        <div className="alert alert-error">{error}</div>
      )}

      {!loading && !error && loaded && (
        <>
          <div className={styles.settlementsSummary}>
            <span>Do odzyskania: <strong>{formatAmountNeutral(totalRecover)}</strong></span>
            <span>Do zapłaty: <strong>{formatAmountNeutral(totalToPay)}</strong></span>
          </div>
          <div className={styles.settlementsSummary}>
            <span>Struktura przeterminowania:</span>
            <span>1-30 dni po terminie: <strong>{formatAmountNeutral(overdue0to30)}</strong></span>
            <span>31-60 dni po terminie: <strong>{formatAmountNeutral(overdue30to60)}</strong></span>
            <span>60+ dni po terminie: <strong>{formatAmountNeutral(overdue60plus)}</strong></span>
          </div>
        </>
      )}

      {!loading && !error && (
        <div className={styles.tableWrap}>
          <table className={styles.settlementTable}>
            <thead>
              <tr>
                <th>Kontrahent</th>
                <th>Numer</th>
                <th>Data wystawienia</th>
                <th>Termin płatności</th>
                <th>Opóźnienie</th>
                <th>Kwota</th>
                <th>Pozostało</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={7} className={styles.emptyRow}>Brak otwartych faktur</td>
                </tr>
              ) : (
                rows.map(({ invoice, overdueDays, remaining }) => {
                  const isOverdue = typeof overdueDays === 'number' && overdueDays > 0;
                  const hasRemaining = (remaining ?? 0) > 0;
                  return (
                    <tr key={invoice.id} className={isOverdue ? styles.overdueRow : undefined}>
                      <td>{contractorLabel(invoice)}</td>
                      <td>{invoice.number_local || '—'}</td>
                      <td>{invoice.issue_date || '—'}</td>
                      <td>{invoice.due_date || '—'}</td>
                      <td className={isOverdue ? styles.overdue : undefined}>
                        {isOverdue ? `${overdueDays} dni` : '—'}
                      </td>
                      <td>{formatAmountByCurrency(invoice.total_gross, invoice.currency || 'PLN')}</td>
                      <td className={hasRemaining ? styles.amountDue : undefined}>
                        {remaining === null ? '—' : formatAmountByCurrency(remaining, invoice.currency || 'PLN')}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
