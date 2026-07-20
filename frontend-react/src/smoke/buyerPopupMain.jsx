/**
 * Smoke mount dla GWO-IFG-0027 — rzeczywisty InvoiceCardList + mock sale invoice.
 * Nie jest częścią production routing; tylko weryfikacja hover w przeglądarce.
 */
import React from 'react';
import { createRoot } from 'react-dom/client';
import InvoiceCardList from '../components/invoice/InvoiceCardList';
import '../styles/theme.css';

const mockInvoice = {
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
    city: 'Warszawa',
    phone: '+48 500 100 200',
    email: 'kontakt@acme-smoke.example',
  },
  totals: { gross: 1230.0, net: 1000.0 },
};

createRoot(document.getElementById('root')).render(
  <div style={{ padding: 24, maxWidth: 1100, margin: '0 auto' }}>
    <h1 style={{ fontSize: 16, marginBottom: 12 }}>Buyer popup smoke</h1>
    <InvoiceCardList
      direction="sale"
      showKsefStatus={false}
      items={[mockInvoice]}
      emptyMsg="Brak"
    />
  </div>,
);
