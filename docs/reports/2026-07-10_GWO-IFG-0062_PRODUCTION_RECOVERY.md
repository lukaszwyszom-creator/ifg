# GWO-IFG-0062 — Production Recovery (diagnoza)

🩷 STATUS KOŃCOWY

✅ Co działa
- Zdiagnozowano przyczynę zatrzymania stacku IFG na DS723+.
- Potwierdzono, że to **nie była awaria runtime** ani błąd obrazu/bazy w momencie zatrzymania.
- Zebrano dowody z SSH: `docker compose ps`, `docker inspect`, logi kontenerów, stan NAS, walidacja compose.
- Przygotowano plan bezpiecznego przywrócenia środowiska (bez wykonania).

⚠️ Znane problemy
- Nie udało się jednoznacznie wskazać **konkretnego aktora** (użytkownik / Container Manager / skrypt), który wykonał stop — logi `docker events` i auth zostały utracone po restarcie NAS.
- Ostatni backup PostgreSQL na NAS pochodzi z **2026-07-08 23:02** — przed zatrzymaniem stacku.
- Guardian release nadal raportuje `PRODUCTION_BLOCKED` (to dotyczy deployu, nie samego restartu operacyjnego).

❌ Co nie działa
- Środowisko produkcyjne IFG jest **całkowicie zatrzymane** od ~25 godzin:
  - `ifg-db-1` — Exited (0)
  - `ifg-api-1` — Exited (137)
  - `ifg-worker-1` — Exited (137)
- `http://127.0.0.1:8000/health` na NAS nie odpowiada (brak listenera na porcie 8000).

---

## ETAP 1 — USTALENIE PRZYCZYNY

### Werdykt

**Kontenery zostały zatrzymane świadomie i kontrolowanie** (wzorzec `docker compose stop` / Stop w Container Manager), a nie przez crash aplikacji, błąd obrazu ani błąd bazy.

Restart NAS ~5 godzin później **utrwalił stan STOPPED**, ponieważ polityka `restart: unless-stopped` **nie wznawia kontenerów, które zostały wcześniej ręcznie zatrzymane**.

### Odrzucenie hipotez

| Hipoteza | Werdykt | Dowód |
|----------|---------|-------|
| Zatrzymanie przez Guardiana (deploy) | ❌ Odrzucona | Ostatni workflow `ifg.deploy.run` (2026-07-09 13:06 UTC) był **DRY-RUN**, `steps_executed: 0`, `PRODUCTION_BLOCKED`. Brak live `compose stop/down`. |
| Crash aplikacji / OOM | ❌ Odrzucona | `OOMKilled=false`. API: graceful shutdown (`Shutting down`, `Application shutdown complete`). Worker: normalna praca KSeF do rana. |
| Błąd obrazu | ❌ Odrzucona | Obrazy `ifg-api:latest` istnieją; kontenery działały stabilnie ~22h przed stop (health 200 OK). |
| Błąd bazy | ❌ Odrzucona | DB: `received fast shutdown request` + `checkpoint complete` + `database system is shut down` (czyste zamknięcie). Brak FATAL/PANIC przed stopem. |
| Błąd compose config | ❌ Odrzucona | `docker compose -p ifg -f docker/docker-compose.prod.yml config --quiet` → **OK**. |
| Restart NAS jako pierwotna przyczyna | ❌ Odrzucona | Stop o **22:32 CEST 2026-07-09**; NAS reboot ~**04:08 CEST 2026-07-10** (`uptime 19:40` o 23:48). |
| Efekt restartu NAS (wtórna przyczyna utrzymania downtime) | ✅ Potwierdzona | Po rebootie działają tylko kontenery, które były uruchomione (`rustmailer-bichon`, `syncthing`, `cloudflared-ifg` — wszystkie `Up 20 hours`). IFG pozostał zatrzymany. |

### Chronologia zdarzeń

