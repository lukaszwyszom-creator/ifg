# GWO-IFG-KSEF-WORKER-RECOVERY-0005

**Data:** 2026-08-14  
**Tryb:** CONTROLLED PRODUCTION REPAIR  
**Host:** DS723+ `/volume1/docker/ifg_v2/ifg_standalone`

---

## STATUS

**RECOVERY_SUCCESS** (z residualnym zombie `ifg-worker-1`)

## VERDICT

1. Worker KSeF przywrócony: żywy proces `python -m app.worker`, scheduler **ACTIVE**.
2. Automatyczna sesja recovery slotu **`2026-08-14T20:00`** zakończona **SUCCESS** (1 nowa FV, 2 duplikaty, mail SENT).
3. Następny automatyczny slot: **2026-08-15 08:00** (potwierdzone runtime: `last_executed_slot=2026-08-14T20:00`, ticki co minutę).
4. Przyczyna „Up bez workera”: **zombie Docker** (Running + pusty cgroup, brak procesów) po restarcie dockerd; brak healthchecka maskował stan.
5. Minimalna poprawka wdrożona: PID1=`python -m app.worker` + healthcheck procesu `app.worker` (commit `2bcb29b`).

---

## FAZA 1 — Diagnoza (przed zmianą)

| Check | Wynik |
|-------|-------|
| `docker ps` | `ifg-worker-1` Up ~19h |
| `docker inspect` | **TIMEOUT / hang** |
| `docker logs` / `exec` | hang / puste |
| Cgroup procesów | **NO_PROCESSES_IN_CGROUP** |
| Command (compose) | `["sh","-c","python -m app.worker"]` |
| Healthcheck | **brak** |
| RestartCount | niedostępny (inspect hang); historycznie 0 przy „Up” |
| Scheduler DB | `last_attempt=2026-08-14 02:08`, `last_executed=2026-08-13T20:00` |

### WORKER_ROOT_CAUSE

**DOCKER_ZOMBIE_EMPTY_CGROUP** (po restarcie dockerd ~02:33):

- Kontener w stanie Docker `Running` / `Up`, ale **żadnych procesów** w cgroup.
- To **nie** był tylko martwy child przy żywym shellu PID1 — PID1 też nie istniał.
- Brak healthchecka ⇒ CM/Docker raportował zdrowy `Up`.
- Wrapper `sh -c` dodatkowo utrudniałby wykrycie śmierci samego Pythona w wariancie „shell żyje, python padł” — usunięty w poprawce.

---

## FAZA 2 — Controlled worker recovery

| Operacja | Wynik |
|----------|-------|
| `compose restart worker` | FAIL (timeout; zombie) |
| `docker kill` / rename zombie | FAIL (no exit event / timeout) |
| `compose force-recreate` | częściowy: utworzył `69858ab3bab4_ifg-worker-1` (Created), zombie nieusuwalny |
| `docker start` replacement | **PASS** — PID shell + `python -m app.worker` |

**NIE ruszano:** DB, API, frontend, CM, NAS, migracji, rebuild obrazu.

Po starcie (21:50:22): worker log `Worker startuje`, scheduler enqueue recovery.

---

## FAZA 3 — KSeF recovery session

Normalna ścieżka schedulera (nie ręczny sync API):

| Pole | Wartość |
|------|---------|
| Slot | `2026-08-14T20:00` (`scheduler_recovery=true`) |
| Job | `96f4c2a5-1ea3-4ad3-8481-6032c1dcf7b6` → **done** |
| START | 21:50:23 CEST (`PURCHASE_SYNC_AUTO` started) |
| END | 21:50:28 CEST (`PURCHASE_SYNC_AUTO` ok) |
| Window | **2026-08-11 → 2026-08-14**, `source=incremental`, **overlap_days=2** |
| Metadata refs | 3 |
| Nowe faktury | **1** (`5140124934-20260814-395172C00000-6B`) |
| Duplikaty / existing | **2** |
| Błędy | 0 |
| Monitor / journal | SCHEDULER_RECOVERY → ENQUEUE → SYNC ok — **widoczne w transmissions** |
| Email | **SENT** (1 nowa FV, recipients=2) — `66184682-…` |

**RECOVERY_SESSION:** SUCCESS  
**RECOVERY_NEW_INVOICES:** 1  
**RECOVERY_DUPLICATES:** 2  
**RECOVERY_EMAIL:** SENT

---

## FAZA 4 — Next run

