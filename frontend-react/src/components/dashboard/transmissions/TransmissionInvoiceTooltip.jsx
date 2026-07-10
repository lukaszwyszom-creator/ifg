import {
  TOOLTIP_EMPTY_MESSAGE,
  formatDateShort,
  invoiceHasTooltipDetails,
} from './transmissionUtils';
import styles from './TransmissionMonitor.module.css';

function formatStatusLabel(status) {
  if (!status) return '—';
  return String(status).replace(/_/g, ' ');
}

export default function TransmissionInvoiceTooltip({ invoice }) {
  if (!invoice) return null;

  if (!invoiceHasTooltipDetails(invoice)) {
    return (
      <div className={`${styles.tooltip} ${styles.tooltipEmpty}`} role="tooltip">
        {TOOLTIP_EMPTY_MESSAGE}
      </div>
    );
  }

  const isPurchase = invoice.direction === 'purchase';
  const partyLabel = isPurchase ? 'Sprzedawca' : 'Nabywca';

  return (
    <div className={styles.tooltip} role="tooltip">
      <div className={styles.tooltipTitle}>{invoice.number}</div>
      <div><span className={styles.tooltipLabel}>{partyLabel}:</span> {invoice.counterparty}</div>
      {invoice.nip && (
        <div><span className={styles.tooltipLabel}>NIP:</span> {invoice.nip}</div>
      )}
      {invoice.amount != null && (
        <div><span className={styles.tooltipLabel}>Kwota brutto:</span> {invoice.amount}</div>
      )}
      <div><span className={styles.tooltipLabel}>Data:</span> {formatDateShort(invoice.date)}</div>
      {invoice.ksefRef && (
        <div><span className={styles.tooltipLabel}>Numer KSeF:</span> <span className={styles.mono}>{invoice.ksefRef}</span></div>
      )}
      <div><span className={styles.tooltipLabel}>Status:</span> {formatStatusLabel(invoice.status)}</div>
    </div>
  );
}
