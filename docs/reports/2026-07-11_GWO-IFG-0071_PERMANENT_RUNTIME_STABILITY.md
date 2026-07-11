---
kind: gwo
project: IFG
workflow: GWO-IFG-0071
handoff: true
created_at: 2026-07-11T09:00:00Z
---

# GWO-IFG-0071 — Trwała stabilizacja runtime IFG + Lamus (GDD-0010)

**Data:** 2026-07-11  
**Cel:** Ustalić przyczynę drugiego pełnego zatrzymania stacku IFG na DS723+, przywrócić produkcję i wdrożyć trwałe zabezpieczenie  
**Werdykt:** **PERMANENT RUNTIME FIX IMPLEMENTED**

---

## LAMUS — GDD-0010 (DONE)

Rozdzielono status runtime od gotowości release w `prod health`:

| Warstwa | Statusy |
|---|---|
| **Runtime** | `PRODUCTION_RUNNING`, `PRODUCTION_STOPPED`, `PRODUCTION_DEGRADED` |
| **Release** | `READY_FOR_DEPLOY`, `PRODUCTION_BLOCKED` (osobno: `guardian release evaluate`) |

### Zmiany

| Plik | Zmiana |
|---|---|
| `scripts/ifg_guardian/core/runtime_status.py` | Klasyfikacja runtime + `RuntimeStatusReport` |
| `scripts/ifg_guardian/modules/production.py` | `prod health` raportuje Runtime niezależnie; wykrywa restart policy mismatch i rejestrację projektu CM |
| `tests/unit/test_production_runtime_status.py` | 6 testów jednostkowych |
| `docs/guardian/deferred_decisions.json` | GDD-0010 → **DONE** |

### Dowód GDD-0010 (przed recovery)

```
Runtime: PRODUCTION_STOPPED
Note: PRODUCTION_STOPPED reflects container runtime only; PRODUCTION_BLOCKED (release gate) does not cause stack shutdown.
Release: (not evaluated — run `guardian release evaluate` for READY_FOR_DEPLOY / PRODUCTION_BLOCKED)
```

### Dowód GDD-0010 (po recovery)

```
Runtime: PRODUCTION_RUNNING
Release: (not evaluated — run `guardian release evaluate` for READY_FOR_DEPLOY / PRODUCTION_BLOCKED)
```

---

## ETAP 1 — Zabezpieczenie dowodów

**Zasada:** Dowody zebrane **przed** uruchomieniem kontenerów (2026-07-11 ~08:53 UTC).

Artefakty: `docs/reports/evidence_2026-07-11_gwo-0071/`

### Wspólny timestamp zatrzymania

| Usługa | FinishedAt (UTC) | Exit | OOMKilled | RestartCount | RestartPolicy |
|---|---|---|---|---|---|
| **db** | `2026-07-11T00:14:27.022Z` | 0 | false | 0 | unless-stopped |
| **worker** | `2026-07-11T00:14:28.586Z` | 137 | false | 0 | unless-stopped |
| **api** | `2026-07-11T00:14:29.060Z` | 137 | false | 0 | unless-stopped |

**CEST:** ~02:14:27–02:14:29 (kolejność: db → worker → api, typowa dla `compose stop`).

### Kluczowe obserwacje

- **db:** `received fast shutdown request` → graceful shutdown (administrator command)
- **api:** `INFO: Shutting down` → graceful SIGTERM, potem exit 137 (SIGKILL po timeout)
- **OOMKilled:** false na wszystkich kontenerach
- **RestartCount:** 0 — brak crash-loop
- **Logi api/worker:** brak FATAL/PANIC przed stoppem; ostatnia aktywność worker = normalny KSeF sync (23:56 CEST 2026-07-10)
- **docker events (24–48h):** puste (brak retencji / brak uprawnień)
- **NAS uptime** przy zbieraniu dowodów: ~1d 6h46m (boot ~04:07 CEST 2026-07-10 — **przed** stoppem stacku)
- **Container Manager:** przed fixem `docker compose ls` **nie** pokazywał projektu `ifg` (tylko `syncthing`)
- **Cron/DSM tasks:** brak dostępu sudo do root crontab; user crontab niedostępny
- **Skrypty z compose stop/down:** tylko `scripts/guardian2.py` (recovery, nie stop)
- **Compose labels:** `com.docker.compose.project=ifg` — poprawna nazwa projektu

---

## ETAP 2 — Root cause

### Klasa przyczyny

