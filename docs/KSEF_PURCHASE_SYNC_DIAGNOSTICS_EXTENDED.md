# KSeF — rozszerzona diagnostyka sync zakupów (lipiec 2026)

**Data:** 2026-07-03  
**Gałąź:** production  
**Problem:** Portal KSeF pokazuje faktury zakupowe (np. z 01.07.2026), których IFG nie widzi po synchronizacji.

---

## 1. Werdykt (przed kolejnym sync na prod)

| Warstwa | Podejrzenie | Priorytet |
|---------|-------------|-----------|
| **Okno sync** | Incremental od `last_date_to` z overlap 2 dni — **lipiec powinien być w zakresie** jeśli `date_to=dziś` | Średni — zweryfikować log WINDOW |
| **Metadata / paginacja** | Historycznie `pageOffset+=50`; w kodzie jest `+=1`. Prod może mieć starą wersję lub pustą stronę 2 | **Wysoki** |
| **429 / partial sync** | Metadata pobiera wszystko, GET XML urywa — `xml_not_in_db_count > 0` | **Wysoki** |
| **Zapis DB** | Parse / walidacja pozycji — `refs_skipped_invalid` | Niski (pojedyncze FV) |
| **UI** | Filtr miesiąca po `issue_date`; lipiec 0 może być **brak w DB**, nie filtr UI | Sprawdzić po MISSING |

**Nie wprowadzono doraźnej poprawki logiki sync** — tylko diagnostyka i jawne oznaczanie sync niekompletnego.

---

## 2. Przepływ (skrót)

```
UI/worker → sync_purchase_invoices
  → resolve_purchase_sync_window_details (WINDOW log)
  → query_purchase_metadata_refs (page logs)
  → GET /invoices/ksef/{ref} per ref
  → _process_purchase_invoice_xml (saved / skipped_*)
  → list_ksef_purchase_refs_in_issue_range (MISSING log)
  → SUMMARY + SYNC_INCOMPLETE jeśli trzeba
```

---

## 3. Nowe markery logów

### `KSEF_PURCHASE_SYNC_AUDIT WINDOW`

```
nip, date_from, date_to, source, requested_date_from/to,
force_full, incremental, days_back, overlap_days,
last_date_to, last_date_from, last_success_at, date_types, resume
```

**Źródła `source`:** `request` | `force_full` | `incremental` | `default` | `resume`

### `KSEF_PURCHASE_SYNC_AUDIT REFS`

Dla każdej kategorii: `count`, `first20`, `last20`.  
Pełna lista: **DEBUG** → `KSEF_PURCHASE_SYNC_AUDIT REFS_FULL`.

Kategorie:
- `refs_received_from_metadata`
- `refs_xml_downloaded`
- `refs_saved`
- `refs_skipped_existing`
- `refs_skipped_invalid`
- `refs_skipped_error`

### `KSEF_PURCHASE_SYNC_AUDIT MISSING`

```
metadata_not_in_db_count / _sample
xml_not_in_db_count / _sample
saved_not_in_db_count / _sample
db_extra_count / _sample
incomplete=true|false
```

### `KSEF_PURCHASE_SYNC_AUDIT SYNC_INCOMPLETE`

Gdy: `hasMore=true` + pusta strona, 429, pagination error, skip invalid/error, lub MISSING > 0.

### Status raportu API/worker

- `status=ok` tylko gdy sync kompletny
- `status=incomplete` lub `deferred` + `incomplete=true` w pozostałych przypadkach
- `mark_success` **nie jest wywoływane** gdy sync niekompletny (ochrona high-water-mark)

---

## 4. Analiza `resolve_purchase_sync_window`

### Algorytm (priorytety)

1. **`date_from` w request** → `(date_from, date_to)` — source: `request`
2. **`force_full`** → ostatnie 365 dni — source: `force_full`
3. **`incremental` + `last_date_to` w state** → `(last_date_to - overlap, date_to)` — source: `incremental`
4. **Domyślnie** → `(date_to - days_back, date_to)` — source: `default`
5. **`resume_state`** → source: `resume` (okno jak incremental jeśli jest state)

### Scenariusz lipiec (01.07.2026)

Przy `last_date_to=2026-06-30`, `date_to=2026-07-03`, `overlap=2`:

```
date_from = 2026-06-28
date_to   = 2026-07-03
```

Zakres **obejmuje 01.07.2026**. Metadata query z `PermanentStorage` powinno zwrócić FV z lipca **jeśli KSeF je indeksuje w tym filtrze**.

**Jeśli WINDOW pokazuje `date_to=2026-06-30`** (np. stary job payload) → FV z 01.07 **nie wejdą do metadata** — przyczyna w oknie sync, nie UI.

**Uwaga:** Po niekompletnym sync ze starym kodem `last_date_to` mogło zostać zapisane mimo braków — kolejny incremental startuje od złego HWM. Nowy kod **nie aktualizuje** state przy `incomplete`.

---

## 5. UI — czy faktury „znikają” po zapisie?

