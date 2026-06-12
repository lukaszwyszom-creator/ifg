# Worker: pending KSeF sync jobs not claimed — fix

**Data:** 2026-05-22  
**Produkcja:** DS723+ (commit bazowy `6c30412`)  
**Zakres:** `background_jobs` / worker / KSeF purchase sync

---

## Objaw (produkcja)

1. Worker startuje poprawnie: `Worker startuje. poll_interval=5s batch=10`
2. Wcześniej sync ruszał (`KSEF_ASYNC_SYNC_WORKER_START`, metadata count=50), potem HTTP 429 przy pobieraniu XML
3. Po operacjach/deployu **nowe joby** w `background_jobs`:
   - `status = pending`
   - `locked_at = NULL`
   - `attempts = 0`
   - worker **nie podejmuje** (brak `WORKER_JOB_CLAIMED`, brak `KSEF_ASYNC_SYNC_WORKER_START`)
4. Stare joby kończyły się: „Sesja KSeF wygasła”, „Brak aktywnej sesji”

---

## Analiza kodu (przed fixem)

### Claim query (`background_job.py`)

```python
select(BackgroundJob)
.where(BackgroundJob.status == "pending")
.order_by(BackgroundJob.available_at.asc())
.limit(batch_size)
.with_for_update(skip_locked=True)
```

**Brakowało filtrów:**
| Filtr | Stan przed fixem |
|-------|------------------|
| `job_type` | brak (worker obsługuje wszystkie typy — OK) |
| `status == pending` | tak |
| `available_at <= now()` | **nie** — joby z backoff w przyszłości były brane natychmiast |
| `attempts < max_attempts` | **nie** — pending z wyczerpanymi próbami blokowały kolejkę |
| `locked_at` | nie używany w SELECT (OK dla pending) |

### Zgodność `job_type`

API (`POST /ksef-sessions/sync-purchase`) enqueue: `job_type="sync_purchase_invoices"`  
Worker handler map: `"sync_purchase_invoices"` → `SyncPurchaseInvoicesJobHandler`  
**Zgodne — to nie był root cause.**

### Worker poll (`app/worker/__main__.py`)

1. `claimable_jobs()` — tylko SELECT FOR UPDATE, **bez** natychmiastowego `status=processing` / `attempts++`
2. Dopiero potem budowa `KSeFClient`, `KSeFSessionService`, handlerów
3. Przy wyjątku **przed pętlą jobów** → `rollback()` → joby wracają do `pending`, `attempts=0` (**niewidoczne w logach poza `Błąd podczas przetwarzania batcha`**)
4. Przy pustym wyniku claim → **brak logów** (cisza mimo pending w DB)
5. Brak recovery jobów `processing` po crashu/deployu workera
6. Retry do `pending` nie czyścił `locked_at` / `locked_by`

---

## Root cause

**Kombinacja trzech problemów:**

1. **Brak widoczności diagnostycznej** — gdy `pending_count > 0` ale `claimable_count == 0` (joby z `available_at` w przyszłości, wyczerpane `attempts`, lub zawieszone `processing`), worker logował tylko start i spał dalej co 5 s.

2. **Niekompletny filtr claim** — brak `attempts < max_attempts` i `available_at <= now()` powodował, że kolejka mogła zawierać „martwe” pending (wyczerpane próby) lub joby niegotowe do uruchomienia; worker nie miał mechanizmu ich normalizacji.

3. **Kolejność claim vs init** — SELECT FOR UPDATE + rollback przy błędzie inicjalizacji KSeF **przed** inkrementacją `attempts` sprawiał w DB wrażenie, że worker „nie dotyka” jobów (`attempts=0`, `locked_at=NULL`), mimo że co 5 s próbował batch.

Dodatkowo: joby **`processing` po killu workera** (deploy, restart) nie wracały do `pending`, co zaniżało `claimable_count` względem oczekiwań operatora.

---

## Wdrożony fix (bez migracji DB)

### `app/persistence/models/background_job.py`

