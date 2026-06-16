# IFGM Dashboard UX Fix

**Data:** 2026-05-22  
**Kontekst:** pierwszy test na iPhone  
**Zakres:** layout dashboardu + globalna lista ostatnich zakupów KSeF

---

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `mobile-expo/app/dashboard.tsx` | UX hero, KPI poziome, ostatnie KSeF z osobnego fetchu |
| `mobile-expo/src/api/mobile.ts` | `fetchRecentKsefPurchaseInvoices()` |

**Nie zmieniono:** backend, logowanie, listy FV, płatności, rozrachunki, KSeF sync, `KpiTile.tsx`.

---

## Opis zmian UX

### 1. FV sprzedaż / FV zakup (wariant A)

- Dwa małe przyciski przeniesione **do kafelka podsumowania** (pod VAT).
- Usunięto osobną sekcję `quickLinks` na dole ekranu.
- Nawigacja bez zmian: `?month=YYYY-MM` z aktualnie wybranego okresu.

### 2. Kwota VAT

- `vatValue` font: **23 → 16** (~30% mniej).
- Etykieta VAT (`vatLabel`) bez zmian (17).
- Sprzedaż/zakup netto bez zmian (20).

### 3. KPI poziome

- Zastąpiono siatkę `KpiTile` lokalnym `HorizontalKpiTile` w `dashboard.tsx`.
- Układ: etykieta + opis po lewej, główna wartość po prawej, pełna szerokość.
- Nawigacja bez zmian: `/debtors`, `/creditors`, `/payments-unassigned`, `/ksef`.
- Styl: ciemne tło, złote akcenty, zgodny z IFGM.

### 4. Ostatnie zakupy KSeF — odpięcie od miesiąca

**Tak — udało się bez zmiany backendu.**

| Aspekt | Zachowanie |
|--------|------------|
| KPI / podsumowanie | Nadal z `GET /api/v1/mobile/dashboard?period=YYYY-MM` |
| Ostatnie zakupy KSeF | Osobny fetch przy wejściu na dashboard, **nie** przeładowuje się przy zmianie miesiąca |

**Endpoint:** `GET /api/v1/invoices/?direction=purchase&page=1&size=50` (bez `month`)

**Logika klienta (`fetchRecentKsefPurchaseInvoices`):**
- filtr: tylko faktury z `ksef_reference_number`,
- sortowanie: `issue_date` malejąco,
- limit: 5 pozycji.

**Uzasadnienie:** endpoint dashboardu (`recent_purchase_invoices`) jest filtrowany po `period` w `MobileService._recent_purchase_invoices`. Lista faktur zakupu bez `month` zwraca globalnie najnowsze (sort `created_at desc` po stronie backendu); dodatkowe sortowanie po `issue_date` i filtr KSeF po stronie mobile.

**Ograniczenie:** pobierane są max 50 ostatnich zakupów z API — przy bardzo dużej bazie starsze pozycje KSeF poza tym oknem nie trafią do listy (akceptowalne dla pilotażu).

---

## Testy

| Test | Wynik |
|------|-------|
| `cd mobile-expo && npm run lint` | OK |
| `cd mobile-expo && npx tsc --noEmit` | OK |
| Backend | Nie zmieniano — testy pominięte |

---

## Ryzyka

| Ryzyko | Ocena |
|--------|-------|
| Limit 50 FV przy pobieraniu ostatnich KSeF | Niskie w pilocie |
| `KpiTile` nadal używany w innych miejscach — brak regresji | Brak wpływu |
| Podwójny request przy wejściu (dashboard + recent KSeF) | Akceptowalne (+1 GET invoices) |

---

*IFGM Dashboard UX Fix — po pierwszym teście iPhone.*
