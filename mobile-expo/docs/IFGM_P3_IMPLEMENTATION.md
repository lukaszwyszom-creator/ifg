# IFGM P3 — rozrachunki (/settlements)

**Data:** 2026-05-22  
**Zakres:** podłączenie `/settlements` do realnego API

---

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `mobile-expo/src/api/mobile.ts` | `SettlementItem`, `fetchSettlements()`, helpery wyświetlania |
| `mobile-expo/app/settlements.tsx` | Usunięto mocki; fetch API; loading/error/retry |

**Backend:** bez zmian.

---

## Usunięte mocki z /settlements

- `salesInvoices`
- `purchaseInvoices`
- `debtors`
- Etykiety demo („Agregat dłużników (demo)”, „Wierzyciele — widok listy”)

---

## Użyty endpoint

```
GET /api/v1/payments/settlements?side=all
```

Odpowiedź `SettlementSummaryResponse`:
- `debtors[]` — otwarte należności (faktury sprzedaży, `remaining_amount > 0`)
- `creditors[]` — otwarte zobowiązania (faktury zakupu, `remaining_amount > 0`)

Backend filtruje pozycje z zerowym saldem w `PaymentService.get_settlement_summary()`.

---

## Mapowanie API → UI

| UI | Pole API |
|----|----------|
| Tab Należności | `debtors[]` |
| Tab Zobowiązania | `creditors[]` |
| Kontrahent | `contractor_name` |
| Numer faktury | `number_local` → `ksef_reference_number` |
| Termin | `due_date` → `dueLabel()` |
| Kwota pozostała | `remaining_amount` |
| Nawigacja wiersza | `/invoice/{invoice_id}` |
| Karta agregatu (należności) | `/debtors` |
| Karta agregatu (zobowiązania) | `/creditors` |
| Liczba kontrahentów | unikalne `contractor_name` w aktywnej liście |
| Suma | suma `remaining_amount` w aktywnej liście |

---

## Sekcje /settlements po P3

1. **Taby** — Należności / Zobowiązania (bez zmian layoutu)
2. **Karta agregatu** — liczba kontrahentów + suma salda; link do `/debtors` lub `/creditors`
3. **Lista faktur** — kontrahent, numer, termin, kwota pozostała → szczegół faktury

Brak sekcji płatności do przypisania (nie było w poprzednim layoutcie).

Brak filtra miesiąca (nie było w UI; endpoint obsługuje `month=YYYY-MM` na przyszłość).

---

## Testy

| Test | Wynik |
|------|-------|
| `mobile-expo`: `npm run lint` | **PASS** |
| `mobile-expo`: `npx tsc --noEmit` | **PASS** |
| `tests/unit/test_payments_api.py` | **2 passed** |

---

## Pozostałe mocki w IFGM

| Ekran | Mock danych |
|-------|-------------|
| `/ksef` | `dashboardMock` |

**Helper (nie mock):** `formatPln` w ekranach API.

---

## Ryzyka i ograniczenia

1. **Brak filtra miesiąca** — endpoint wspiera `month`, UI jeszcze nie.
2. **Paginacja** — endpoint zwraca pełną listę otwartych pozycji (bez limitu stron w mobile); przy bardzo dużej liczbie faktur może być wolne.
3. **Spójność z `/debtors`/`/creditors`** — agregaty po kontrahentach liczone inaczej (mobile API grupuje po nazwie; settlements to lista faktur).
4. **Waluty** — wyświetlane salda bez konwersji; pozycje niefakturowe w obcej walucie pokazują `currency` z API bez osobnej obsługi UI.

---

*IFGM P3 — rozrachunki na istniejącym endpointzie `/payments/settlements`.*