| Czas (CEST) | Zdarzenie |
|-------------|-----------|
| 2026-07-08 22:34 | Start `ifg-api-1` / `ifg-worker-1` (po ostatnim deployu/rebuild) |
| 2026-07-09 08:00 | Worker: normalny job KSeF `sync_purchase_invoices` (HTTP 200, brak błędów) |
| 2026-07-09 15:06 | Guardian `ifg deploy run --dry-run` → `PRODUCTION_BLOCKED` (bez akcji na NAS) |
| 2026-07-09 22:32:26 | DB: `received fast shutdown request` |
| 2026-07-09 22:32:31 | DB: `database system is shut down` (exit 0) |
| 2026-07-09 22:32:38–39 | Worker/API: graceful shutdown → exit 137 |
| 2026-07-10 ~04:08 | Restart NAS (uptime ~19h40m przy diagnostyce 23:48) |
| 2026-07-10 23:48 | IFG nadal STOPPED; inne projekty Docker działają |

### Kolejność zatrzymania (dowód kontrolowanego stopu)

```
ifg-db-1     Finished=2026-07-09T20:32:33Z  Exit=0
ifg-worker-1 Finished=2026-07-09T20:32:38Z  Exit=137
ifg-api-1    Finished=2026-07-09T20:32:39Z  Exit=137
```

- `Exit=0` na DB = graceful shutdown (SIGTERM / `docker stop`).
- `Exit=137` na API/worker = SIGKILL po graceful shutdown (typowe przy `compose stop` z limitem czasu).
- Log API kończy się komunikatami uvicorn shutdown, nie stack trace.

---

## ETAP 2 — DIAGNOSTYKA

### Docker Compose status (NAS)

```text
NAME          STATUS                      PORTS
ifg-api-1     Exited (137) 25 hours ago   127.0.0.1:8000->8000/tcp
ifg-db-1      Exited (0) 25 hours ago     5432/tcp
ifg-worker-1  Exited (137) 25 hours ago
```

Projekt compose: `ifg` (label `com.docker.compose.project=ifg`).

`docker compose ls` pokazuje tylko `syncthing` jako running project — IFG ma wszystkie serwisy w stanie Exited, więc nie jest aktywnym projektem runtime.

### Restart policy

Wszystkie serwisy: `restart: unless-stopped`.

**Ważne:** `unless-stopped` nie restartuje kontenerów zatrzymanych ręcznie przed restartem demona Docker.

### Logi — API (`ifg-api-1`, tail)

- Ostatnie wpisy: ciągłe `GET /health HTTP/1.1 200 OK`.
- Koniec logu:
  - `Shutting down`
  - `Waiting for application shutdown.`
  - `Application shutdown complete.`
  - `Finished server process [1]`

**Brak błędów startup/runtime przed stoppem.**

### Logi — Worker (`ifg-worker-1`, tail)

- Ostatnia aktywność biznesowa: **2026-07-09 08:00** — job `sync_purchase_invoices`, zapytania KSeF HTTP 200.
- Brak traceback / FATAL przed zatrzymaniem.

### Logi — DB (`ifg-db-1`, tail)

- Normalne checkpointy co 5 min do 22:29.
- O 22:32:
  - `received fast shutdown request`
  - `aborting any active transactions`
  - `terminating connection due to administrator command`
  - `shutting down` → `checkpoint starting: shutdown immediate` → `database system is shut down`

**Brak korupcji danych w logach. Zamknięcie administracyjne.**

### Stan NAS / Docker

| Element | Wartość |
|---------|---------|
| Host | `DS723plus` |
| Uptime przy diagnozie | `19:40` (restart ~04:08 CEST 2026-07-10) |
| Docker Server | `24.0.2` |
| Live Restore | `false` |
| Kontenery running | 3 (`rustmailer-bichon`, `syncthing`, `cloudflared-ifg`) |
| Kontenery stopped | 3 (cały stack IFG) |

### Stan repo / artefaktów na NAS

| Element | Stan |
|---------|------|
| `git HEAD` | `f5215b0` — `fix(auth): map invalid JWT sub to 401 instead of HTTP 500` (2026-07-08) |
| `frontend-react/dist/index.html` | istnieje (2026-07-09 00:32) |
| `.env.production` | istnieje |
| `docker compose config` | PASS |
| Wolumen DB `docker_postgres_data` | istnieje (Created 2026-05-04) |
| Ostatni backup | `ksef_backend_20260708_230227.dump` (279331 B) |

