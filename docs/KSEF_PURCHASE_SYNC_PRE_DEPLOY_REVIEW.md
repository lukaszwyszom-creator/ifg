# KSeF purchase sync — pre-deploy review (429 / resume fix)

**Data:** 2026-07-03  
**Branch:** `production`  
**Zakres:** review implementacji bez zmian w kodzie  
**Powiązany fix:** [KSEF_PURCHASE_SYNC_429_RESUME_FIX.md](./KSEF_PURCHASE_SYNC_429_RESUME_FIX.md)

---

## 1. Retry-After przy planowaniu resume

### Ścieżka krytyczna (HTTP 429 na GET XML faktury)

Przy `defer_purchase_rate_limit=True` (wymuszane w `sync_purchase_invoices`) pierwsze 429 na `_get_purchase_invoice_xml` **nie robi sleep w pętli**, tylko:

1. `_rate_limit_sleep_seconds(response, attempt)` czyta nagłówek `Retry-After`
2. Jeśli brak/niepoprawny → fallback: exponential backoff (`_purchase_download_backoff_seconds`)
3. Wartość trafia do `KSeFRateLimitDeferredError(retry_after_seconds=...)`
4. Serwis przekazuje `retry_after_seconds` w `resume_state` / raporcie API
5. Worker: `JobRateLimitDeferredError.retry_after_seconds` → `background_jobs.available_at = now + timedelta(seconds=...)`

**Wniosek:** Dla głównego scenariusza prod (429 przy pobieraniu XML) **Retry-After jest wykorzystywany**, o ile KSeF go zwraca.

### Wyjątki i luki

| Miejsce | Zachowanie | Retry-After w resume? |
|---------|------------|------------------------|
| GET XML, defer=True | Natychmiastowy defer z `_rate_limit_sleep_seconds` | **Tak** (lub backoff) |
| Worker handler | `report.get("retry_after_seconds", 120.0)` | **Fallback 120 s** gdy brak w raporcie |
| `ExternalServiceError` ← `KSeFRateLimitDeferredError` | `cause.retry_after_seconds` | **Tak** |
| POST metadata (`_request_with_retry`) | Sleep in-process, retry w tej samej sesji HTTP | **Nie dotyczy job resume** — brak defer/resume fazy metadata |
| API inline `/sync/purchases` przy defer | Zwraca `retry_after_seconds` w JSON | **Informacyjnie** — brak automatycznego `available_at` (to robi tylko worker) |
| Brak nagłówka `Retry-After` na 429 XML | Backoff od attempt | **Nie** — użyty jest backoff, nie nagłówek |

### Ocena punktu 1

**Częściowo spełnione.** Retry-After jest poprawnie propagowany w łańcuchu **429 na XML → defer → worker.available_at**, co odpowiada produkcyjnemu problemowi (13× 429 na refach XML).

Nie jest „zawsze” w sensie absolutnym:
- metadata 429 nie ma mechanizmu resume/defer (tylko retry + sleep w procesie),
- handler ma twardy fallback **120 s**,
- brak nagłówka → backoff zamiast Retry-After.

Dla wdrożenia na DS723+ (async worker, typowo dziesiątki–setki refs) **ryzyko operacyjne niskie**. Dla pełnej zgodności „zawsze Retry-After” wymagany byłby follow-up: defer + resume także dla paginacji metadata oraz usunięcie fallbacku 120 s na rzecz wyłącznie wartości z KSeF/backoffu z logiem.

---

## 2. Lock synchronizacji — thread vs współdzielony

Implementacja **nie opiera się wyłącznie na thread lock**. Są **trzy warstwy**, o różnym zasięgu:

### Warstwa A — `BackgroundJob` (DB, współdzielona między procesami)

```python
find_active_purchase_sync_background_job(nip, exclude_job_id=...)
```

