import { useLocation } from 'react-router-dom';
import KSeFConnectionTile from './KSeFConnectionTile';
import styles from './Topbar.module.css';

function getCurrentMonthYear() {
  const monthYear = new Intl.DateTimeFormat('pl-PL', {
    month: 'long',
    year: 'numeric',
  }).format(new Date());
  return monthYear;
}

export default function Topbar({ onMenuToggle }) {
  const location = useLocation();
  const monthYear = getCurrentMonthYear();
  const invoicesTitle = (
    <>
      <span className={styles.pageTitlePrefix}>Faktury bieżące sprzedaży - </span>
      <span className={styles.pageTitleAccent}>{monthYear}</span>
    </>
  );
  const pageTitles = {
    '/invoices': invoicesTitle,
    '/dashboard': <span className={styles.pageTitleGold}>Zestawienia: sprzedaż / zakup</span>,
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
        <KSeFConnectionTile />
      </div>
    </header>
  );
}
