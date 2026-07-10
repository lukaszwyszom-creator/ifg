# GWO-IFG-0050 — Final Production Deploy

**Data:** 2026-07-08  
**Target commit:** `f5215b0`  
**Workflow:** `ifg.deploy.run --allow-dirty-build --yes`  
**Status końcowy:** **SUCCESS**

---

## Przebieg deployu

Polecenie:

```bash
.venv/bin/python scripts/guardian.py ifg deploy run --allow-dirty-build --yes --markdown
```

Wynik: **SUCCESS** (exit code 0, duration ~336s)

Workflow ID: `2026-07-08T214533Z_ifg_deploy_run`

### Etapy przed wykonaniem

| Etap | Wynik |
|------|-------|
| `ifg.doctor` | SUCCESS (`READY_WITH_WARNINGS`) |
| `ifg.release.plan` | SUCCESS (risk MEDIUM) |
| `ifg.release.evaluate` | SUCCESS (`READY_WITH_OVERRIDE`) |
| Blockers | 0 |
| Preflight / Safety Gate | **GO** (1 warning: dirty tree override) |

### Pipeline wykonania (9/9 required)

| # | Akcja | Status | Czas |
|---|-------|--------|------|
| 1 | `git pull origin production` | EXECUTED | ~5.8s |
| 2 | `npm run build` (frontend) | EXECUTED | ~1.7s |
| 3 | artifact gate local | EXECUTED | OK |
| 4 | rsync dist → DS723+ | EXECUTED | ~1.8s |
| 5 | artifact gate remote | EXECUTED | GO |
| 6 | `docker compose build api worker` | EXECUTED | ~216s |
| 7 | alembic upgrade | SKIPPED (schema at head) | — |
| 8 | `docker compose up -d` | EXECUTED | ~64.5s |
| 9 | health check | EXECUTED | OK |
| 10 | log verification | EXECUTED | OK |

Remote HEAD po pull: `f5215b0`

---

## Wynik wszystkich etapów deployu

- **Backup policy:** spełniony przed deployem (GWO-0049, Safety Gate GO)
- **Frontend build:** PASS (lokalnie + rsync)
- **Frontend artifacts:** GO (local + remote)
- **Docker build api/worker:** PASS
- **Restart:** PASS (`ifg-api-1`, `ifg-worker-1` recreated)
- **Health (Guardian):** PASS
- **Log verification (Guardian):** PASS (brak błędów w tail)

Rollback point zapisany: commit `f5215b0`, alembic `a9b1c2d3e4f5 (head)`

---

## Wynik runtime (po deployu)

Weryfikacja na DS723+ (`ssh zdalny_admin@ds723`), ~2 min po deployu.

### 1. Health endpoint

```json
{"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production","db_timezone":"Europe/Warsaw","db_timezone_utc":false,"regon":{"environment":"production","configured":true}}
```

**PASS**

### 2. Kontenery

| Kontener | Status |
|----------|--------|
| `ifg-api-1` | Up, **healthy** |
| `ifg-db-1` | Up, **healthy** |
| `ifg-worker-1` | Up |

**PASS**

### 3. API

- `GET /openapi.json` → **HTTP 200**
- `GET /health` → **HTTP 200**

**PASS**

### 4. GET /api/v1/transmissions/

Po poprawnym logowaniu (Bearer token):

| Endpoint | HTTP | Wynik |
|----------|------|-------|
| `?page=1&size=20&warnings_or_errors_only=false` | **200** | 20 items, total 85 |
| `?page=1&size=20&warnings_or_errors_only=true` | **200** | 0 items, total 0 |

**PASS**

### 5. Monitor KSeF (warstwa API)

Monitor KSeF korzysta z endpointu transmisji — zweryfikowano:

- lista transmisji ładuje dane (200, 85 rekordów),
- filtr ostrzeżeń/błędów działa (200, pusta lista gdy brak warn/error),
- brak HTTP 500 w logach API po deployu.

**PASS** (API/runtime; weryfikacja UI w przeglądarce wymaga ręcznego potwierdzenia przez operatora)

### 6. Ponowne logowanie (nowy JWT)

- `POST /api/v1/auth/login` → **OK** (access_token otrzymany)
- Claim `sub` w JWT: **UUID** (`fe60cfaf-c61e-4c79-9a1b-390f5eea8a52`) — zgodnie z oczekiwaniem po GWO-0042

**PASS**

### 7. Brak HTTP500

- Legacy invalid JWT (`sub=admin`) → **HTTP 401** (nie 500):

```json
{"error":{"code":"unauthorized","message":"Nieprawidlowy token dostepu."}}
```

- Tail logów `api` i `worker`: brak `Traceback` / `ERROR` / `500`

**PASS** — hotfix GWO-0042 potwierdzony na produkcji

### 8. Smoke test

| Test | Wynik |
|------|-------|
| Logowanie | PASS |
| Lista faktur `GET /api/v1/invoices/?page=1&size=5` | HTTP 200, 5 items, total 106 |
| Monitor KSeF (transmissions API) | HTTP 200 |
| Health | HTTP 200 |
| Frontend `/ui/` | HTTP 200 |
| Frontend `/ui/login` | HTTP 200 |

**PASS**

---

## 🩷 STATUS KOŃCOWY

### ✅ CO DZIAŁA

- Pełny deploy produkcyjny zakończony sukcesem (commit `f5215b0`).
- Wszystkie etapy pipeline Guardiana wykonane bez błędów.
- Health, kontenery, API, transmisje, logowanie — PASS.
- Hotfix auth (401 zamiast 500 dla invalid JWT sub) potwierdzony na produkcji.

### ⚠️ ZNANE PROBLEMY

- Deploy wykonany z `--allow-dirty-build` (świadomy override dirty tree lokalnego).
- Weryfikacja UI Monitora KSeF w przeglądarce nie została wykonana automatycznie (wymaga ręcznego logout/login w UI).

### ❌ CO NIE DZIAŁA

- Brak — deploy i runtime verification zakończone pomyślnie.

---

## A. ROOT CAUSE (kontekst)

Poprzednie próby deployu blokowały Safety Gate (brak backupu) i dirty tree policy. GWO-0049 usunął blocker backupu; GWO-0050 domknął deploy z kontrolowanym override.

## B. ZMIENIONE PLIKI

- `docs/reports/2026-07-08_GWO-IFG-0050_FINAL_PRODUCTION_DEPLOY.md`

## C. DEPLOY

Wykonany — SUCCESS (`2026-07-08T214533Z_ifg_deploy_run`).

## D. TESTY

Runtime smoke na DS723+: wszystkie sprawdzenia PASS (szczegóły powyżej).

## E. NASTĘPNY KROK

Operator: wyloguj się i zaloguj ponownie w UI (odświeżenie JWT w LocalStorage), potwierdź Monitor KSeF w przeglądarce.

---

## Lista wygenerowanych raportów `.md`

1. `docs/reports/2026-07-08_GWO-IFG-0050_FINAL_PRODUCTION_DEPLOY.md`
2. `docs/guardian/IFG_DEPLOY_RUN_2026_07_08.md`
