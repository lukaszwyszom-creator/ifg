# IFGM P2.1 — płatności do przypisania

**Data:** 2026-05-22  
**Zakres:** `/payments-unassigned` → realne API

---

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `mobile-expo/src/api/mobile.ts` | `UnassignedPayment`, `fetchUnassignedPayments()`, helpery wyświetlania |
| `mobile-expo/app/payments-unassigned.tsx` | Mock `unassignedPayments` usunięty; fetch API; loading/error/retry |

**Backend:** bez zmian.

---

## Użyty endpoint

Brak dedykowanego `GET /payments/unassigned`.

**Realny odpowiednik:**
```
GET /api/v1/payments/transactions?match_status=unmatched&page=1&size=200
```

Odpowiedź: `TransactionListResponse` z `items[]` typu `BankTransactionResponse`.

---

## Mapowanie API → UI

| UI | Pole API |
|----|----------|
| `id` (klucz listy) | `id` |
| Kontrahent | `counterparty_name` → fallback „Nieznany kontrahent” |
| Kwota | `remaining_amount` (jeśli > 0), inaczej `amount` |
| Tytuł przelewu | `title` → fallback „—” |
| Data | `transaction_date` → `YYYY-MM-DD` |
| Konto (opcjonalnie) | `counterparty_account` |
| Subtitle licznik | `total` z odpowiedzi |
| Subtitle suma | suma `remaining_amount` / `amount` z pobranych pozycji |

Pola niedostępne w API (poza zakresem): `suggested_invoice_id`, `suggested_invoice_number`.

---

## Przycisk „Przypisz do faktury”

**Disabled (placeholder)** — tekst widoczny ze stylem `actionBtnDisabled` (opacity 0.6, kolor muted), brak `onPress`.  
Pod listą: „Przypisywanie płatności — w kolejnym etapie.”

---

## Testy

| Test | Wynik |
|------|-------|
| `mobile-expo`: `npm run lint` | **PASS** |
| `mobile-expo`: `npx tsc --noEmit` | **PASS** |
| Testy backendowe płatności nieprzypisanych | **Brak dedykowanych** (`test_payments_api.py` — tylko settlements) |

---

## Pozostałe mocki (po P2.1)

| Ekran | Mock |
|-------|------|
| `/settlements` | `salesInvoices`, `purchaseInvoices`, `debtors` |
| `/ksef` | `dashboardMock` |

**Helper (nie mock danych):** `formatPln` w wielu ekranach API.

---

## Ryzyka i ograniczenia

1. **Filtr `match_status=unmatched`** — nie obejmuje `partial` ani `manual_review` (transakcje częściowo przypisane).
2. **Rozjazd z KPI dashboardu** — dashboard sumuje wszystkie transakcje (`match_status` bez filtra, size 500); lista pokazuje tylko `unmatched`.
3. **Paginacja** — max 200 pozycji; przy większej liczbie lista niepełna.
4. **Przypisywanie** — celowo niezaimplementowane (P2.2+).

---

*IFGM P2.1 — lista płatności na realnym API, bez akcji allocate.*
