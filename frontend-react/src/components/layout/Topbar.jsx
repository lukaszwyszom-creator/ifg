import { useLocation } from 'react-router-dom';
import KSeFConnectionTile from './KSeFConnectionTile';
import KSeFTopbarInfo from './KSeFTopbarInfo';
import styles from './Topbar.module.css';

function getCurrentMonthYear() {
  return String(new Date().getFullYear());
}

export default function Topbar({ onMenuToggle }) {
  const location = useLocation();
  const monthYear = getCurrentMonthYear();
  const invoicesTitle = (
    <>
      <span className={styles.pageTitlePrefix}>Faktury sprzedaż - </span>
      <span className={styles.pageTitleAccent}>{monthYear}</span>
    </>
  );
  const pageTitles = {
    '/invoices': invoicesTitle,
    '/dashboard': <span className={styles.pageTitleGold}>Zestawienia</span>,
    '/payments': 'Płatności',
    '/stock': 'Magazyn',
  };

  return (
    <header className={styles.topbar}>
      <div className={styles.left}>
        <button className={styles.menuBtn} onClick={onMenuToggle} aria-label="Menu">
          ☰
        </button>
        <span className={styles.pageTitle}>
          {pageTitles[location.pathname] ?? 'System Fakturowania'}
        </span>
      </div>

      <div className={styles.right}>
        <KSeFTopbarInfo />
        <KSeFConnectionTile />
      </div>
    </header>
  );
}
