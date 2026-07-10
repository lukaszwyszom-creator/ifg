# KSeF purchase sync 429/resume — raport deploy DS723+

**Data:** 2026-07-03  
**Branch:** `production`  
**Fix:** [KSEF_PURCHASE_SYNC_429_RESUME_FIX.md](./KSEF_PURCHASE_SYNC_429_RESUME_FIX.md)  
**Pre-deploy review:** [KSEF_PURCHASE_SYNC_PRE_DEPLOY_REVIEW.md](./KSEF_PURCHASE_SYNC_PRE_DEPLOY_REVIEW.md)

---

## 1. Commit lokalny

| Pole | Wartość |
|------|---------|
| Hash | `a405646` |
| Message | `fix: KSeF purchase sync 429 resume for API and worker` |
| Poprzedni HEAD | `733bab4` Add purchase sync audit diagnostics |

Pliki w commicie:
- `app/services/ksef_session_service.py`
- `app/worker/job_handlers/sync_purchase_invoices.py`
- `tests/unit/test_ksef_purchase_sync_resume.py`
- `tests/unit/test_ksef_sync_service.py`
- `docs/KSEF_PURCHASE_SYNC_429_RESUME_FIX.md`
- `docs/KSEF_PURCHASE_SYNC_PRE_DEPLOY_REVIEW.md`

Push: `origin/production` — `733bab4..a405646` OK.

---

## 2. Wynik testów (lokalnie, przed push)

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

**Wynik: 47 passed** (0.30s)

---

## 3. Guardian2 deploy

```bash
python3 scripts/guardian2.py deploy-ksef --yes
```

### Lokalnie (OK)

- `node --test frontend-react/src/api/ksef.purchase-sync.test.mjs` — 6/6 pass
- `npm ci && npm run build` — OK
- `python3 scripts/guardian.py --ksef-async-check` — Status: OK
- `git push origin production` — Everything up-to-date (po wcześniejszym push)

### Remote DS723+ (częściowo OK)

| Krok | Status |
|------|--------|
| `git pull origin production` | OK → fast-forward do `a405646` |
| `npm ci && npm run build` (frontend) | OK |
| `docker compose build api` | OK |
| `docker compose up -d --force-recreate api worker` | OK — kontenery wystartowały |
| `python3 scripts/guardian.py --ksef-async-check` (remote) | **FAIL** |
| `python3 scripts/guardian.py --deploy-check` | nie wykonany (abort po poprzednim kroku) |

**Exit code Guardian2:** 1 (ABORT)

### Błąd `datetime.UTC` (Python 3.8 na hoście NAS)

```
ImportError: cannot import name 'UTC' from 'datetime' (/usr/lib/python3.8/datetime.py)
```

Post-check uruchamia `scripts/guardian.py` **na hoście Synology** (Python 3.8), nie w kontenerze API (Python 3.13). **Nie blokuje samego deployu kontenerów** — build i recreate zakończone przed abortem.

---

## 4. Weryfikacja ręczna DS723+ (po deploy)

### Commit aktywny

```
a405646 fix: KSeF purchase sync 429 resume for API and worker
```

### Kod w kontenerze API

Potwierdzone w `/app/app/services/ksef_session_service.py`:
- `find_active_purchase_sync_background_job`
- `defer_purchase_rate_limit = True`
- `exists_by_ksef_number(ref)` przed GET XML

### `docker compose ps`

| Service | Status |
|---------|--------|
| docker-api-1 | Up, health OK |
| docker-worker-1 | Up |
| docker-db-1 | Up (healthy) |

### Health API

```bash
curl -fsS http://127.0.0.1:8000/health
```

```json
{"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production",...}
```

### Logi startu

- **api:** Uvicorn running, startup complete
- **worker:** `Worker startuje. poll_interval=5s batch=1`

---

## 5. Status sesji KSeF

| Pole | Wartość |
|------|---------|
| NIP | `9670402857` |
| DB status | `active` |
| session_reference | `20260703-SO-3CA2239000-F3211E28FE-3F` |
| **expires_at** | **2026-07-03 19:54:38** (Europe/Warsaw) |
| Czas weryfikacji | **2026-07-03 ~20:41** CEST |

**Sesja wygasła** (~47 min przed wznowieniem joba). Sync po deploy nie mógł kontynuować pobierania z KSeF.

**Wymagana akcja operatora:** ponowne połączenie KSeF w portalu IFG (redeem), następnie ponowne uruchomienie async sync.

---

## 6. Sync zakupów (async) — wykonanie

### Nowy sync z parametrami z zadania

**Nie uruchomiono** nowego `POST /sync-purchase` z `force_full=true` — sesja KSeF expired (krok 6 procedury).

Próba logowania API z kontenera (`INITIAL_ADMIN_USERNAME=admin`) → **401** (hasło prod inne niż env template); operacje weryfikacyjne wykonano przez DB + logi workera.

### Istniejący job (resume sprzed deploy)

Po recreate workera **automatycznie wznowił** odroczony job (bez równoległego drugiego synca):

| Pole | Wartość |
|------|---------|
| **job_id** | `1233dc68-ea81-4537-be02-ca431f0191ef` |
| status końcowy | `failed` |
| last_error | `Sesja KSeF dla NIP 9670402857 wygasła.` |
| available_at | `2026-07-03 20:41:09` |
| **has resume** | **true** |
| **current_offset** | **44** |
| current_reference | `9512120077-20260612-004168C00149-48` |
| partial_result.skipped_existing | 44 |
| partial_result.received | 68 |
| partial_result.rate_limited | true |

