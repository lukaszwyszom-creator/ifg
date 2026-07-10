import TransmissionDetails from './TransmissionDetails';
import TransmissionSummary from './TransmissionSummary';
import {
  buildProcessSummaryMeta,
  deriveProcessProgress,
  deriveProcessIcon,
  formatGroupStatusDisplay,
  invoicesSummaryLabel,
  mapStatusKeyToTone,
  summarizeGroup,
} from './transmissionUtils';
import styles from './TransmissionMonitor.module.css';

export default function TransmissionGroup({
  group,
  expanded,
  onToggle,
  onRetry,
  retryBusyId,
}) {
  const summary = summarizeGroup(group.rows);
  const tone = mapStatusKeyToTone(group.status?.key);
  const statusClass = styles[`status_${tone}`] || styles.status_neutral;
  const processIcon = deriveProcessIcon(group.title, group.status);
  const dateParts = group.dateTimeParts || { dateLine: group.datetime, timeLine: '' };
  const progress = deriveProcessProgress(group);
  const progressToneClass = styles[`progress_${progress.tone}`] || styles.progress_neutral;

  return (
    <div className={`${styles.group} ${styles[`groupAccent_${tone}`] || ''}`}>
      <button
        type="button"
        className={styles.groupHeader}
        onClick={onToggle}
        aria-expanded={expanded}
      >
        <span className={styles.expandIcon}>{expanded ? '▼' : '▶'}</span>
        <span className={styles.colMarker}>
          <span className={styles.mono}>{group.marker}</span>
        </span>
        <span className={styles.colProcess}>
          <span className={styles.processTitleRow}>
            <span className={`${styles.processIcon} ${styles[`iconTone_${tone}`] || ''}`} aria-hidden>{processIcon}</span>
            <span className={styles.processTitle}>{group.title}</span>
          </span>
          {!expanded && (
            <span className={styles.processMeta}>
              {buildProcessSummaryMeta(summary, group.title)}
            </span>
          )}
          {!expanded && (
            <span className={`${styles.progressWrap} ${progressToneClass}`} title={progress.title}>
              <span className={styles.progressBar} aria-hidden>
                <span className={styles.progressFill} style={{ width: `${progress.percent}%` }} />
              </span>
              <span className={styles.progressLabel}>
                {progress.percent}% · {progress.label}
              </span>
              <span className={styles.progressSteps} aria-hidden>
                {progress.steps.map((step) => (
                  <span
                    key={step.key}
                    className={`${styles.progressStepDot} ${styles[`progressStep_${step.status}`] || ''}`}
                  />
                ))}
              </span>
            </span>
          )}
        </span>
        <span className={`${styles.colStatus} ${statusClass}`}>
          <span className={styles.statusPill}>
            {formatGroupStatusDisplay(group.status)}
          </span>
        </span>
        <span className={styles.colInvoices}>{invoicesSummaryLabel(summary)}</span>
        <span className={styles.colTime}>
          <span className={styles.dateLine}>{dateParts.dateLine}</span>
          {dateParts.timeLine && (
            <span className={styles.timeLine}>{dateParts.timeLine}</span>
          )}
        </span>
        <span className={styles.colActions} onClick={(e) => e.stopPropagation()} />
      </button>

      {expanded && (
        <div className={styles.groupBody}>
          <TransmissionSummary summary={summary} status={group.status} title={group.title} />
          <TransmissionDetails
            rows={group.rows}
            summary={summary}
            onRetry={onRetry}
            retryBusy={retryBusyId === summary.retryRow?.id}
          />
        </div>
      )}
    </div>
  );
}
