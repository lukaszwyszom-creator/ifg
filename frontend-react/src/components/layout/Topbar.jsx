import { useLocation } from 'react-router-dom';
import { useAuthStore } from '../../store/useAuthStore';
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
  const user = useAuthStore((s) => s.user);
  const monthYear = getCurrentMonthYear();
  const invoicesTitle = (
    <>
      Faktury bieżące sprzedaży - <span className={styles.pageTitleAccent}>{monthYear}</span>
    </>
  );
  const pageTitles = {
    '/invoices': invoicesTitle,
    '/dashboard': 'Dashboard',
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
        <div className={styles.userBadge}>
          <span className={styles.userIcon}>👤</span>
          <span className={styles.userName}>{user?.username ?? 'operator'}</span>
        </div>
      </div>
    </header>
  );
}