- Zapytanie SQL: `job_type=sync_purchase_invoices`, `status IN (pending, processing)`, `payload_json.nip`
- Przy trwającym jobie worker → `ConflictError` (HTTP **409**)
- Enqueue `POST /sync-purchase`: zwraca istniejący `job_id` zamiast tworzyć duplikat

**Zasięg:** API ↔ worker (gdy istnieje rekord joba).

### Warstwa B — `threading.Lock` per NIP (in-memory, jeden proces)

```python
_purchase_sync_nip_locks[nip].acquire(blocking=False)
```

- Blokuje równoległe wywołania **w tym samym procesie Pythona**
- Na DS723+: API = **1 proces uvicorn** (domyślnie, bez `--workers`), worker = **osobny kontener/proces**

**Zasięg:** wyłącznie w obrębie jednego procesu.

### Warstwa C — brak

- **Brak** PostgreSQL advisory lock
- **Brak** rekordu „sync lease” w DB dla inline API
- `ksef_sync_states.mark_running()` to **status audytowy**, nie mutex

### Macierz scenariuszy równoległości

| Scenariusz | Blokada? |
|------------|----------|
| Dwa joby async (ten sam NIP) | **Tak** — enqueue + `find_active_*` |
| Worker processing + API `/sync/purchases` | **Tak** — `find_active_*` widzi job |
| Dwa równoległe `/sync/purchases` w jednym procesie API | **Tak** — thread lock |
| **`/sync/purchases` inline + worker job (worker startuje bez wcześniejszego joba w DB)** | **NIE w pełni** — inline nie tworzy `BackgroundJob`; locki są w różnych procesach |
| API (1 worker uvicorn) + worker container równolegle przy samym inline sync | **Luka** — procesy nie dzielą `threading.Lock` |

### Ocena punktu 2

**Częściowo spełnione.** Mechanizm współdzielony (DB/`BackgroundJob`) istnieje i działa dla **domyślnej ścieżki UI (async enqueue)** oraz gdy worker już ma job w stanie pending/processing.

**Luka cross-process:** synchroniczne `POST /sync/purchases` nie rejestruje się w `background_jobs`, więc **nie blokuje** równoległego workera w drugim kontenerze (i odwrotnie: worker nie blokuje inline, dopóki job nie istnieje w DB).

Na DS723+ (1× API, 1× worker) operacyjnie: **używać async `/sync-purchase`**, unikać równoległego curl na `/sync/purchases` podczas joba.

---

## 3. Usunięcie `bulk_metadata` — wpływ na wydajność

### Co faktycznie usunięto

Usunięto ścieżkę serwisową wywołującą `query_received_invoices` → `_download_metadata_purchase_invoices` (batch download w kliencie **bez resume przy 429**). Kod klienta bulk nadal istnieje, ale **purchase sync go nie używa**.

### Obecna ścieżka (incremental)

1. Metadata **raz** — `query_purchase_metadata_refs` (paginacja, jak wcześniej)
2. Pętla per ref: `exists_by_ksef_number` → opcjonalnie GET XML → parse → `add` → **`session.flush()`**

### Porównanie przy dużej skali (5 000–15 000 faktur)

| Aspekt | Stary bulk | Nowy incremental |
|--------|------------|------------------|
| Liczba GET XML do KSeF | ~N (sekwencyjnie) | ~N minus `skipped_existing` |
| Równoległość GET | Brak | Brak |
| Pace KSeF | ~1,2 s min między requestami | To samo |
| Pamięć | Wysoka (XML w RAM do końca batcha) | Niska (1 faktura na raz) |
| DB | Zapis po batchu | **N×** (`exists` + `flush`) |
| 429 | Kontynuacja bez resume → utrata postępu | Defer + resume → **dłuższy wall-clock, ale domknięcie syncu** |
| Szacunek czasu samych GET (1,2 s/ref) | 5k ≈ 1,7 h; 15k ≈ 5 h | Podobnie (+ narzut DB) |

