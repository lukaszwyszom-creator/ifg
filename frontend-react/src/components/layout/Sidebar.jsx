import { NavLink, useNavigate } from 'react-router-dom';
import { useAppStore } from '../../store/useAppStore';
import { useAuthStore } from '../../store/useAuthStore';
import { ksefApi } from '../../api/ksef';
import styles from './Sidebar.module.css';
import logo from '../../assets/logo-ifg.png';

const NAV_ITEMS = [
  { to: '/invoices', label: 'Faktury sprzedaży', icon: '📄' },
  { to: '/dashboard', label: 'Zestawienia', icon: '📊' },
  { to: '/payments', label: 'Płatności', icon: '💳' },
  { to: '/warehouse', label: 'Magazyn', icon: '📦' },
  { to: '/settings', label: 'Ustawienia firmy', icon: '⚙️' },
];

export default function Sidebar({ open = false, onClose }) {
  const sellerNip = useAppStore((s) => s.sellerNip);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  const handleLogout = async () => {
    if (sellerNip) {
      try {
        await ksefApi.closeSession(sellerNip);
      } catch {
        // Zamknięcie sesji nie powiodło się lub sesja już nieaktywna — ignorujemy
      }
    }
    logout();
    navigate('/login');
  };

  const handleNav = () => {
    // zamknij sidebar na mobile po kliknięciu w link
    onClose?.();
  };

  return (
    <aside className={`${styles.sidebar} ${open ? styles.sidebarOpen : ''}`}>
      <div className={styles.logo}>
        <img src={logo} alt="IFG" className={styles.logoImg} />
        <span className={styles.logoText}>Imperium Faktur G</span>
      </div>

      <div className={styles.sellerInfo}>
        <span className={styles.sellerBrand}>IKONA</span>
        <span className={styles.sellerLine}>Małgorzata Katarzyna</span>
        <span className={styles.sellerLine}>Krzyżanowska-Witkowska</span>
        <span className={styles.sellerLine}>ul. Kossaka 72</span>
        <span className={styles.sellerLine}>85-307 Bydgoszcz</span>
        <span className={styles.sellerMeta}>NIP 9670402857</span>
        <span className={styles.sellerMeta}>REGON 366321403</span>
      </div>

      <nav className={styles.nav}>
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={handleNav}
            className={({ isActive }) =>
              `${styles.navItem} ${isActive ? styles.navActive : ''}`
            }
          >
            <span className={styles.navIcon}>{item.icon}</span>
            <span className={styles.navLabel}>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className={styles.bottom}>
        <button className={styles.logoutBtn} onClick={handleLogout}>
          <span>↩</span> Wyloguj
        </button>
      </div>
    </aside>
  );
}
