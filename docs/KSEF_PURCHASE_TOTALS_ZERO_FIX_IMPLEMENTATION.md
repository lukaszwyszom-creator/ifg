# KSeF purchase totals zero — raport implementacji

**Data weryfikacji:** 2026-06-13  
**Specyfikacja:** [KSEF_PURCHASE_TOTALS_ZERO_FIX.md](./KSEF_PURCHASE_TOTALS_ZERO_FIX.md)  
**Commit:** `27fa7e4` — `fix(ksef): purchase totals fallback from line items when header P_13/P_14 missing.`

---

## Zakres (zgodnie z poleceniem)

| Plik | Status |
|------|--------|
| `app/integrations/ksef/xml_parser.py` | Zaimplementowane |
| `tests/unit/test_ksef_xml_parser.py` | Zaimplementowane |
| Frontend | Bez zmian |
| Repair historyczny | **Nie uruchamiano** |

---

## Zmiany w kodzie

### `xml_parser.py`

1. **`_sum_item_totals(items)`** — suma `net_total`, `vat_total`, `gross_total` z sparsowanych pozycji (quantize 2 miejsca).

2. **`_resolve_totals_with_item_fallback(...)`** — po `_extract_totals()` z nagłówka:
   - jeśli brak `P_13_*` / `P_14_*` (net/vat = 0), a pozycje mają kwoty → uzupełnia net/VAT z pozycji;
   - jeśli jest `P_15` i net z pozycji, a VAT pozycji = 0 → `total_vat = P_15 - net`;
   - nie nadpisuje poprawnych wartości z nagłówka (`P_13_1`, `P_14_1`, `P_15`).

3. **`_build_parsed_invoice_payload`** — najpierw parsuje pozycje, potem stosuje fallback na totals (jedna lista `items` używana w payloadzie).

### `test_ksef_xml_parser.py`

| Test | Scenariusz | Oczekiwany wynik |
|------|------------|------------------|
| `test_parse_fa3_xml_totals_fallback_from_items_when_header_p13_missing` | Tylko `P_15` + linia `P_11A`/`P_9B` | net=219.51, vat=50.49, gross=270.00 |
| `test_parse_fa3_xml_header_totals_not_overwritten_by_item_fallback` | Pełny nagłówek P_13/P_14/P_15 | net=100, vat=23, gross=123 (bez nadpisania) |

---

## Diff (commit `27fa7e4`, pliki w zakresie)

```
app/integrations/ksef/xml_parser.py          | +58 linii (_sum_item_totals, _resolve_totals_with_item_fallback, hook w _build_parsed_invoice_payload)
tests/unit/test_ksef_xml_parser.py           | +83 linii (2 testy regresji)
```

Pełny diff: `git show 27fa7e4 -- app/integrations/ksef/xml_parser.py tests/unit/test_ksef_xml_parser.py`

---

## Wynik testów (weryfikacja lokalna)

```bash
.venv/bin/pytest tests/unit/test_ksef_xml_parser.py -q
```

```
7 passed in 0.05s
```

---

## Wpływ na runtime

- **Nowe importy KSeF (purchase):** `ksef_session_service` kopiuje `parsed["total_net/vat/gross"]` do `Invoice` → `totals_json` będzie poprawne od razu.
- **Dane historyczne:** wymagają osobnego skryptu `scripts/repair_purchase_totals_from_items.py` (poza zakresem tego wdrożenia).

---

## Ryzyka

| Ryzyko | Mitigacja |
|--------|-----------|
| Stare rekordy z zerowym net/VAT | Repair skryptem (dry-run domyślnie) |
| Faktury zw/exempt (VAT=0, net>0) | Fallback nie nadpisuje poprawnego netto z nagłówka |
| Rozbieżność sum pozycji vs P_15 | Priorytet nagłówka gdy P_13/P_14 obecne |

---

## Commit message (użyty)

```
fix(ksef): purchase totals fallback from line items when header P_13/P_14 missing.

When FA(3) purchase invoices have P_15 and line amounts but no header net/VAT,
derive totals_json from parsed items instead of leaving net/vat at zero.
```
