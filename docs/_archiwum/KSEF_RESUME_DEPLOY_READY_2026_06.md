# KSeF purchase sync resume — deploy ready (DS723+)

**Data:** 2026-06-22  
**Spec:** [KSEF_PURCHASE_SYNC_RESUME_FIX.md](./KSEF_PURCHASE_SYNC_RESUME_FIX.md)  
**Audyt:** [KSEF_RESUME_AUDIT_2026_06.md](./KSEF_RESUME_AUDIT_2026_06.md), [KSEF_RESUME_VERIFICATION.md](./KSEF_RESUME_VERIFICATION.md)

---

## Weryfikacja implementacji

| Element | Plik | Status |
|---------|------|--------|
| Incremental sync + resume_state | `ksef_session_service.py` | OK |
| Partial defer bez mark_success | `ksef_session_service.py` | OK |
| Publiczne API metadata/XML | `client.py` | OK |
| Resume w JobRateLimitDeferredError | `sync_purchase_invoices.py` | OK |
| Persist resume w payload | `__main__.py` | OK |
| Blokada joba per NIP | `ksef_session.py` | OK |
| Testy resume + worker defer | `test_ksef_purchase_sync_resume.py`, `test_background_job_claim.py` | OK |

**Poza tym commitem (świadomie):** UNIQUE na `ksef_reference_number`, commit per faktura, migracja Alembic.

---

## Zmienione pliki (commit)

| Plik | Zmiana |
|------|--------|
| `app/services/ksef_session_service.py` | incremental GET+save+flush, resume, partial defer |
| `app/integrations/ksef/client.py` | `query_purchase_metadata_refs`, `get_purchase_invoice_xml` |
| `app/worker/job_handlers/sync_purchase_invoices.py` | resume + partial_result w defer |
| `app/worker/__main__.py` | zapis `resume` / `partial_result` w payload |
| `app/api/routers/ksef_session.py` | blokada duplikatu enqueue per NIP |
| `tests/unit/test_ksef_purchase_sync_resume.py` | **nowy** |
| `tests/unit/test_background_job_claim.py` | test persist resume |
| `docs/KSEF_PURCHASE_SYNC_RESUME_FIX.md` | spec fixu |
| `docs/KSEF_RESUME_DEPLOY_READY_2026_06.md` | ten raport |

---

## Testy

```bash
.venv/bin/pytest tests/unit/test_ksef_purchase_sync_resume.py \
  tests/unit/test_background_job_claim.py \
  tests/unit/test_ksef_sync_service.py \
  tests/unit/test_ksef_client_retry.py -q
```

**Wynik:** `44 passed in ~7.7s`

---

## Migracja DB

**NIE** — resume w istniejącym `background_jobs.payload_json` (JSONB).

---

## Restart wymagany

**TAK** — restart / recreate kontenerów **api** i **worker** (logika sync w API enqueue + worker handler).

Frontend: **bez zmian** w tym deployu.

---

## Ryzyka pozostające

1. **Brak UNIQUE** na `invoices.ksef_reference_number` — dedup tylko aplikacyjny (`exists_by_ksef_number`).
2. **Brak commit per faktura** — trwałość faktur przy DEFERRED dopiero po `session.commit()` workera na końcu iteracji; crash przed commit kasuje postęp bieżącej iteracji.
3. **Stale recovery** (job `processing` > 30 min) — brak `payload.resume`, sync od metadata (dedup ratuje duplikaty).
4. **TOCTOU enqueue** — równoległe POST mogą utworzyć dwa joby (niskie przy normalnym UI).

---

## Deploy DS723+

Ścieżka: `/volume1/docker/ifg_v2/ifg_standalone`

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
git fetch origin production
git pull --ff-only origin production

docker compose -f docker/docker-compose.prod.yml --env-file .env.production build api worker
docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d --no-deps --force-recreate api worker
```

### Weryfikacja po deploy

```bash
curl -sf http://127.0.0.1:8000/health

docker compose -f docker/docker-compose.prod.yml --env-file .env.production logs --since 5m worker \
  | grep -E 'KSEF_ASYNC_SYNC|WORKER_JOB_DEFERRED|resume'

docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec -T db \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT id, status, payload_json->'resume'->>'current_offset' AS offset, last_error
   FROM background_jobs WHERE job_type='sync_purchase_invoices'
   ORDER BY created_at DESC LIMIT 3;"
```

### Oczekiwane zachowanie po deploy

- Przy 429: `WORKER_JOB_DEFERRED`, `payload_json.resume` z `current_offset`, część faktur zapisana po commit iteracji.
- Kolejny trigger sync dla tego NIP → ten sam `job_id` (pending/processing).
- Brak `alembic upgrade`.

---

## Rollback

```bash
git checkout <poprzedni_commit>
docker compose -f docker/docker-compose.prod.yml --env-file .env.production build api worker
docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d --no-deps --force-recreate api worker
```

Joby z `payload.resume` z nowej wersji pozostają kompatybilne wstecz (ignorowane przez starą wersję).