### Ostatni workflow Guardiana

Źródło: `docs/guardian/IFG_DEPLOY_RUN_2026_07_09.md` + ponowny dry-run 2026-07-10.

| Pole | Wartość |
|------|---------|
| Workflow | `ifg.deploy.run` |
| Mode | `DRY-RUN` |
| Release decision | `PRODUCTION_BLOCKED` |
| Steps executed | `0` |
| Blockers | 6 (dirty tree, tests_must_pass, rebuild required, …) |

**Guardian nie wykonał operacji stop/restart na produkcji.**

---

## ETAP 3 — ANALIZA

### Dlaczego kontenery są zatrzymane?

**Główna przyczyna:** świadome, kontrolowane zatrzymanie stacku IFG o **22:32 CEST 2026-07-09**.

**Przyczyna utrzymania downtime:** restart NAS następnego dnia + polityka `unless-stopped` dla wcześniej zatrzymanych kontenerów.

### Klasyfikacja

| Kategoria | Ocena |
|-----------|-------|
| Oczekiwany stan operacyjny | ❌ Nie — produkcja IFG powinna działać 24/7 |
| Efekt wcześniejszych prac (Guardian GWO-0060/0061) | ❌ Nie bezpośrednio — te GWO zablokowały deploy, ale nie wykonały stopu |
| Awaria runtime | ❌ Nie |
| Błąd konfiguracji | ❌ Nie (compose config OK) |
| Błąd deployu | ❌ Nie (brak live deployu) |
| **Inna przyczyna: ręczny stop + restart NAS** | ✅ **Tak** |

### Ocena ryzyka

| Obszar | Ryzyko | Uzasadnienie |
|--------|--------|--------------|
| Integralność bazy | **LOW** | Clean shutdown DB, wolumen zewnętrzny nietknięty |
| Utrata danych przy restarcie | **LOW** | Brak sygnałów korupcji; ostatni dump z 2026-07-08 |
| Błąd konfiguracji przy starcie | **LOW** | `compose config` PASS, `.env.production` i `dist/` obecne |
| Nieznany aktor stopu | **MEDIUM** | Brak logów po reboot; wymaga potwierdzenia operatora |
| Restart bez backupu | **MEDIUM** | Zalecany świeży `pg_dump` przed `up` (polityka IFG) |
| Mylenie recovery z deployem | **HIGH** | Guardian nadal `PRODUCTION_BLOCKED`; recovery ≠ release Monitora |

---

## ETAP 4 — PLAN BEZPIECZNEGO ODTWORZENIA ŚRODOWISKA

> **Nie wykonano.** Poniżej plan operacyjny (recovery), nie plan release GWO-0060.

### Krok 0 — Potwierdzenie intencji

1. Potwierdzić u operatora, że stop o 22:32 był zamierzony lub akceptowalny.
2. Ustalić, czy celem jest **szybki restart istniejącego stacku** (bez nowego kodu), czy pełny deploy po odblokowaniu Guardiana.

### Krok 1 — Pre-flight (read-only, już częściowo wykonane)

Na NAS (`/volume1/docker/ifg_v2/ifg_standalone`):

```bash
export PATH=/var/packages/ContainerManager/target/usr/bin:$PATH
docker compose -p ifg -f docker/docker-compose.prod.yml ps -a
docker compose -p ifg -f docker/docker-compose.prod.yml config --quiet
ls -la frontend-react/dist/index.html .env.production
```

### Krok 2 — Backup DB (zalecany przed startem)

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
export PATH=/var/packages/ContainerManager/target/usr/bin:$PATH

# Start tylko DB tymczasowo
docker compose -p ifg -f docker/docker-compose.prod.yml up -d db
docker compose -p ifg -f docker/docker-compose.prod.yml exec -T db \
  pg_dump -U postgres ksef_backend > backups/pre_recovery_$(date +%Y%m%d_%H%M%S).dump

