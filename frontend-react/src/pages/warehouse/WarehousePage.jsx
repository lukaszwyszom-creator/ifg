import { useState } from 'react';
import BalanceTab from './tabs/BalanceTab';
import CatalogTab from './tabs/CatalogTab';
import DocumentsTab from './tabs/DocumentsTab';
import styles from './WarehousePage.module.css';

const TABS = [
  { key: 'balance', label: 'Stany' },
  { key: 'documents', label: 'Dokumenty' },
  { key: 'fiscal', label: 'Raporty fiskalne' },
  { key: 'catalog', label: 'Kartoteka' },
];

export default function WarehousePage() {
  // Domyślny widok: Stany (nie Kartoteka)
  const [tab, setTab] = useState('balance');

  const handleAddItem = () => setTab('catalog');

  return (
    <div className={styles.page}>
      <h1 className={styles.pageTitle}>Magazyn</h1>

      <div className={styles.tabs}>
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            className={`${styles.tab}${tab === key ? ` ${styles.tabActive}` : ''}`}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className={styles.tabContent}>
        {tab === 'balance' && <BalanceTab onAddItem={handleAddItem} />}
        {tab === 'documents' && <DocumentsTab />}
        {tab === 'fiscal' && (
          <div className={styles.emptyState}>
            <p className={styles.emptyMsg}>Raporty fiskalne — dostępne w kolejnym etapie</p>
          </div>
        )}
        {tab === 'catalog' && <CatalogTab />}
      </div>
    </div>
  );
}