| Dowód | Wartość |
|-------|---------|
| `last_cron` | `0 8,14,20 * * *` |
| `last_executed_slot` | `2026-08-14T20:00` |
| `last_attempt_at` (runtime) | aktualizowany co ~1 min (np. 22:21:04) |
| SKIP po recovery | `SCHEDULER_SKIP_ALREADY_EXECUTED` dla slotu 20:00 |
| Następny due slot | **2026-08-15 08:00 Europe/Warsaw** |

**NEXT_SCHEDULED_SESSION:** `2026-08-15 08:00 CEST`  
**SCHEDULER_STATUS:** ACTIVE

---

## FAZA 5 — Worker health semantics

### Poprawka (minimalna)

1. `command: ["python", "-m", "app.worker"]` — PID1 = worker.
2. Healthcheck: skan `/proc/*/cmdline` pod kątem `app.worker` → brak = **unhealthy**.

Pliki: `docker/docker-compose.prod.yml`, `docker/docker-compose.yml`

| | |
|--|--|
| Commit | **`2bcb29bf04c365d5848bdd3d2a54c220669e36d7`** |
| Push | `origin/production` |
| Deploy prod | compose zsynchronizowany na NAS; live worker odtworzony jako **`ifg-worker-active`** z healthcheck + PID1 python (**bez rebuild obrazu**) |

### Residual

- Zombie **`ifg-worker-1`** (CID `69858ab3bab4`) nadal `Up`, **pusty cgroup**, nieusuwalny bez naprawy dockerd/CM (poza zakresem bezpiecznego recovery).
- Aktywny worker: **`ifg-worker-active`** (`4439d2cc4ab4`), **healthy**, RC=0.

---

## FAZA 6 — Końcowa walidacja (22:21 CEST)

| Wymaganie | Wynik |
|-----------|-------|
| DB healthy | PASS |
| API healthy + `/health` 200 | PASS |
| Worker real process | PASS (`python -m app.worker`, Pid=9721) |
| Worker health | **healthy** |
| Scheduler ACTIVE | PASS (last_attempt świeży) |
| Frontend available | PASS (HTTP 200 :32768) |
| KSeF recovery SUCCESS | PASS |
| Next run 15.08 08:00 | PASS |
| Observe ≥10 min, RC bez wzrostu | PASS (RC=0, Up 18+ min) |

---

## RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED  
- [ ] READY_FOR_DEPLOY  
- [x] **DEPLOYED_TO_DS723**  
- [x] **PRODUCTION_VERIFIED**  

---

🩷 STATUS KOŃCOWY

✅ Co działa  
- Scheduler KSeF, recovery session, mail, API/DB/frontend, nowy worker healthy.

⚠️ Znane problemy  
- Zombie `ifg-worker-1` pozostaje w Docker (pusty); wymaga osobnego GWO dockerd/CM.  
- Nazwa kanoniczna compose `ifg-worker-1` tymczasowo zastąpiona przez `ifg-worker-active`.

❌ Co nie działa  
- Usunięcie zombie bez restartu Container Manager (świadomie nie wykonane).

### A. Root cause
Docker zombie empty-cgroup po restarcie dockerd + brak healthchecka; scheduler martwy mimo `Up`.

### B. Zmienione pliki
- `docker/docker-compose.prod.yml`
- `docker/docker-compose.yml`
- `docs/reports/2026-08-14_GWO-IFG-KSEF-WORKER-RECOVERY-0005.md`

### C. Deploy
Compose sync + recreate live worker (`ifg-worker-active`); commit `2bcb29b` na GitHub `production`. Bez rebuild API image.

### D. Testy
Procesy cgroup, health=healthy, SQL journal, `/health` 200, frontend 200, observe 10+ min RC=0.

### E. Następny krok
GWO: usunięcie zombie `ifg-worker-1` / rename na kanoniczną nazwę po naprawie dockerd; weryfikacja slotu 15.08 08:00.

## Decyzje dla ChatGPT

1. Czy akceptować residual `ifg-worker-active` + zombie `ifg-worker-1` do czasu GWO dockerd?  
2. Czy planować kontrolowany restart Container Manager poza godzinami sync?  
3. Czy dodać alert Guardian gdy `last_attempt_at` schedulera > 5 min?

## Wygenerowane raporty

- `/Users/lukasz/projekty/ifg_standalone/docs/reports/2026-08-14_GWO-IFG-KSEF-WORKER-RECOVERY-0005.md`