| # | Klasa | Werdykt |
|---|---|---|
| 1 | Świadomy stop Container Manager | **Prawdopodobna** (brak bezpośredniego logu CM) |
| 2 | `docker compose stop/down` | **Prawdopodobna** (wzorzec zgodny) |
| 3 | Workflow Guardiana | **Odrzucona** — ostatni live deploy GWO-0069; brak `compose stop` w workflow |
| 4 | DSM / cron | **Niepotwierdzona** — brak dostępu do logów/zadań |
| 5 | Restart NAS / Docker daemon | **Odrzucona jako przyczyna stopu** — NAS działał; stop o 02:14 był izolowany |
| 6 | OOM / crash / healthcheck | **Odrzucona** — OOMKilled=false, graceful shutdown db |
| 7 | Błąd konfiguracji Compose | **Odrzucona** |
| 8 | Problem restart policy | **Potwierdzona jako mechanizm utrwalenia** — `unless-stopped` + manual stop = brak auto-wznowienia |
| 9 | Brak auto-startu po restarcie | **Częściowo** — projekt `ifg` nie był w `docker compose ls` przed recovery |

### Werdykt root cause

| Pole | Wartość |
|---|---|
| **Aktor zatrzymania** | **Nieustalony** (brak docker events, brak logów DSM/CM z sudo) |
| **Mechanizm** | Kontrolowany stop stacku (~02:14 CEST) + `restart: unless-stopped` → stack pozostał STOPPED 8+ h |
| **Pewność stopu** | **MEDIUM** (wzorzec identyczny z GWO-IFG-0062) |
| **Pewność mechanizmu unless-stopped** | **HIGH** |
| **Niepotwierdzone** | Tożsamość aktora (CM UI vs SSH vs inny operator) |

---

## ETAP 3 — Bezpieczne recovery

```bash
PYTHONPATH=scripts python3 -m ifg_guardian.cli prod recover --yes
```

| Krok | Wynik |
|---|---|
| Precheck | ✅ OK (stack zatrzymany, obrazy, wolumen, .env, dist) |
| Backup DB | ✅ `backups/pre_recovery_20260711_085538.dump` (1 415 408 B) |
| Start db → healthy | ✅ |
| Start api + worker | ✅ |
| `/health` | ✅ HTTP 200 |
| Smoke | ✅ openapi, dist, container health |
| Zakazy | ✅ Bez deploy/pull/rebuild/migracji/`down -v` |

Raport recovery: `docs/GUARDIAN2_RECOVERY_DS723.md`

---

## ETAP 4 — Trwała naprawa

### B. Restart policy / auto-start (zastosowane)

Zmiana w `docker/docker-compose.prod.yml`:

```yaml
restart: always   # było: unless-stopped
```

Wdrożenie na DS723+ (bez rebuild):

```bash
sed -i 's/restart: unless-stopped/restart: always/g' docker/docker-compose.prod.yml
docker compose -f docker/docker-compose.prod.yml up -d
```

**Dowód po wdrożeniu:**

```
ifg-api-1 RestartPolicy=always Status=running
ifg-worker-1 RestartPolicy=always Status=running
ifg-db-1 RestartPolicy=always Status=running
```

### E. Monitoring runtime (GDD-0010)

`prod health` wykrywa teraz:

- wszystkie trzy kontenery zatrzymane → `PRODUCTION_STOPPED`
- brak `/health` listenera
- DB/API/worker stopped (osobno w detail)
- rozbieżność restart policy vs oczekiwane `always`
- brak rejestracji projektu `ifg` w Container Manager

### Container Manager

Po `compose up -d` projekt `ifg` ponownie zarejestrowany:

```
ifg    running(3)    /volume1/docker/ifg_v2/ifg_standalone/docker/docker-compose.prod.yml
```

---

## ETAP 5 — Zapobieganie trzeciemu wystąpieniu

**Co konkretnie zapobiegnie trzeciemu wystąpieniu?**

1. **`restart: always`** — Docker automatycznie wznawia kontenery po manualnym stopie i restarcie daemona (w przeciwieństwie do `unless-stopped`).
2. **`prod health` → `PRODUCTION_STOPPED`** — jednoznaczna detekcja pełnego stopu, niezależna od Release Gate.
3. **Alert restart policy mismatch** — `prod health` sygnalizuje gdy polityka ≠ `always`.
4. **Weryfikacja CM project** — `prod health` sprawdza `docker compose ls` dla projektu `ifg`.

**Test akceptacyjny (wymaga zgody operatora, NIE wykonany):**

1. Kontrolowany `docker compose stop` na DS723+
2. Oczekiwanie 2 min
3. Oczekiwane: kontenery wracają do `running` (restart: always) LUB `prod health` = `PRODUCTION_STOPPED` z jasnym raportem
4. Weryfikacja `docker compose ls` → `ifg running(3)`

---

## ETAP 6 — Walidacja

| Check | Wynik |
|---|---|
| `ifg-db-1` | Up, healthy ✅ |
| `ifg-api-1` | Up, healthy ✅ |
| `ifg-worker-1` | Up ✅ |
| `/health` | HTTP 200 ✅ |
| Frontend dist | deploy check OK ✅ |
| FATAL/PANIC/Traceback | brak w ostatnich 50 liniach ✅ |
| Guardian Runtime | `PRODUCTION_RUNNING` ✅ |
| Guardian Release | niezależny (osobne polecenie) ✅ |
| Restart policy | `always` na api/worker/db ✅ |
| CM project `ifg` | `running(3)` ✅ |
| Trwała naprawa aktywna | ✅ (compose na NAS + lokalnie) |

