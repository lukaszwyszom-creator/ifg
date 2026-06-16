# IFGM Invoice Detail — poprawka pozycji faktury

**Data:** 2026-05-22  
**Zakres:** `/invoice/[id]` — sekcja pozycji

---

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `mobile-expo/src/api/mobile.ts` | Rozszerzony `InvoiceItemResponse`, helpery mapowania i formatowania |
| `mobile-expo/app/invoice/[id].tsx` | Nowy układ pozycji, użycie `mapInvoiceItemForDisplay` |

**Nie zmieniono:** backend, dashboard, listy FV, płatności, KSeF.

---

## Realna struktura `items[]` z API

Źródło: `GET /api/v1/invoices/{id}` → `InvoiceItemResponse` (`app/schemas/invoice.py`).

```json
{
  "id": "uuid | null",
  "name": "string",
  "quantity": "decimal string",
  "unit": "string",
  "unit_price_net": "decimal string",
  "vat_rate": "decimal string",
  "net_total": "decimal string",
  "vat_total": "decimal string",
  "gross_total": "decimal string",
  "sort_order": 0,
  "isbn": "string | null"
}
```

**Poprzedni typ mobile** znał tylko `net_total`, `vat_total`, `gross_total` — pomijał `unit_price_net` i `vat_rate`, przez co UI nie mógł wyliczyć brakujących kwot gdy `net_total`/`vat_total` były zerowe w odpowiedzi.

---

## Mapowanie pól pozycji (UI)

| Kolumna UI | Źródło |
|------------|--------|
| lp. | `sort_order` (jeśli > 0) lub `index + 1` |
| nazwa | `name` → fallback „Pozycja” |
| ilość | `quantity` + `unit` → fallback „—” |
| kwota netto | `net_total` → jeśli ≤0: `unit_price_net × quantity` → jeśli brak: `gross_total − vat_total` |
| stawka VAT | `vat_rate` → jeśli brak i net>0: `vat / net × 100` |
| kwota VAT | `vat_total` → jeśli brak: `net × vat_rate / 100` → jeśli brak: `gross − net` |

Formatowanie:
- brak danych / nienumeryczne → **„—”** (nie „0 zł”),
- kwoty z separatorem PLN przez `formatAmountOrDash`,
- stawka przez `formatVatRateOrDash` (np. `23%`).

**Brutto pozycji** nie jest wyświetlane — tylko w podsumowaniu faktury u góry.

---

## Fałszywe 0 zł — uniknięcie

| Przypadek | Zachowanie |
|-----------|------------|
| `net_total: "0.00"`, ale jest `unit_price_net` | Wyliczenie netto z ceny × ilość |
| `vat_total: "0.00"`, jest netto i `vat_rate` | Wyliczenie VAT (0% → „0 zł” jest poprawne) |
| Wszystkie pola puste / zero bez możliwości wyliczenia | „—” zamiast „0 zł” |
| `formatPln` na pustym polu (wcześniej) | Zastąpione `formatAmountOrDash` |

---

## Układ na iPhone

Wielowierszowy blok na pozycję:
1. `{lp}. {nazwa}`
2. `Ilość: X szt.`
3. trzy kolumny: Netto | VAT % | Kwota VAT

---

## Ograniczenia backendu

- Jeśli API zwraca **wyłącznie** `gross_total` na pozycji (bez netto, VAT, ceny jednostkowej i stawki), mobile pokaże „—” dla netto/VAT — **bez zgadywania** z brutto faktury.
- Sortowanie pozycji: kolejność z tablicy API (backend: `sort_order` / `created_at` w repo).
- Backend **zwraca** pełne pola — problem wynikał głównie z niepełnego typu TS i braku fallbacków w UI, nie z braku pól w schemacie.

---

## Testy

| Test | Wynik |
|------|-------|
| `npm run lint` | OK |
| `npx tsc --noEmit` | OK |

---

*IFGM Invoice Detail Items Fix — frontend bez zmian backendu.*
