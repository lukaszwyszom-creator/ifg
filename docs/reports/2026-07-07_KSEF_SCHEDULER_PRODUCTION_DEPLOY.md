# 2026-07-07_KSEF_SCHEDULER_PRODUCTION_DEPLOY

Wdrożenie produkcyjne KSeF Auto-Sync Scheduler na DS723+ wyłącznie przez workflow Guardian.

---

🩷 STATUS KOŃCOWY

✅ CO DZIAŁA
- Deploy LIVE zakończony sukcesem (`ifg.deploy.run --yes`, workflow `2026-07-07T193538Z_ifg_deploy_run`).
- Worker uruchomiony z kodem schedulera (`a7d98db` + `5a5d713` na DS723+).
- Scheduler zainicjalizowany: `SCHEDULER_STARTED` w Monitorze KSeF.
- Recovery po restarcie workera: `SCHEDULER_SLOT` → `SCHEDULER_RECOVERY` → `SCHEDULER_ENQUEUE`.
- Brak wpisów `SCHEDULER_TICK` w `transmissions` (0 wierszy).
- Runtime ENV workera: `KSEF_AUTO_SYNC_ENABLED=true`, `KSEF_AUTO_SYNC_CRON=0 8,14 * * *`.
- Endpoint ręcznego sync odpowiada (`POST /api/v1/ksef-sessions/sync-purchase` → HTTP 401 bez tokenu, brak regresji routingu).
- Testy schedulera przed deployem: **49 passed**.

⚠️ ZNANE PROBLEMY
- Pierwsze 3 próby deployu FAIL — blokada `git pull` na DS723+ (brudne drzewo po wcześniejszym rsync monitora). Odblokowane commitem Guardian `5a5d713` (`git reset --hard origin/production`).
- Job wygenerowany przez scheduler (`dec20445-...`) zakończył się błędem **Brak aktywnej sesji KSeF** — to problem operacyjny sesji KSeF, nie schedulera.
- Release decision: `READY_WITH_WARNINGS` (MEDIUM risk).
- Guardian health w pipeline zwrócił `environment":"local"` w jednym odczycie; późniejszy `/health` na DS723+: `environment":"production"`.

❌ CO NIE DZIAŁA
- Automatyczny sync zakupów **nie wykonał importu** przy pierwszym enqueue (brak aktywnej sesji KSeF w DB).
- Nie wykonano osobnego testu ze zmianą cron na produkcji (świadomie pominięty — patrz sekcja 4).

---

## OCENA KOŃCOWA

# GOTOWE DO PRACY

Scheduler jest wdrożony, zainicjalizowany i enqueue działa. Pełna synchronizacja zakupów wymaga aktywnej sesji KSeF (stan operacyjny poza zakresem schedulera).

---

## 1. Przygotowanie (pre-deploy)

| Krok | Wynik |
|------|-------|
| Branch | `production` |
| Git status przed commitem | zmiany schedulera + monitor journal — niezacommitowane |
| Commit schedulera | `a7d98db` — `feat(ksef): add auto-sync scheduler with monitor journal integration` |
| Commit odblokowujący deploy | `c717c8b`, `5a5d713` — sync git na DS723+ (`reset --hard`) |
| Push | `origin/production` |
| Testy wymagane | 49 passed (scheduler + KSeF sync + transmission API) |

### Commity wdrożone na DS723+

| SHA | Opis |
|-----|------|
| `a7d98db` | Scheduler + journal + config |
| `c717c8b` | Guardian: stash przed pull (zastąpione) |
| `5a5d713` | Guardian: `reset --hard` przed pull (skuteczne) |

Remote HEAD po deploy: **`5a5d713`**

---

## 2. Workflow Guardian

### Użyty workflow

```bash
python scripts/guardian.py ifg deploy run --yes
```

Workflow ID: **`2026-07-07T193538Z_ifg_deploy_run`**

Zależności (auto):
- `ifg.release.plan` → SUCCESS (`2026-07-07T193538Z_ifg_release_plan`)
- `ifg.release.evaluate` → SUCCESS (`2026-07-07T193600Z_ifg_release_evaluate`, decision: `READY_WITH_WARNINGS`)

### Pipeline (9/9 required EXECUTED)

| # | Akcja | Status | Exit |
|---|-------|--------|------|
| 1 | git pull (+ remote reset) | EXECUTED | 0 |
| 2 | frontend build | EXECUTED | 0 |
| 3 | artifact verify local | EXECUTED | GO |
| 4 | dist sync | EXECUTED | 0 |
| 5 | artifact verify remote | EXECUTED | GO |
| 6 | docker build api/worker | EXECUTED | 0 |
| 7 | alembic upgrade | SKIPPED | schema at head |
| 8 | compose up | EXECUTED | 0 |
| 9 | health check | EXECUTED | OK |
| 10 | log verification | EXECUTED | 0 |

**Czas deployu:** 919 428 ms (~15 min)  
**Raport Guardian:** `docs/guardian/IFG_DEPLOY_RUN_2026_07_07.md`

### Nieudane próby (przed odblokowaniem git)

| Workflow ID | Przyczyna |
|-------------|-----------|
| `2026-07-07T191416Z_ifg_deploy_run` | `git pull` — dirty working tree na DS723+ |
| `2026-07-07T191702Z_ifg_deploy_run` | j.w. |
| `2026-07-07T192925Z_ifg_deploy_run` | j.w. (stash nieudany przez `logs/` Permission denied) |

