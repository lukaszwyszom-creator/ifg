# IFGM G2 — audyt P1–P3 (przed KSeF)

**Data:** 2026-05-22  
**Zakres:** ekrany podłączone w fazach P1–P3 (mobile-expo)  
**Cel:** weryfikacja gotowości przed integracją KSeF; tylko krytyczne, małe poprawki

---

## 1. Mocki danych poza `/ksef`

| Ekran | Źródło danych | Mock? |
|-------|---------------|-------|
| `/dashboard` | `fetchDashboard` | Nie |
| `/debtors`, `/debtors/[id]` | `fetchDebtors`, `fetchDebtorDetail` | Nie |
| `/creditors`, `/creditors/[id]` | `fetchCreditors`, `fetchCreditorDetail` | Nie |
| `/sales-invoices`, `/purchase-invoices` | `fetchInvoices` | Nie |
| `/invoice/[id]` | `fetchInvoice` | Nie |
| `/payments-unassigned` | `fetchPaymentsForAssignment` + allocate/reverse | Nie |
| `/settlements` | `fetchSettlements` | Nie |
| `/ksef` | `dashboardMock` | **Tak (zamierzone, poza P1–P3)** |

**Import z `@/data/mock` poza `/ksef`:** wyłącznie `formatPln` (formatowanie PLN, nie dane demo).  
**Wniosek:** po P1–P3 jedyny ekran z mockowanymi danymi biznesowymi to `/ksef`.

---

## 2. Linki nawigacji

| Trasa źródłowa | Cel oczekiwany | Status |
|----------------|----------------|--------|
| Dashboard → FV sprzedaż | `/sales-invoices?month=YYYY-MM` | OK (`dashboard.tsx`) |
| Dashboard → FV zakup | `/purchase-invoices?month=YYYY-MM` | OK |
| Dashboard → dłużnicy | `/debtors` | OK (KPI „Dłużnicy”) |
| Dashboard → wierzyciele | `/creditors` | OK (KPI „Wierzyciele”, poprawione w P1) |
| Dashboard → płatności | `/payments-unassigned` | OK (KPI „Płatności do przypisania”) |
| Dashboard → rozrachunki | `/settlements` | **Brak linku z dashboardu** (celowe od P1 — rozrachunki to osobny ekran; dostęp tylko przez deep link / menu w przyszłości) |
| Dashboard → ostatnie zakupy | `/invoice/{id}` | OK |
| Listy FV → szczegół | `/invoice/{id}` | OK |
| `/settlements` → agregat | `/debtors` / `/creditors` | OK (karta podsumowania) |
| `/settlements` → wiersz | `/invoice/{invoice_id}` | OK |
| `/debtors/[id]`, `/creditors/[id]` → faktura | `/invoice/{invoice_id}` | OK |

---

## 3. Obsługa stanów (loading / error / retry / pusty / 401)

| Ekran | Loading | Error + retry | Pusty stan | 401 → logout |
|-------|---------|---------------|------------|--------------|
| `dashboard.tsx` | Tak | Tak | Tak (brak ostatnich zakupów) | Tak |
| `sales-invoices.tsx` | Tak | Tak | Tak | Tak |
| `purchase-invoices.tsx` | Tak | Tak | Tak | Tak |
| `invoice/[id].tsx` | Tak | Tak | Tak (brak pozycji) | Tak |
| `debtors/index.tsx` | Tak | Tak | Tak | Tak |
| `debtors/[id].tsx` | Tak | Tak | Tak (brak faktur) | Tak |
| `creditors/index.tsx` | Tak | Tak | Tak | Tak |
| `creditors/[id].tsx` | Tak | Tak | Tak (brak faktur) | Tak |
| `payments-unassigned.tsx` | Tak | Tak | Tak | Tak (load + akcje modalne) |
| `settlements.tsx` | Tak | Tak | Tak (per tab) | Tak |

**Wzorzec spójny** we wszystkich ekranach audytowanych.

---

## 4. Fałszywie działające przyciski

| Ekran | Element | Ocena |
|-------|---------|-------|
| `/payments-unassigned` | „Przypisz” / „Zmień przypisanie” | Działa (P2.2 — realne API) |
| `/ksef` | „Pobierz faktury z KSeF” | Demo (setTimeout) — **poza zakresem G2** |
| `/debtors/[id]`, `/creditors/[id]` | Sekcja „Historia notatek” | Statyczny tekst „Brak notatek…” — nie jest przyciskiem; brak akcji windykacji w Mobile API |
| Pozostałe ekrany P1–P3 | — | Brak martwych `onPress` / fałszywych CTA |

---

## 5. Spójność helperów API (`mobile.ts`)

