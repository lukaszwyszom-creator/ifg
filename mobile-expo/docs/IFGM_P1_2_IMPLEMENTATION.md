# IFGM P1.2 — listy faktur sprzedaży i zakupu

**Data:** 2026-05-22  
**Zakres:** `/sales-invoices`, `/purchase-invoices` → `GET /api/v1/invoices`

---

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `mobile-expo/src/api/mobile.ts` | `fetchInvoices`, typ `InvoiceListItem`, helpery listy (`invoiceDisplayNumber`, `contractorNameFromListItem`, `normalizePaymentStatus`, `dueLabel`) |
| `mobile-expo/app/sales-invoices.tsx` | Mock `salesInvoices` → API; loading/error/retry/pusta lista |
| `mobile-expo/app/purchase-invoices.tsx` | Mock `purchaseInvoices` → API; loading/error/retry/pusta lista |

**Backend:** bez zmian.

---

## Endpoint i parametry

**Użyty:** `GET /api/v1/invoices/`

| Parametr | Wartość |
|----------|---------|
| `direction` | `sale` (sprzedaż) / `purchase` (zakup) |
| `page` | `1` |
| `size` | `100` (max backend) |

Nie użyto: `month`, `view`, `status` (status dokumentu), `number_filter` — wyszukiwanie i filtry płatności/KSeF po stronie klienta na pobranej liście (jak wcześniej z mockami).

---

## Mapowanie API → UI

| UI | Pole API |
|----|----------|
| Nawigacja `/invoice/{id}` | `id` |
| Numer | `number_local` → `ksef_reference_number` → „Brak numeru” |
| Kontrahent (sprzedaż) | `buyer_snapshot.name` |
| Kontrahent (zakup) | `seller_snapshot.name` |
| Kwota brutto | `total_gross` |
| Termin (etykieta) | `due_date` → `dueLabel()` |
| Filtr płatności | `payment_status` (`unpaid` / `partial` / `paid`) |
| Filtr „Z KSeF” | `ksef_reference_number` niepuste |
| Wiersz KSeF (zakup) | `ksef_reference_number` |

---

## Przepływ po P1.2

```
Dashboard → FV sprzedaż/zakup → /sales-invoices | /purchase-invoices (API)
                                        ↓
                                  /invoice/[id] (API, P1.1)
```

---

## Testy

| Test | Wynik |
|------|-------|
| `mobile-expo`: `npm run lint` | **PASS** |
| `mobile-expo`: `npx tsc --noEmit` | **PASS** |
| `tests/unit/test_invoice_api.py::TestListInvoices` | **17 passed** |

---

## Pozostałe mocki (po P1.2)

| Ekran | Mock danych |
|-------|-------------|
| `/settlements` | `salesInvoices`, `purchaseInvoices`, `debtors` |
| `/payments-unassigned` | `unassignedPayments` |
| `/ksef` | `dashboardMock` |

**Na realnym API:** login, dashboard, dłużnicy, wierzyciele, szczegół faktury, **listy FV sprzedaż/zakup**.

**Helper (nie mock):** `formatPln` z `@/data/mock`.

---

## Ryzyka i ograniczenia

1. **Paginacja** — pobierana jest tylko pierwsza strona (`size=100`). Przy >100 fakturach w danym kierunku lista będzie niepełna.
2. **Wyszukiwanie** — filtrowane po stronie klienta na max 100 rekordach; backend `number_filter` obsługuje też kontrahenta, ale nie podłączono (minimalny diff).
3. **Filtr „Częściowo” (sprzedaż)** — oparty o `payment_status`; backend nie filtruje listy po tym polu — filtrowanie lokalne.
4. **Brak filtra okresu** — ekrany nie miały selektora miesiąca; backend obsługuje `month=YYYY-MM`, nie wykorzystano.

---

*IFGM P1.2 — layout bez zmian, mocki usunięte z list FV.*
