/**
 * Smoke mount GWO-IFG-0028 — popup Nabywca + Sprzedawca z miejscowością.
 */
import React from 'react';
import { createRoot } from 'react-dom/client';
import InvoiceCardList from '../components/invoice/InvoiceCardList';
import '../styles/theme.css';

const mockSale = {
  id: 'smoke-sale-1',
  number_local: '01/07/2026',
  issue_date: '2026-07-15',
  due_date: '2026-07-29',
  currency: 'PLN',
  status: 'ISSUED',
  buyer_snapshot: {
    name: 'ACME Kontrahent Smoke Sp. z o.o.',
    nip: '5250000999',
    street: 'ul. Testowa 1',
    postal_code: '00-001',
    city: 'Warszawa',
    country: 'PL',
    phone: '+48 500 100 200',
    email: 'kontakt@acme-smoke.example',
  },
  totals: { gross: 1230.0, net: 1000.0 },
};

const mockPurchase = {
  id: 'smoke-purchase-1',
  number: 'FZ/99/2026',
  issue_date: '2026-07-10',
  due_date: '2026-07-24',
  currency: 'PLN',
  status: 'ISSUED',
  seller_snapshot: {
    name: 'Dostawca Smoke SA',
    nip: '5250000888',
    street: 'ul. Magazynowa 9',
    postal_code: '30-001',
    city: 'Kraków',
    country: 'PL',
    phone: '+48 600 700 800',
    email: 'biuro@dostawca-smoke.example',
  },
  totals: { gross: 500.0, net: 406.5 },
};

createRoot(document.getElementById('root')).render(
  <div style={{ padding: 24, maxWidth: 1100, margin: '0 auto', display: 'grid', gap: 32 }}>
    <section data-smoke-section="sale">
      <h1 style={{ fontSize: 16, marginBottom: 12 }}>Nabywca popup smoke</h1>
      <InvoiceCardList
        direction="sale"
        showKsefStatus={false}
        items={[mockSale]}
        emptyMsg="Brak"
      />
    </section>
    <section data-smoke-section="purchase">
      <h1 style={{ fontSize: 16, marginBottom: 12 }}>Sprzedawca popup smoke</h1>
      <InvoiceCardList
        direction="purchase"
        showKsefStatus={false}
        items={[mockPurchase]}
        emptyMsg="Brak"
      />
    </section>
  </div>,
);
