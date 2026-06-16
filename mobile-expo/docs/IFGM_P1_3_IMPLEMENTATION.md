# IFGM P1.3 — ujednolicenie okresu dashboard ↔ listy FV

**Data:** 2026-05-22  
**Zakres:** przekazanie `month=YYYY-MM` z dashboardu do list faktur

---

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `mobile-expo/src/api/mobile.ts` | `parseMonthParam()`, opcjonalny `month` w `fetchInvoices` |
| `mobile-expo/app/dashboard.tsx` | Quick linki FV z `?month=YYYY-MM` z aktualnego okresu |
| `mobile-expo/app/sales-invoices.tsx` | Odczyt `month` z query; przekazanie do API; subtitle „Okres: …” |
| `mobile-expo/app/purchase-invoices.tsx` | Analogicznie |

---

## Przekazywanie okresu

Dashboard przechowuje okres jako **`periodYear` + `periodMonth`** (state lokalny), serializowany funkcją `periodKey()` → `"YYYY-MM"`.

Quick linki:
```
/sales-invoices?month=2026-05
/purchase-invoices?month=2026-05
```

Listy odczytują parametr przez `useLocalSearchParams`, walidują `parseMonthParam()` i przekazują do `fetchInvoices`.

Bez globalnego store — wyłącznie URL query params.

---

## Parametr API

Gdy `month` jest poprawny:
```
GET /api/v1/invoices/?direction=sale|purchase&page=1&size=100&month=YYYY-MM
```

Backend filtruje po `issue_date` w przedziale `[pierwszy dzień miesiąca, pierwszy dzień następnego miesiąca)`.

---

## Zachowanie przy braku / błędnym month

| Scenariusz | Zachowanie |
|------------|------------|
| Brak `?month` w URL | `fetchInvoices` bez parametru `month` — jak P1.2 (wszystkie faktury, max 100) |
| Błędny format (`2026-2`, `foo`) | `parseMonthParam` → `undefined`; month nie wysyłany do API |
| Miesiąc poza 01–12 | Odrzucony; month nie wysyłany |
| Subtitle listy | Pokazywany tylko gdy month poprawny |

Aplikacja nie crashuje przy złym query param.

---

## Testy

| Test | Wynik |
|------|-------|
| `mobile-expo`: `npm run lint` | **PASS** |
| `mobile-expo`: `npx tsc --noEmit` | **PASS** |
| `test_month_filter_expands_to_date_range` | **PASS** |
| `test_month_with_no_data_returns_empty_list` | **PASS** |
| `test_month_december_rolls_over_year` | **PASS** |
| `test_invalid_month_format_rejected` | **PASS** |

---

## Ryzyka i ograniczenia

1. **Wejście poza dashboardem** — bezpośredni `/sales-invoices` bez `month` nadal pobiera listę bez filtra daty.
2. **Paginacja** — nadal max 100 faktur na miesiąc.
3. **Brak synchronizacji wstecz** — zmiana okresu na dashboardzie nie aktualizuje już otwartej listy (lista ma własny URL).
4. **Ostatnie zakupy KSeF** na dashboardzie używają tego samego okresu co KPI, ale link do szczegółu faktury nie przenosi `month` (poza zakresem).

---

*IFGM P1.3 — minimalny diff, bez nowej architektury stanu.*