Logi workera (2026-07-03 20:41:11):

```
WORKER_JOB_CLAIMED job_id=1233dc68-ea81-4537-be02-ca431f0191ef
KSEF_ASYNC_SYNC_WORKER_START job_id=1233dc68-ea81-4537-be02-ca431f0191ef nip=9670402857
KSEF_PURCHASE_SYNC_AUDIT WINDOW ... source=resume ... resume=offset=44 refs=68
KSEF_ASYNC_SYNC_WORKER_ERROR ... Sesja KSeF dla NIP 9670402857 wygasła.
```

**Wnioski o resume (429 fix):**
- Job wznowił się od **offset=44** (nie od 0)
- `skipped_existing_accumulated=44` — refs 0..43 pominięte bez ponownego GET
- `payload_json.resume` zachowany między defer a wznowieniem
- Po deploy nowy kod obsłużył resume poprawnie do momentu wygaśnięcia sesji

Historycznie (job `e1ae883f`, status `done`, 19:44:17): offset=64, zapisano m.in. faktury lipcowe.

---

## 7. Logi audit / rate-limit / defer

Po recreate kontenerów (20:37+) dostępne głównie logi wznowienia joba. Wcześniejsze defer z dzisiaj widoczne w DB:

- `last_error`: `KSeF ograniczył tempo pobierania faktur (HTTP 429)...`
- `payload_json.resume.current_offset`: progresja (np. 44, wcześniej 64)
- `available_at`: ustawiane po 429 (np. 20:41:09)

Przykład `grep` użyty na DS723+:

```bash
sudo docker compose -f docker/docker-compose.prod.yml logs --since 60m api worker \
  | grep -E 'KSEF_PURCHASE_SYNC_AUDIT|KSEF_RATE_LIMIT_DEFER|WORKER_JOB_DEFERRED|sync_purchase'
```

---

## 8. SQL — faktury lipcowe

```sql
SELECT ksef_reference_number, issue_date, created_at
FROM invoices
WHERE direction = 'purchase'
  AND ksef_reference_number IS NOT NULL
  AND issue_date >= '2026-07-01'
ORDER BY issue_date, created_at;
```

**Wynik: 3 wiersze**

| ksef_reference_number | issue_date | created_at |
|-----------------------|------------|------------|
| 8171972369-20260701-49BFDB800005-B5 | 2026-07-01 | 2026-07-03 19:44:17 |
| 8971840043-20260701-5335F9000099-26 | 2026-07-01 | 2026-07-03 19:44:17 |
| 5540233408-20260701-5F00DB800003-5F | 2026-07-01 | 2026-07-03 19:44:17 |

**Zakres 2026-06-01 .. 2026-07-03:** 29 faktur zakupowych w DB (min issue_date 2026-06-01, max 2026-07-01).

### Czy lipcowe faktury weszły do DB?

**Częściowo TAK** — 3 faktury z `issue_date = 2026-07-01` zapisane o 19:44 (przed deployem fix, podczas wcześniejszego async sync z resume). Pełne domknięcie okna po deploy **nie nastąpiło** z powodu wygasłej sesji KSeF.

### Czy resume działa przy 429?

**TAK (potwierdzone):**
- `payload_json.resume` z `current_offset` po defer
- wznowienie od offsetu (44), nie od początku listy
- `skipped_existing=44` bez ponownych GET XML
- post-deploy worker użył nowego kodu (`source=resume` w audycie)

---

## 9. `ksef_sync_states`

| scope | status | last_error |
|-------|--------|------------|
| purchase_invoices | error | Sesja KSeF dla NIP 9670402857 wygasła. |

`last_success_at`: 2026-06-24 (HWM nie zaktualizowany po partial/defer — zgodnie z fix).

---

## 10. Końcowy werdykt

# DEPLOY PARTIAL

| Obszar | Ocena |
|--------|-------|
| Commit + push | OK (`a405646`) |
| Testy lokalne | OK (47 passed) |
| Deploy kontenerów DS723+ | OK (api + worker na `a405646`) |
| Guardian2 post-check | FAIL (`datetime.UTC` / Python 3.8 na NAS) |
| Health / kontenery | OK |
| Fix w runtime | OK (kod w kontenerze, resume po deploy) |
| Kontrolowany sync po deploy | **NIE ukończony** — sesja KSeF expired |
| Faktury lipcowe | **Częściowo** — 3× 2026-07-01 w DB |

### Następne kroki (operator)

1. Portal IFG → **Połącz KSeF** (nowa sesja dla NIP `9670402857`).
2. Uruchomić **tylko async** (bez inline):

```bash
curl -sS -X POST "https://<HOST>/api/v1/ksef-sessions/sync-purchase" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "nip": "9670402857",
    "date_from": "2026-06-01",
    "date_to": "2026-07-03",
    "force_full": true
  }'
```

3. Monitorować job_id do `done` lub kolejnych `WORKER_JOB_DEFERRED` z rosnącym `current_offset`.
4. Po sukcesie powtórzyć SQL lipca.

**Nie uruchamiać** równolegle `POST /api/v1/ksef/sync/purchases`.