# Weryfikacja rozmiaru dumpa (>0 B)
ls -l backups/pre_recovery_*.dump | tail -1
```

**Nie używać** `docker compose down -v`.

### Krok 3 — Uruchomienie stacku (bez rebuild, bez deployu)

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
export PATH=/var/packages/ContainerManager/target/usr/bin:$PATH

# DB najpierw — poczekać na healthy
docker compose -p ifg -f docker/docker-compose.prod.yml up -d db
docker compose -p ifg -f docker/docker-compose.prod.yml ps db

# Następnie API + worker (istniejące obrazy)
docker compose -p ifg -f docker/docker-compose.prod.yml up -d api worker
```

**Celowo bez `--build`** — kontenery działały poprawnie przed stopem; rebuild należy do osobnego, świadomego deployu.

### Krok 4 — Weryfikacja po starcie

```bash
curl -sS http://127.0.0.1:8000/health
docker compose -p ifg -f docker/docker-compose.prod.yml ps
docker compose -p ifg -f docker/docker-compose.prod.yml logs --tail=50 db api worker
```

Kryteria GO:
- `/health` → HTTP 200
- `ifg-db-1` → healthy
- `ifg-api-1` → running (healthcheck OK po start_period)
- `ifg-worker-1` → running, log `Worker startuje`

### Krok 5 — Smoke minimalny (opcjonalny)

```bash
curl -sS http://127.0.0.1:8000/openapi.json | head -c 200
# opcjonalnie: python3 scripts/guardian.py (health/deploy-check)
```

### Krok 6 — Czego NIE robić w recovery

- ❌ `docker compose down -v`
- ❌ rebuild obrazów bez decyzji release
- ❌ `git pull` / rsync / deploy Guardiana przy `PRODUCTION_BLOCKED`
- ❌ restart „na ślepo” bez backupu i weryfikacji `ps`

### Rollback planu recovery

Jeśli start się nie powiedzie:

1. Zatrzymać api/worker: `docker compose -p ifg -f docker/docker-compose.prod.yml stop api worker`
2. Zachować logi: `docker compose -p ifg -f docker/docker-compose.prod.yml logs --tail=200 > logs/recovery_fail_$(date +%Y%m%d_%H%M%S).log`
3. Nie usuwać wolumenu DB
4. Przy problemach DB — restore z `ksef_backend_20260708_230227.dump` lub świeżego `pre_recovery_*.dump`

---

A. ROOT CAUSE
- Stack IFG został **ręcznie i kontrolowanie zatrzymany** 2026-07-09 o 22:32 CEST (wzorzec `compose stop`). Restart NAS ~04:08 CEST 2026-07-10 utrwalił stan STOPPED z powodu `unless-stopped`. Guardian i ostatni deploy **nie były przyczyną** — deploy był zablokowany i nie wykonany.

B. ZMIENIONE PLIKI
- `docs/reports/2026-07-10_GWO-IFG-0062_PRODUCTION_RECOVERY.md`

C. DEPLOY
- Nie wykonano (zgodnie z wymaganiem GWO-0062).

D. TESTY / DOWODY
- SSH `docker compose ps -a` na DS723+ → 3/3 IFG Exited
- `docker inspect` → Exit 0 (db), 137 (api/worker), `OOMKilled=false`
- Logi DB/API/worker → graceful/admin shutdown, brak crash
- `docker compose config --quiet` → OK
- `uptime` NAS → restart po stopie IFG
- Guardian `ifg deploy run --dry-run` → `PRODUCTION_BLOCKED`, `steps_executed: 0`

E. NASTĘPNY KROK
- Potwierdzenie operatora: czy wykonać **Krok 2–4 planu recovery** (restart bez deployu).
- Osobno: domknięcie blockerów release (GWO-0061) przed jakimkolwiek deployem nowego kodu.

## Decyzje dla ChatGPT

1. Czy wykonać **operacyjny restart** istniejącego stacku (plan ETAP 4), czy najpierw czekać na pełne odblokowanie `PRODUCTION_BLOCKED` i deploy nowego kodu?
2. Czy operator pamięta **kto/co zatrzymało** stack o 22:32 CEST 2026-07-09 (Container Manager, SSH, maintenance)?

## Wygenerowane raporty

- `docs/reports/2026-07-10_GWO-IFG-0062_PRODUCTION_RECOVERY.md`