| Mechanizm | Wpływ |
|-----------|--------|
| `issue_date` vs filtr miesiąca | `InvoiceList` + `dashboardQuery` filtrują po `issue_date`. FV z `issue_date=2026-07-01` widać w lipcu **jeśli są w DB** |
| `defaultToCurrentMonth` | Dashboard/VATSummary używają bieżącego miesiąca; `InvoiceList` ma `defaultToCurrentMonth: false` — filtr z UI (Filters) |
| `direction` | API: `direction=purchase` w query pool |
| `status` / soft delete | Brak soft delete na `InvoiceORM` |
| NIP / tenant | Sync po NIP sesji; DB comparison filtruje `buyer_snapshot.nip` |
| PermanentStorage vs Issue | Sync query używa 3 dateType; **zapis** używa `issue_date` z XML — UI zawsze po `issue_date` |

**Wniosek:** Lipiec z 0 FV w UI przy obecności w KSeF portalu to **najpewniej brak w DB**, nie ukrycie frontendem — potwierdź `MISSING` i SQL poniżej.

---

## 6. Limity w kodzie (bez zmian)

| Limit | Wartość |
|-------|---------|
| `_METADATA_PAGE_SIZE` | 50 |
| `_METADATA_MAX_PAGES` | 200 (10 000 ref / dateType) |
| `ksef_purchase_sync_days_back` | 90 (default) |
| `ksef_purchase_sync_overlap_days` | 2 |
| Throttle | 1.2 s / request KSeF |

---

## 7. Pliki zmienione

| Plik | Zmiana |
|------|--------|
| `app/services/ksef_purchase_sync_audit.py` | WINDOW, REFS, MISSING, `resolve_purchase_sync_window_details`, ref sets |
| `app/services/ksef_session_service.py` | Window audit, ref tracking, incomplete status, skip mark_success |
| `app/integrations/ksef/client.py` | page refs w audycie, ref tracking download errors |
| `app/persistence/repositories/invoice_repository.py` | `list_ksef_purchase_refs_in_issue_range` |
| `tests/unit/test_ksef_sync_window.py` | **nowy** |
| `tests/unit/test_ksef_purchase_sync_audit.py` | rozszerzony |
| `tests/unit/test_ksef_metadata_pagination.py` | 3 strony pageOffset 0,1,2 |

**Frontend:** bez zmian (build nie wymagany).

---

## 8. Testy

```bash
PYTHONPATH=. .venv/bin/pytest \
  tests/unit/test_ksef_metadata_pagination.py \
  tests/unit/test_ksef_purchase_sync_audit.py \
  tests/unit/test_ksef_sync_window.py \
  tests/unit/test_ksef_session_service.py \
  tests/unit/test_ksef_sync_service.py \
  tests/unit/test_ksef_purchase_sync_resume.py \
  -q
```

**Wynik:** 41 passed

---

## 9. Logi do zebrania z produkcji

Po jednym sync zakupów:

```bash
grep 'KSEF_PURCHASE_SYNC_AUDIT' /path/to/worker.log
```

Minimalny checklist:

1. **WINDOW** — `date_from`, `date_to`, `source`, `last_date_to`, czy 2026-07-01 ∈ [from, to]
2. **page=** — ile stron, ostatnia `hasMore`, czy `PAGINATION_ERROR`
3. **REFS** — `refs_received_from_metadata count` vs portal KSeF
4. **MISSING** — `metadata_not_in_db_count`, sample z numerami KSeF
5. **SUMMARY** / **SYNC_INCOMPLETE** — `incomplete=true`?

SQL weryfikacja:

```sql
SELECT ksef_reference_number, issue_date, created_at
FROM invoices
WHERE direction = 'purchase'
  AND ksef_reference_number IS NOT NULL
  AND issue_date >= '2026-07-01'
ORDER BY issue_date;
```

---

## 10. Następna poprawka (po diagnozie z logów)

| Obserwacja w logach | Poprawka |
|---------------------|----------|
| `pages_downloaded=1`, `metadata_returned=50`, portal >50 | Deploy paginacji / fix prod |
| `metadata_not_in_db_count>0`, `xml_downloaded` pełne | Parser / walidacja pozycji |
| `xml_not_in_db_count>0`, `rate_limited=true` | Exports API lub dłuższe resume |
| WINDOW `date_to` < 2026-07-01 | Payload joba / HWM / force_full |
| `isTruncated=true` | Algorytm shift dateRange MF |
| DB ma FV, UI nie | Filtr frontend / issue_date |

---

## 11. Interpretacja dla faktur 01.07.2026

1. Uruchom sync z **`force_full`** lub jawnym `date_from=2026-06-01` (jednorazowo diagnostycznie).
2. Sprawdź czy `KSEF-...-20260701-...` pojawia się w `refs_received_from_metadata`.
3. Jeśli **nie ma w metadata** → problem KSeF filtr / Subject2 / dateType (poza IFG).
4. Jeśli **jest w metadata, brak w DB** → XML / zapis / incomplete sync.
5. Jeśli **jest w DB, brak w UI** → filtr miesiąca / issue_date w UI.