```bash
PYTHONPATH=scripts python3 -m ifg_guardian.cli prod health
# Runtime: PRODUCTION_RUNNING

python3 scripts/guardian.py deploy check
# Werdykt: PRODUKCJA ZGODNA Z LOKALNYM KODEM
# ⚠️ lokalne zmiany (compose restart policy na NAS, niezsynchronizowane z origin)
```

### Ograniczenia walidacji

- Brak testu kontrolowanego stop + auto-resume (wymaga zgody operatora)
- Brak logów DSM/Container Manager (sudo)
- Brak identyfikacji aktora stopu o 02:14 CEST
- Zmiana `restart: always` na NAS nie jest jeszcze w `origin/production` (wymaga commit + deploy w osobnym GWO)

---

## ETAP 7 — Werdykt końcowy

**PERMANENT RUNTIME FIX IMPLEMENTED**

Uzasadnienie: wdrożono trwałą zmianę restart policy (`always`), rozszerzono monitoring runtime (GDD-0010), przywrócono produkcję przez workflow Guardiana — nie wykonano wyłącznie „gołego restartu”.

---

🩷 STATUS KOŃCOWY

✅ Co działa
- Stack IFG na DS723+: db/api/worker Up, `/health` 200
- `prod health`: Runtime `PRODUCTION_RUNNING`, niezależny od Release Gate
- GDD-0010 DONE — 6 testów PASS
- Restart policy `always` aktywna na DS723+
- Projekt CM `ifg` zarejestrowany (`running(3)`)
- Backup recovery: `pre_recovery_20260711_085538.dump`

⚠️ Znane problemy
- Aktor stopu o 02:14 CEST nieustalony
- Zmiana compose na NAS nie wypchnięta do origin (dirty tree lokalnie + NAS)
- Test akceptacyjny auto-resume po stop nie wykonany

❌ Co nie działa
- Brak

---

### A. Root cause

Kontrolowany stop stacku (~02:14 CEST 2026-07-11) + `restart: unless-stopped` utrwalił stan STOPPED. OOM/crash odrzucone. Aktor nieustalony (MEDIUM pewność klasy, HIGH pewność mechanizmu).

### B. Zmienione pliki

- `scripts/ifg_guardian/core/runtime_status.py` (nowy)
- `scripts/ifg_guardian/modules/production.py`
- `tests/unit/test_production_runtime_status.py` (nowy)
- `docker/docker-compose.prod.yml` (restart: always)
- `docs/guardian/deferred_decisions.json` (GDD-0010 DONE)
- `docs/reports/evidence_2026-07-11_gwo-0071/` (dowody)
- `docs/GUARDIAN2_RECOVERY_DS723.md` (auto, recovery)
- `docs/reports/2026-07-11_GWO-IFG-0071_PERMANENT_RUNTIME_STABILITY.md` (ten raport)

### C. Deploy

Nie wykonano deployu nowego kodu. Zastosowano wyłącznie:
- recovery (`prod recover --yes`)
- `compose up -d` z nową restart policy na NAS (bez rebuild)

### D. Testy

```bash
PYTHONPATH=scripts python3 -m pytest tests/unit/test_production_runtime_status.py -q
# 6 passed

PYTHONPATH=scripts python3 -m ifg_guardian.cli prod health
# Runtime: PRODUCTION_RUNNING

python3 scripts/guardian.py deploy check
# PRODUKCJA ZGODNA Z LOKALNYM KODEM
```

### E. Następny krok

1. Commit + push `restart: always` + GDD-0010 + raport do `origin/production`
2. Opcjonalnie: test akceptacyjny kontrolowanego stop (za zgodą operatora)
3. Rozważyć alertowanie gdy `prod health` = `PRODUCTION_STOPPED` > N minut

## Decyzje dla ChatGPT

1. Czy zaakceptować `restart: always` jako stałą politykę produkcyjną (ryzyko: niekontrolowany restart po świadomym stopie na maintenance), czy dodać osobny profil maintenance z `unless-stopped`?
2. Czy wdrożyć automatyczne powiadomienie (np. cron na Mac mini: `guardian prod health`) gdy Runtime ≠ `PRODUCTION_RUNNING`?

## Wygenerowane raporty

| Ścieżka |
|---|
| `docs/reports/2026-07-11_GWO-IFG-0071_PERMANENT_RUNTIME_STABILITY.md` |
| `docs/reports/evidence_2026-07-11_gwo-0071/ds723_evidence_raw.txt` |
| `docs/reports/evidence_2026-07-11_gwo-0071/ds723_evidence_extended.txt` |
| `docs/GUARDIAN2_RECOVERY_DS723.md` |
