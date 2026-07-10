import { deriveProcessIcon, buildSummaryLines, mapStatusKeyToTone } from './transmissionUtils';
import styles from './TransmissionMonitor.module.css';

export default function TransmissionSummary({ summary, status, title }) {
  const { status: statusLine, effects, meta } = buildSummaryLines(summary, status, title);
  const tone = mapStatusKeyToTone(status?.key);
  const statusClass = styles[`status_${tone}`] || styles.status_neutral;

  return (
    <div className={styles.summaryBlock}>
      <div className={styles.summaryTitleRow}>
        <span className={`${styles.summaryProcessIcon} ${styles[`iconTone_${tone}`] || ''}`} aria-hidden>{deriveProcessIcon(title, status)}</span>
        <span className={styles.summaryTitle}>{title}</span>
      </div>
      <div className={`${styles.summaryStatusLine} ${statusClass}`}>{statusLine}</div>
      {effects.length > 0 && (
        <div className={styles.summaryEffects}>
          {effects.map((line) => (
            <span key={line} className={styles.summaryEffectLine}>{line}</span>
          ))}
        </div>
      )}
      {meta.length > 0 && (
        <div className={styles.summaryMeta}>
          {meta.map((line) => (
            <span key={line} className={styles.summaryMetaLine}>{line}</span>
          ))}
        </div>
      )}
    </div>
  );
}