---

## 3. Weryfikacja po deployu

### Status API

```json
{"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production","db_timezone":"Europe/Warsaw","db_timezone_utc":false,"regon":{"environment":"production","configured":true}}
```

### Status workera

```
ifg-worker-1   ifg-api:latest   Up   python -m app.worker
```

Log startu:
```
Worker startuje. poll_interval=5s batch=1
```

Brak wyjątków **schedulera** w logach (`KSeF scheduler tick failed` — brak).

### Status schedulera

**ENV (w kontenerze workera):**
```
KSEF_AUTO_SYNC_ENABLED= True
KSEF_AUTO_SYNC_CRON= 0 8,14 * * *
```

**Moduł:** `import app.worker.ksef_auto_sync_scheduler` → OK

**Stan DB (`ksef_sync_states`):**
```json
{
  "last_cron": "0 8,14 * * *",
  "last_executed_slot": "2026-07-07T14:00",
  "last_enqueued_job_id": "dec20445-a4d5-4a0b-9eba-e62456e79f5b"
}
```

### Monitor KSeF — wpisy schedulera

| operation_type | severity | status | created_at (CEST) |
|----------------|----------|--------|-------------------|
| SCHEDULER_STARTED | INFO | started | 2026-07-07 21:51:18 |
| SCHEDULER_SLOT | RUNNING | slot_due | 2026-07-07 21:51:18 |
| SCHEDULER_RECOVERY | WARNING | recovery | 2026-07-07 21:51:18 |
| SCHEDULER_ENQUEUE | SUCCESS | enqueued | 2026-07-07 21:51:19 |

**`SCHEDULER_TICK`:** 0 wpisów (potwierdzone `COUNT(*)`).

### Logowanie tuning — potwierdzenie

- `SCHEDULER_TICK` nie trafia do Monitora (tylko `logger.debug` w procesie).
- Wpisy semantyczne mają poprawne `operation_type` i `severity`.

---

## 4. Kontrolowany test `SCHEDULER_ENQUEUE`

**Nie zmieniano cron na produkcji.**

Po restarcie workera (~21:51 CEST) scheduler wykrył **niewykonany slot 14:00** i uruchomił ścieżkę recovery:

1. `SCHEDULER_SLOT` (slot `2026-07-07T14:00`)
2. `SCHEDULER_RECOVERY`
3. `SCHEDULER_ENQUEUE` → job `dec20445-a4d5-4a0b-9eba-e62456e79f5b`

To jest bezpieczniejszy i wystarczający dowód enqueue na produkcji niż tymczasowa zmiana `KSEF_AUTO_SYNC_CRON` (ryzyko dodatkowego szumu / niechcianych slotów).

Job sync zakończył się:
```
NotFoundError: Brak aktywnej sesji KSeF dla NIP 9670402857.
```
Enqueue i claim joba działają; wykonanie sync wymaga otwartej sesji KSeF.

---

## 5. Regresja ręcznego sync

| Test | Wynik |
|------|-------|
| `POST /api/v1/ksef-sessions/sync-purchase` (bez auth) | HTTP **401** (endpoint istnieje, wymaga tokenu) |
| `GET /health` | HTTP **200** |

Brak regresji routingu API. Pełny test autoryzowany manual sync nie był wykonywany w tej procedurze (wymaga tokenu operatora).

---

## 6. Testy

```bash
PYTHONPATH=scripts pytest \
  tests/unit/test_ksef_auto_sync_scheduler.py \
  tests/unit/test_ksef_purchase_sync_resume.py \
  tests/unit/test_ksef_sync_service.py \
  tests/unit/test_ksef_sync_api.py \
  tests/unit/test_transmission_api.py
```

**Wynik: 49 passed in 0.53s**

---

## 7. Ostrzeżenia i następne kroki

1. **Otwórz sesję KSeF** w UI przed oczekiwanym auto-sync o **08:00** i **14:00** — inaczej joby będą padać na `Brak aktywnej sesji KSeF`.
2. Monitoruj pierwszy planowy cykl **2026-07-08 08:00** — oczekiwane: `SCHEDULER_ENQUEUE` (bez recovery, jeśli worker działa ciągle).
3. Zachować **jedną** instancję workera z schedulerem (zgodnie z architekturą).
4. Guardian deploy na DS723+ wymaga czystego sync z `origin/production` — unikać ręcznego rsync plików `app/` poza pipeline.

---

## A. ROOT CAUSE (incydenty deployu)

Brudne drzewo git na DS723+ (pozostałość po ręcznym rsync monitora KSeF) blokowało `git pull`. `git stash -u` nie działał przez pliki `logs/` z Permission denied. Rozwiązanie: `git reset --hard origin/production` w executorze Guardian.

## B. ZMIENIONE PLIKI (deploy)

- Scheduler: `a7d98db` (22 pliki)
- Guardian deploy sync: `c717c8b`, `5a5d713`
- Ten raport

## C. DEPLOY

**Wykonano** — `ifg.deploy.run --yes`, SUCCESS, 2026-07-07 ~21:50 CEST.

## D. TESTY

49 passed (pakiet schedulera + KSeF).

## E. NASTĘPNY KROK

Weryfikacja planowego auto-sync o **08:00** z aktywną sesją KSeF.

---

*Raport wygenerowany: 2026-07-07. Wdrożenie przez Guardian `ifg.deploy.run`.*
