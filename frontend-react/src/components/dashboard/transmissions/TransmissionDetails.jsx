import StatusBadge from '../../common/StatusBadge';
import TransmissionInvoiceTooltip from './TransmissionInvoiceTooltip';
import {
  deriveRowStatusTone,
  formatOperatorDateTimeDisplay,
  formatDateShort,
  formatTransmissionMarker,
  operationLabel,
} from './transmissionUtils';
import styles from './TransmissionMonitor.module.css';

function StageIcon({ row }) {
  const sev = String(row.severity || '').toUpperCase();
  if (sev === 'ERROR' || row.status?.startsWith('failed')) return '✗';
  if (sev === 'WARNING') return '⚠';
  if (sev === 'RUNNING') return '◌';
  return '✓';
}

function toneToBadgeStatus(row, tone) {
  if (tone === 'success') return 'success';
  if (tone === 'error') return row.status?.startsWith('failed') ? 'failed_permanent' : 'error';
  if (tone === 'warning') return row.status || 'warning';
  if (tone === 'info') return 'info';
  return 'neutral';
}

function renderMetadata(value) {
  if (!value || typeof value !== 'object') return <span className={styles.dash}>—</span>;
  return (
    <details className={styles.metaDetails}>
      <summary className={styles.metaSummary}>JSON</summary>
      <pre className={styles.metaPre}>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

export default function TransmissionDetails({ rows, summary, onRetry, retryBusy }) {
  return (
    <div className={styles.details}>
      <div className={styles.stageList}>
        {rows.map((row) => (
          <div key={row.id} className={styles.stageRow}>
            <span className={`${styles.stageIcon} ${styles[`iconTone_${deriveRowStatusTone(row)}`] || ''}`}>
              <StageIcon row={row} />
            </span>
            <span className={styles.stageName}>{operationLabel(row.operation_type)}</span>
            <StatusBadge status={toneToBadgeStatus(row, deriveRowStatusTone(row))} />
            <span className={styles.stageTime}>{formatOperatorDateTimeDisplay(row.created_at).replace('\n', ' ')}</span>
          </div>
        ))}
      </div>

      {summary.invoices.length > 0 && (
        <div className={styles.invoiceList}>
          <div className={styles.invoiceListTitle}>Faktury w procesie</div>
          <div className={styles.invoiceTable}>
            {summary.invoices.map((inv) => (
              <div key={inv.id || inv.number} className={styles.invoiceRow}>
                <span className={styles.invoiceCell}>
                  <span className={styles.tooltipWrap}>
                    <span className={styles.invoiceNumber}>{inv.number}</span>
                    <TransmissionInvoiceTooltip invoice={inv} />
                  </span>
                </span>
                <span className={styles.invoiceCell}>{inv.counterparty}</span>
                <span className={styles.invoiceCell}>{inv.amount ?? '—'}</span>
                <span className={styles.invoiceCell}><StatusBadge status={inv.status} /></span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className={styles.techGrid}>
        {rows.map((row) => (
          <div key={`tech-${row.id}`} className={styles.techCard}>
            <div className={styles.techHeader}>
              {operationLabel(row.operation_type)}
              <span className={styles.techTime}>{formatTransmissionMarker(row.created_at)}</span>
            </div>
            <dl className={styles.techDl}>
              <dt>Severity</dt><dd>{row.severity || '—'}</dd>
              <dt>Status</dt><dd>{row.status}</dd>
              <dt>Próby</dt><dd>{row.attempt_no ?? '—'}</dd>
              <dt>Correlation</dt><dd className={styles.mono}>{row.correlation_id || '—'}</dd>
              <dt>Job</dt><dd className={styles.mono}>{row.job_id || '—'}</dd>
              <dt>Ref KSeF</dt><dd className={styles.mono}>{row.ksef_reference_number || '—'}</dd>
              <dt>External ref</dt><dd className={styles.mono}>{row.external_reference || '—'}</dd>
              <dt>Błąd</dt><dd className={styles.errText}>{row.error_message || '—'}</dd>
              <dt>Metadata</dt><dd>{renderMetadata(row.metadata_json)}</dd>
            </dl>
          </div>
        ))}
      </div>

      {summary.hasRetryable && summary.retryRow && (
        <div className={styles.detailsActions}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={retryBusy}
            onClick={() => onRetry(summary.retryRow)}
          >
            {retryBusy ? 'Ponawianie…' : 'Ponów transmisję'}
          </button>
        </div>
      )}
    </div>
  );
}