| Pole | Helper | Fallback |
|------|--------|----------|
| Numer faktury (listy, settlements) | `invoiceDisplayNumber`, `settlementDisplayNumber` | `'Brak numeru'` |
| Numer faktury (szczegół) | `invoiceDisplayNumber` (po poprawce G2) | `'Brak numeru'` |
| Kontrahent (listy FV) | `contractorNameFromListItem` | `'Nieznany kontrahent'` |
| Kontrahent (settlements) | `settlementContractorName` | `'Nieznany kontrahent'` |
| Kontrahent (szczegół FV) | lokalny `contractorFromInvoice` | `'Nieznany kontrahent'` / NIP `'—'` |
| Kontrahent (dłużnicy/wierzyciele detail) | pole `inv.number` z API | z backendu |
| Kwota (listy FV) | `invoiceListDisplayAmount` (po poprawce G2) | `remaining_amount` → `total_gross` |
| Kwota (settlements) | `remaining_amount` | bezpośrednio |
| Kwota (płatności) | `unassignedPaymentDisplayAmount` | `remaining_amount` → `amount` |
| Termin | `dueLabel` | `'brak terminu'` |
| Data wystawienia | `formatIssueDate` | `iso.slice(0, 10)` |
| Kwoty numeryczne | `parseAmount` | `0` przy NaN |

**Niespójności pozostawione (niski priorytet, bez poprawki):**
- Szczegół FV ma lokalny `contractorFromInvoice` zamiast wspólnego helpera — duplikacja logiki, nie błąd funkcjonalny.
- Detale dłużników/wierzycieli używają `inv.number` z API agregatu (nie `invoiceDisplayNumber`).

---

## 6. Wprowadzone poprawki (G2)

### 6.1 Kwota na listach FV — `remaining_amount` zamiast `total_gross`

**Problem:** listy sprzedaży/zakupu pokazywały `total_gross`, podczas gdy rozrachunki i dashboard KPI operują na saldzie do zapłaty. Przy częściowej płatności użytkownik widział błędną kwotę.

**Poprawka:** helper `invoiceListDisplayAmount` w `src/api/mobile.ts`; użycie w `sales-invoices.tsx` i `purchase-invoices.tsx`.

### 6.2 Spójny fallback numeru faktury w szczególe

**Problem:** `invoice/[id].tsx` używał lokalnego `invoiceNumber` z fallbackiem `'—'`, podczas gdy reszta aplikacji używa `'Brak numeru'`.

**Poprawka:** import i użycie `invoiceDisplayNumber` z `mobile.ts`.

### 6.3 Wyróżnienie przeterminowanych na listach FV

**Problem:** kolor „po terminie” na liście sprzedaży zależał tylko od `payment_status === 'unpaid'`, ignorując `overdue_days` z API. Lista zakupu nie miała wyróżnienia w ogóle.

**Poprawka:** warunek `overdue_days > 0` + styl `dueOver` (także dodany w `purchase-invoices.tsx`).

---

## 7. Znaleziska bez poprawki (wymagałyby większej zmiany)

| # | Opis | Uzasadnienie braku poprawki |
|---|------|----------------------------|
| 1 | Brak linku dashboard → `/settlements` | Świadoma decyzja P1 (wierzyciele → `/creditors`); dodanie KPI wymaga projektu UI |
| 2 | `/ksef` — pełny mock + demo sync | Osobna faza integracji KSeF |
| 3 | `formatPln` w `@/data/mock` | Refaktor (przeniesienie do utils) — poza zakresem G2 |
| 4 | Limit paginacji list (100 FV, 200 płatności) | Brak infinite scroll — feature, nie bug krytyczny |
| 5 | Subtitle płatności: `total` z odpowiedzi API vs długość `items` | Drobna rozbieżność przy paginacji; brak paginacji w UI |
| 6 | Sekcja windykacji w detalu dłużnika | Brak endpointu Mobile API |
| 7 | Duplikacja `contractorFromInvoice` vs helpery list | Refaktor kosmetyczny |

---

## 8. Testy

```bash
cd mobile-expo && npm run lint    # OK (tsc --noEmit)
cd mobile-expo && npx tsc --noEmit # OK
```

---

## 9. Podsumowanie

Ekrany P1–P3 są podłączone do realnego Mobile API z kompletną obsługą stanów i poprawną nawigacją (poza brakiem bezpośredniego linku do rozrachunków z dashboardu). Jedyny mock danych biznesowych: `/ksef`. W ramach G2 wprowadzono trzy małe poprawki krytyczne dla spójności kwot i numerów faktur oraz wizualizacji przeterminowania.