**Wniosek:** Usunięcie bulk **nie usuwa wąskiego gardła KSeF** (sekwencja + rate limit). Główna różnica to **narzut DB** (N zapytań `exists` + N flush) i **poprawność przy 429** (korzyść incremental).

Dla skali IFG (dziesiątki–setki refs na okno, prod: 29 refs) **wpływ pomijalny**.

Przy **kilku–kilkunastu tysiącach** nowych faktur w jednym oknie:
- sync będzie **wolny**, ale **wykonalny** przez resume (wielokrotne joby),
- ryzyko: długi czas, obciążenie DB, brak batch flush.

### Propozycja architektury `bulk + bulk_resume` (follow-up, nie bloker deploy)

Zamiast trwałego przywracania starego bulk bez resume:

```
┌─────────────────────────────────────────────────────────┐
│  Faza 1: metadata (jak dziś) + resume metadata_offset   │
├─────────────────────────────────────────────────────────┤
│  Faza 2: bulk_download XML [offset..offset+BATCH)       │
│          • defer przy 429 → resume {refs, offset}       │
│          • opcjonalnie: prefetch exists (1 query IN)    │
├─────────────────────────────────────────────────────────┤
│  Faza 3: bulk_persist [offset..offset+BATCH)            │
│          • parse + add, flush co BATCH (np. 50–100)   │
│          • resume {persist_offset} niezależnie od GET    │
└─────────────────────────────────────────────────────────┘
```

**Zasady:**
- **Jedna** ścieżka wejścia (API + worker), flaga `sync_mode=incremental|bulk_resume`
- Próg przełączenia: np. `len(refs) > 500` lub `force_bulk_resume=true`
- **Zakaz** bulk bez `resume_state` — ten sam kontrakt defer co dziś
- Prefetch `list_ksef_purchase_refs_in_issue_range` / `WHERE ksef_number IN (...)` zamiast N× `exists`

To daje skalowalność bez powrotu do „połykania” 429.

---

## Podsumowanie review

| Obszar | Status | Uwagi |
|--------|--------|-------|
| Retry-After → resume (XML 429) | OK z zastrzeżeniami | Główny bug prod; fallback 120 s; metadata bez defer |
| Lock równoległości | OK z zastrzeżeniami | DB+thread; luka inline API ↔ worker cross-process |
| Wydajność bez bulk | OK dla IFG | Przy 10k+ rozważyć `bulk_resume` w kolejnej iteracji |
| Testy | 47 passed | Suite KSeF sync/resume/audit |

---

## Werdykt deploy

# DEPLOY READY

**Uzasadnienie:**

1. **Główna przyczyna prod** (429 na XML bez resume na `/sync/purchases`, utrata faktur lipcowych) jest **naprawiona** — jedna ścieżka incremental z defer i `resume_state`.
2. **Retry-After** jest propagowany w krytycznym łańcuchu XML → worker → `available_at`; to wystarcza dla scenariusza DS723+ z async workerem.
3. **Blokada równoległości** działa dla standardowej ścieżki UI (async job + DB) i dla worker+API gdy job istnieje; pozostała luka dotyczy **ręcznego inline sync równolegle z workerem** — łagodzona operacyjnie (używać `/sync-purchase`, nie uruchamiać równoległego `/sync/purchases`).
4. **Skala IFG** (dziesiątki–setki refs) nie wymaga przywracania bulk przed deployem; architektura `bulk_resume` to sensowny follow-up przy wzroście wolumenu, nie warunek wdrożenia hotfixa.

**Warunki operacyjne deployu:**

- Odtworzenie faktur lipca: **`POST /sync-purchase`** (async), nie równoległy inline curl.
- Po deploy: monitorować logi `KSEF_RATE_LIMIT_DEFER retry_after_seconds=...` i `WORKER_JOB_DEFERRED`.
- Follow-up (poza tym deployem): cross-process lock dla inline sync, defer metadata 429, opcjonalnie `bulk_resume` przy >500 refs.
