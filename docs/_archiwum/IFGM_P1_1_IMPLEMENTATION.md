# IFGM P1.1 — podłączenie szczegółów faktury do API

**Data:** 2026-05-22  
**Zakres:** `/invoice/[id]` → `GET /api/v1/invoices/{id}`

---

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `mobile-expo/src/api/mobile.ts` | Typy `InvoiceResponse`, `InvoiceItemResponse`; `fetchInvoice(id)` |
| `mobile-expo/app/invoice/[id].tsx` | Usunięto mock `allInvoices`; fetch API; loading/error/retry; 401 → logout |

**Backend:** bez zmian — wykorzystano istniejący endpoint.

---

## Endpoint

**Użyto istniejącego:** `GET /api/v1/invoices/{invoice_id}`  
**Nowy endpoint mobile:** nie dodano.

Endpoint zwraca `InvoiceResponse` z polami m.in.:
- identyfikacja: `id`, `number_local`, `ksef_reference_number`, `direction`
- kontrahent: `seller_snapshot`, `buyer_snapshot` (dict: `name`, `nip`)
- kwoty: `total_gross`, `paid_amount`, `remaining_amount`, `payment_status`
- daty: `issue_date`, `due_date`
- pozycje: `items[]` (`name`, `quantity`, `unit`, `net_total`, `vat_total`)

Przykład (skrócony):

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "number_local": "FV/7/05/2026",
  "direction": "sale",
  "issue_date": "2026-05-18",
  "due_date": "2026-06-01",
  "ksef_reference_number": null,
  "payment_status": "unpaid",
  "total_gross": "2460.00",
  "paid_amount": "0.00",
  "remaining_amount": "2460.00",
  "seller_snapshot": { "name": "...", "nip": "..." },
  "buyer_snapshot": { "name": "ABC Sp. z o.o.", "nip": "5250001001" },
  "items": [
    {
      "name": "Usługa konsultingowa",
      "quantity": "10",
      "unit": "godz.",
      "net_total": "2000.00",
      "vat_total": "460.00"
    }
  ]
}
```

---

## Mapowanie UI

| UI | Źródło API |
|----|------------|
| Kontrahent (sprzedaż) | `buyer_snapshot` |
| Kontrahent (zakup) | `seller_snapshot` |
| Numer faktury | `number_local` → fallback `ksef_reference_number` |
| Status płatności | `payment_status` (lub wyliczenie z kwot) |
| Brutto / zapłacono / pozostało | `total_gross`, `paid_amount`, `remaining_amount` |
| Pozycje | `items[]` |
| Historia | wyliczona z API (wystawienie/KSeF + ewentualna płatność) — brak dedykowanego endpointu historii |

Nawigacja bez zmian:
- `/debtors/[id]` → `/invoice/{invoice_id}`
- `/creditors/[id]` → `/invoice/{invoice_id}`
- dashboard (ostatnie zakupy) → `/invoice/{id}`

---

## Testy

| Test | Wynik |
|------|-------|
| `mobile-expo`: `npm run lint` (`tsc --noEmit`) | **PASS** |
| `tests/unit/test_mobile_api.py` | **6 passed** |
| `tests/unit/test_invoice_api.py::TestGetInvoice` | **3 passed** |

Brak dedykowanych testów jednostkowych frontendu dla faktury w `mobile-expo/`.

---

## Pozostałe mocki w IFGM (po P1.1)

| Ekran | Mock danych |
|-------|-------------|
| `/sales-invoices` | `salesInvoices` |
| `/purchase-invoices` | `purchaseInvoices` |
| `/settlements` | `salesInvoices`, `purchaseInvoices`, `debtors` |
| `/payments-unassigned` | `unassignedPayments` |
| `/ksef` | `dashboardMock` |

**Helper (nie mock danych):** `formatPln` z `@/data/mock` — używany w ekranach API.

**Na realnym API:** login, dashboard, dłużnicy, wierzyciele, **szczegół faktury**.

---

## Znane ograniczenia

1. **Historia płatności** — uproszczona (wystawienie + suma zapłacona); pełna historia wymaga `GET /payments/invoice/{id}/history` (poza zakresem).
2. **Listy FV** (`/sales-invoices`, `/purchase-invoices`) — nadal mocki.
3. **Płatności, KSeF, rozrachunki** — bez zmian.

---

*IFGM P1.1 — minimalny diff, layout bez zmian.*