- Filtr claim: `pending` + `attempts < max_attempts` + (`available_at IS NULL OR available_at <= now()`)
- `prepare_job_queue()` — przed poll:
  - `release_stale_processing_jobs()` (>30 min w `processing`)
  - `fail_exhausted_pending_jobs()` — pending z `attempts >= max_attempts` → `failed`
- `claim_and_lock_jobs()` — atomowy claim: `processing`, `locked_at`, `locked_by`, `attempts++`
- Liczniki: `count_pending_jobs`, `count_claimable_jobs`, `count_pending_blocked_reasons`

### `app/worker/__main__.py`

- Logi (tylko gdy jest co raportować):
  - `WORKER_POLL_TICK pending_count=… claimable_count=… processing=…`
  - `WORKER_JOB_CLAIMED job_id=… job_type=… attempts=…`
  - `WORKER_JOB_SKIPPED reason=…` (no_claimable_jobs / unknown_job_type / worker_init_failed)
- Claim **przed** init KSeF; przy błędzie init — jawny zapis `failed`/`pending` + commit (bez cichego rollback)
- Retry → `pending` czyści `locked_at` / `locked_by`
- Obsługa 429/retry/backoff w `KSeFClient` — **bez zmian**

---

## Test regresyjny

Plik: `tests/unit/test_background_job_claim.py`

```bash
.venv/bin/pytest tests/unit/test_background_job_claim.py -q
```

Scenariusze:
- pending `sync_purchase_invoices` → `claim_and_lock_jobs` → `processing`, `attempts=1`
- `available_at` w przyszłości → nie claimowane
- pending z wyczerpanymi próbami → normalizacja do `failed`
- stale `processing` → zwolnienie do `pending`
- `_process_batch()` z mock handlerem → job `done`, handler wywołany

---

## Weryfikacja na DS723+ (po deployu)

```bash
# 1. Backup DB (wymagany przed operacjami)
docker compose -f docker/docker-compose.prod.yml exec db \
  pg_dump -U postgres ksef_backend > backup_$(date +%Y%m%d_%H%M)_pre_worker_fix.sql

# 2. Deploy
docker compose -f docker/docker-compose.prod.yml up -d --build worker api

# 3. Logi workera
docker compose -f docker/docker-compose.prod.yml logs -f worker | grep -E \
  'WORKER_POLL_TICK|WORKER_JOB_CLAIMED|WORKER_JOB_SKIPPED|KSEF_ASYNC_SYNC'

# 4. Stan kolejki w DB
docker compose -f docker/docker-compose.prod.yml exec db psql -U postgres -d ksef_backend -c \
  "SELECT status, job_type, COUNT(*), MIN(available_at), MAX(attempts) FROM background_jobs GROUP BY 1,2 ORDER BY 1,2;"

# 5. Ręczny trigger sync z UI → oczekiwane:
#    KSEF_ASYNC_SYNC_ENQUEUE → WORKER_JOB_CLAIMED job_type=sync_purchase_invoices → KSEF_ASYNC_SYNC_WORKER_START
```

### Istniejące pending joby (bez resetu DB)

Fix **nie wymaga** migracji ani `docker compose down -v`.  
Joby `pending` z poprawnym `available_at <= now()` i `attempts < max_attempts` zostaną odebrane przy następnym ticku.  
Joby `processing` starsze niż 30 min wrócą do `pending` automatycznie.

---

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `app/persistence/models/background_job.py` | filtry claim, recovery, liczniki, `claim_and_lock_jobs` |
| `app/worker/__main__.py` | logi diagnostyczne, kolejność claim/init, cleanup locków |
| `tests/unit/test_background_job_claim.py` | test regresyjny |
| `docs/WORKER_PENDING_JOBS_NOT_CLAIMED_FIX.md` | ten raport |

---

## Komendy deploy (skrót)

```bash
cd /path/to/ifg_standalone
docker compose -f docker/docker-compose.prod.yml exec db \
  pg_dump -U postgres ksef_backend > backup_pre_worker_fix.sql
docker compose -f docker/docker-compose.prod.yml up -d --build worker
docker compose -f docker/docker-compose.prod.yml logs -f worker
```
