# IFGM P2.2 — przypisywanie i zmiana przypisania płatności

**Data:** 2026-05-22  
**Zakres:** aktywacja przypisywania na `/payments-unassigned`

---

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `mobile-expo/src/api/mobile.ts` | `allocatePayment`, `reversePaymentAllocation`, `fetchInvoicePaymentHistory`, `searchInvoices`, `fetchPaymentsForAssignment`, `apiDelete` |
| `mobile-expo/app/payments-unassigned.tsx` | Modal wyboru faktury; akcje przypisz / zmień przypisanie |

**Backend:** bez zmian — wykorzystano istniejące endpointy.

---

## Wykorzystane endpointy

| Operacja | Endpoint |
|----------|----------|
| Lista płatności | `GET /payments/transactions?match_status=unmatched\|partial\|manual_review` |
| Wyszukiwanie faktur | `GET /invoices/?direction=sale\|purchase&number_filter=…` |
| Przypisanie | `POST /payments/transactions/{id}/allocate` body: `{ invoice_id, amount }` |
| Cofnięcie przypisania | `DELETE /payments/allocations/{allocation_id}` |
| Historia (reassign) | `GET /payments/invoice/{invoice_id}/history` |

Brak dedykowanego endpointu „reassign” — zmiana = **reverse + allocate**.

---

## Przepływ przypisania

1. Użytkownik klika **„Przypisz do faktury →”** (gdy `remaining_amount > 0`).
2. Modal: wyszukiwanie faktury (min. 2 znaki) po numerze/kontrahencie.
3. Wybór faktury → `POST …/allocate` z kwotą = saldo płatności.
4. Sukces → komunikat + odświeżenie listy.

---

## Przepływ zmiany przypisania

1. Użytkownik klika **„Zmień przypisanie”** (transakcje `partial` / `manual_review`).
2. Krok 1 — wybór faktury z **błędnym** przypisaniem.
3. `GET /payments/invoice/{id}/history` → znalezienie alokacji dla `transaction_id`.
4. Krok 2 — wybór **nowej** faktury.
5. `DELETE /payments/allocations/{id}` → `POST …/allocate` (ta sama kwota co stara alokacja).
6. Sukces → komunikat + odświeżenie listy.

---

## Przyciski

| Akcja | Stan |
|-------|------|
| „Przypisz do faktury →” | **Aktywny** — otwiera modal |
| „Zmień przypisanie” | **Aktywny** — dwuetapowy modal |

---

## Testy

| Test | Wynik |
|------|-------|
| `mobile-expo`: `npm run lint` | **PASS** |
| `mobile-expo`: `npx tsc --noEmit` | **PASS** |
| `test_payment_service.py::TestAllocateManual` | **5 passed** |
| `test_payment_service.py::TestReverseAllocation` | **2 passed** |

---

## Pozostałe mocki (po P2.2)

| Ekran | Mock |
|-------|------|
| `/settlements` | `salesInvoices`, `purchaseInvoices`, `debtors` |
| `/ksef` | `dashboardMock` |

---

## Ograniczenia

1. **Brak GET alokacji per transakcja** — reassign wymaga wyboru faktury z błędnym przypisaniem + historii faktury.
2. **Wyszukiwanie faktur** — min. 2 znaki; max ~40 wyników (20 sale + 20 purchase).
3. **Zmiana kwoty przy reassign** — nieobsługiwana; przenoszona jest kwota starej alokacji.
4. **Częściowe przypisanie reszty** — możliwe przez „Przypisz”, ale bez edycji kwoty w UI (pełne saldo).
5. **Paginacja listy płatności** — max 200 per status.
6. **Brak endpointu reassign atomowego** — ryzyko niespójności przy błędzie między DELETE a POST (backend obsługuje osobno).

---

*IFGM P2.2 — przypisywanie płatności na istniejącym backendzie IFG.*
