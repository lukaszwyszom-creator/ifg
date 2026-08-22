# GWO-IFG-INCIDENT-DB-SIGKILL-0002

**Data forensyki:** 2026-08-14 07:27–07:34 CEST  
**Tryb:** READ-ONLY (bez restartów, bez zmian konfiguracji, bez deployu, bez migracji)  
**Host:** DS723plus  
**Runtime:** `/volume1/docker/ifg_v2/ifg_standalone`  
**Kontener:** `ifg-db-1` (`f6c12971584b…`)

---

## STATUS

**FORENSIC_COMPLETE / INCIDENT_STILL_ACTIVE**

`ifg-db-1` nadal `restarting` (Exit **137**).  
**Nie stwierdzono OOM** jako przyczyny SIGKILL na podstawie dostępnych liczników cgroup / flag Docker.

## VERDICT

1. **Pierwsze zdarzenie awaryjne tej nocy:** `2026-08-14 02:08:11.992 CEST` — PostgreSQL dostał **SIGINT** (Docker `StopSignal=SIGINT`) i zalogował `received fast shutdown request`.
2. To **nie** jest samoczynny crash Postgres (brak `PANIC`, brak I/O error, brak „Out of memory” w logach PG).
3. **ExitCode 137** = zabicie procesu sygnałem **SIGKILL** (128+9), typowo jako **drugi etap** `docker stop` po timeoutcie albo kill przy restarcie kontenera/daemon — **nie** jako udowodniony host/cgroup OOM.
4. `OOMKilled=false`, `memory.failcnt=0`, brak limitu pamięci cgroup → **nie klasyfikować jako OOM_OR_RESOURCE_KILL**.
5. O ~**02:33** restartował się **dockerd** (proces start `Fri Aug 14 02:33:06`) — wtedy padły też inne kontenery i wstały ~02:34; **DB nie wróciła do READY**.
6. Snapshot share **Firmowe** o **02:05:01** jest **silnie skorelowany czasowo**, ale **nie udowodniono**, że to on wydał `docker stop` (IFG/PG leży poza share Firmowe).

## ROOT_CAUSE

**D. EXTERNAL_DOCKER_KILL**

(mechanizm SIGKILL: Docker stop/restart → `SIGINT` → incomplete shutdown → `SIGKILL` → Exit 137)

**Współczynniki / korelacja (nie pierwotny dowód sprawcy):**

- **E. DSM_TASK_OR_MAINTENANCE** — Task Scheduler id=10 `Share [Firmowe] Snapshot` daily **02:05**; artefakt `/volume1/@sharesnap/Firmowe/GMT+02-2026.08.14-02.05.01`
- **F. DOCKER_DAEMON_RESTART** — dockerd/containerd start **02:33:06–07**; `@docker` mtime **02:33:13**; masowy restart kontenerów ~02:33–02:34

**Wykluczone / niepotwierdzone:**

| Kod | Werdykt |
|-----|---------|
| B. HOST_OOM | **NO** (brak failcnt; brak czytelnego kern OOM; `OOMKilled=false`) — kern.log niedostępny dla usera → nie da się wykluczyć w 100%, ale **brak pozytywnego dowodu** |
| C. CGROUP_MEMORY_LIMIT | **NO** (`failcnt=0`, limit ≈ unlimited) |
| A. DB_PROCESS_FAILURE | **NO** (brak PANIC/self-crash) |
| G. HOST_REBOOT_OR_POWER_EVENT | **NO** (uptime **35 days**) |
| H. STORAGE_IO_FAILURE | **NO** w logach PG (`IO_ERROR_COUNT=0`, dysk volume1 36% free) |

## CONFIDENCE

| Twierdzenie | Confidence |
|-------------|------------|
| Mechanizm Exit 137 = Docker SIGKILL po stop/SIGINT, nie OOM | **90%** |
| Pierwszy failure timestamp = 02:08:11.992 CEST | **99%** |
| Firmowe Snapshot 02:05 jest bezpośrednim sprawcą `docker stop` | **45%** (korelacja; brak events/logu CM) |
| Dockerd restart 02:33 pogłębił outage | **95%** |

---

## ETAP 1 — Historia `ifg-db-1`

| Pole | Wartość |
|------|---------|
| RestartCount | **26** |
| State.Status | `restarting` |
| State.ExitCode | **137** |
| State.OOMKilled | **false** |
| State.Error | *(pusty)* |
| State.StartedAt (ostatnia próba) | `2026-08-14T00:31:13.572Z` (= **02:31:13 CEST**) |
| State.FinishedAt | `2026-08-14T00:31:25.187Z` (= **02:31:25 CEST**, ~12 s życia) |
| restart policy | `always` / MaxRetry=0 |
| healthcheck | `pg_isready -U postgres -d ksef_backend` (10s/5s/5) → **unhealthy** |
| image | `postgres:17` |
| Entrypoint/Cmd | `docker-entrypoint.sh` / `postgres` |
| StopSignal | **`SIGINT`** (Postgres = fast shutdown) |
| Memory / Reservation / Swap limit | **0 / 0 / 0** (brak limitów Docker) |
| ShmSize | 64 MiB |

### Docker events (01:45–03:00 CEST)

```text
docker events --since 2026-08-13T23:45:00 --until 2026-08-14T01:00:00
→ 0 linii
```

**Synology Container Manager nie zachował historii events** dla tego okna. Sekwencja kill/die/start **nie** jest dostępna z `docker events`. Wnioskowanie oparte na inspect + logach PG + uptime procesów.

---

## ETAP 2 — Czy to był OOM?

| Flaga | Werdykt | Dowód |
|-------|---------|-------|
| **HOST_OOM** | **NO** *(z zastrzeżeniem: `/var/log/kern.log` Permission denied)* | `uptime` 35d; host cgroup `memory.failcnt=0`; brak OOM w dostępnym `dmesg` (wymaga sudo) |
| **CGROUP_OOM** | **NO** | DB cgroup: `memory.failcnt=0`, `memsw.failcnt=0`, `under_oom 0`, `limit_in_bytes` ≈ unlimited (`9223372036854771712`) |
| **DOCKER_OOMKILLED** | **NO** | `State.OOMKilled=false` |

**Wniosek obowiązkowy GWO:** Exit 137 + OOMKilled=false **bez** failcnt/kern OOM **≠** klasyfikacja OOM.

Aktualne zużycie hosta (pomiar diagnostyczny): RAM 1.9 GiB, ~1.0 GiB swap used — presja pamięci **środowiskowa** istnieje, ale **nie jest dowodem** zabicia DB przez OOM killer.

---

## ETAP 3 — Zdarzenie ~02:08 (±20 min)

### Potwierdzone

| Czas CEST | Zdarzenie | Dowód |
|-----------|-----------|-------|
| **02:05:01** | Utworzono snapshot **Share [Firmowe]** | Dir `/volume1/@sharesnap/Firmowe/GMT+02-2026.08.14-02.05.01`; task id=10 `run hour=2 run min=5` |
| **02:04:46** | PG checkpoint time — DB zdrowa | log PG |
| **02:08:11.992** | PG: `received fast shutdown request` | log PG |
| **02:08:12–18** | terminating backends / `checkpoint starting: shutdown immediate` | log PG |
| **02:15–02:31** | Wielokrotne próby startu PG; **0×** `ready to accept` po 02:08 | log PG; `READY_AFTER_0208=0` |
| **02:33:06** | **dockerd** start | `ps` LSTART |
| **02:33:07** | containerd start | `ps` LSTART |
| **02:33:13** | `/volume1/@docker` mtime | `stat` |
| **02:33–02:34** | Restart większości kontenerów | inspect Started/Finished |

### Task Scheduler (correlation)

| id | Czas | Nazwa | Stan |
|----|------|-------|------|
| **10** | **02:05 daily** | Share [Firmowe] Snapshot | enabled — **trafienie w okno** |
| 11 | 02:30 daily | Share [Foto] Snapshot | enabled |
| 9 | 00:00 / co 6h | Share [Dane] Snapshot | enabled |
| 5/6 | 00:00 | ActiveBackup retention/notify | enabled |
| 7 | 03:17 | ActiveBackup ResourceRecycler | enabled |
| 1 | 03:55 | DSM Auto Update | enabled |

**Uwaga ścieżek:** IFG/Postgres (`/volume1/docker/…`, volume `docker_postgres_data` w `/volume1/@docker`) **nie leży na share Firmowe**. Snapshot Firmowe **nie** jest snapshotem katalogu danych PG. Korelacja może wynikać z obciążenia tego samego Btrfs `/volume1` albo z innego, nieudokumentowanego triggera Container Manager.

### Inne

- Hyper Backup: brak osobnego tasku poza ActiveBackup retention o 00:00 (wcześniej niż 02:08).
- Host reboot / UPS: **brak**.
- Guardian/deploy: brak dowodu uruchomienia tej nocy.
- USB backup share: **100% full** (`/volumeUSB1/usbshare`) — stresor środowiskowy, bez bezpośredniego dowodu na kill DB.
- Docker events / CM daemon logs / `/var/log/messages`: **niedostępne** (events puste; messages Permission denied).

### Historyczny wzorzec (ważne)

W logach PG widać wcześniejsze `fast shutdown request` (m.in. 2026-07-29, 08-04×2, **08-12 01:41**, **08-14 02:08**). To sugeruje **powtarzalne zewnętrzne stopowanie** kontenera DB, nie jednorazowy bug Postgres.

---

## ETAP 4 — Czy zginęła tylko DB?

| Kontener | FinishedAt (UTC) | StartedAt (UTC) | Interpretacja |
|----------|------------------|-----------------|---------------|
| ifg-db-1 | 00:31:25 | 00:31:13 (loop) | w pętli **przed** i **po** restarcie dockerd |
| ifg-api-1 | cyklicznie | cyklicznie | restart loop wtórny (brak DB) |
| ifg-worker-1 | 00:33:38 | 00:34:52 | padł z daemonem, wstał |
| ifg-frontend-1 | 00:33:32 | 00:34:46 | j.w. |
| cloudflared-ifg | 00:33:27 | 00:34:39 | j.w. |
| syncthing-1 | 00:33:32 | 00:34:52 | j.w. |
| rustmailer-bichon-1 | 00:33:27 | 00:34:52 | j.w. |

**Wniosek:**

- O **02:08** — na podstawie logów PG — **celowane/stopujące zdarzenie obejmowało co najmniej DB** (SIGINT→fast shutdown). Brak events nie pozwala dowieść stop całego projektu w tej samej sekundzie.
- O **02:33** — **tak, wiele kontenerów jednocześnie** + **restart Docker daemon** (nie host reboot).

---

## ETAP 5 — PostgreSQL logs

### Przed SIGKILL / stop

- Do 02:04:46: normalne checkpointy — **zdrowy**.
- 02:08:11: `received fast shutdown request` ← **SIGINT / docker stop**, nie crash wewnętrzny.
- `FATAL: terminating connection due to administrator command` ← standardowy tekst PG przy fast shutdown (niekoniecznie człowiek-admin).
- Brak: `PANIC`, corruption, disk full, permission, shared memory OOM.

### Po

- Starty o 02:15, 02:24, … bez `database system is ready to accept connections` po 02:08.
- `database system was interrupted; last known up at 2026-08-14 02:24:41` — dowód **twardego przerwania** mid-start/recovery.
- `PANIC_COUNT=0`, `IO_ERROR_COUNT=0`, `READY_AFTER_0208=0`.

**Rozstrzygnięcie:** PostgreSQL **został zabity/zatrzymany z zewnątrz** (Docker), **nie** „sam się wysypał”.

---

## ETAP 6 — Storage

| Check | Wynik |
|-------|-------|
| Free space `/volume1` | 96G, **36%** used — OK |
| Volume `docker_postgres_data` | istnieje (external) |
| Btrfs | volume1 = btrfs; brak dostępnych logów I/O error dla usera |
| PG data dir | „Skipping initialization” przy restartach → katalog danych **obecny** |
| fsck/repair | **NIE wykonywano** (zakaz) |

---

## ETAP 7 — Causal chain (tylko elementy z dowodem)

```
[E korelacja] 02:05:01  DSM Task #10 tworzy snapshot Firmowe
        (brak dowodu, że to wywołuje docker stop)

[D DOWÓD]     02:08:11  Docker wysyła StopSignal=SIGINT do ifg-db-1
                → PG: "received fast shutdown request"
                → backends: "administrator command"

[D DOWÓD]     ~02:08:2x  Shutdown nie dokończony w logu
                → kontener kończy Exit 137 (SIGKILL)
                → OOMKilled=false, cgroup failcnt=0

[D/policy]    restart: always próbuje podnieść DB (02:15–02:31)
                → kolejne starty przerywane (interrupted / Exit 137)
                → READY nigdy nie osiągnięty

[F DOWÓD]     02:33:06  dockerd/containerd restart
                → FinishedAt ~02:33 dla api/worker/frontend/cloudflared/…

[F]           02:34     inne kontenery UP; DB dalej restarting(137)

[skutek]      API: failed to resolve / connect host 'db'
                → Application startup failed → Exit 3
                → restart: always → setki restartów → DSM alerts
```

---

## Ryzyko utraty danych

**DATA_INTEGRITY_RISK: MEDIUM**

- Volume danych istnieje; brak `PANIC`/jawnej korupcji w logach.
- Wielokrotne hard-kille podczas shutdown/recovery **podnoszą** ryzyko niespójnego stanu WAL.
- **Zakaz** `pg_resetwal` / repair bez osobnego GWO i backupu.

---

## Rekomendowana naprawa (**NIE WYKONYWAĆ tutaj**)

1. Osobny GWO recovery: zatrzymać pętlę API, zwolnić RAM, **start tylko DB**, czekać na `ready to accept connections`, potem API/worker.
2. Przed startem DB: upewnić się, że snapshoty/backupy nie trwają.
3. Ustal w DSM UI / Log Center (wymaga wyższych uprawnień): kto wydał stop o 02:08 (CM audit).
4. Rozważyć zmianę harmonogramu snapshotów Firmowe z dala od okna nocnego IFG **albo** izolację I/O.
5. Rozważyć `stop_grace_period` > default dla Postgres (dłuższy clean shutdown).
6. Monitoring: alert gdy DB nie-READY > N minut.
7. **Nie** klasyfikować/naprawiać jako „OOM fix” bez kern OOM evidence.

---

## HOST_OOM / CGROUP_OOM (pola wymagane)

- **HOST_OOM:** NO *(z ograniczeniem: brak odczytu kern.log)*  
- **CGROUP_OOM:** NO  
- **DOCKER_OOMKILLED:** NO  

## EXTERNAL_TRIGGER

**CORRELATED: YES** — Firmowe Snapshot 02:05 + Docker daemon restart 02:33  
**DIRECT ACTOR of 02:08 docker stop: UNKNOWN** (brak docker events / CM audit)

## PRODUCTION_CHANGED

**NO**

---

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

(Forensyka read-only; brak zmian aplikacji. Produkcja nadal down/restarting — wymaga osobnego GWO recovery.)

---

🩷 STATUS KOŃCOWY

✅ Co działa
- Zebrano inspect DB, cgroup memory, logi Postgres, korelację Task Scheduler, uptime hosta, LSTART dockerd.
- OOM wykluczony na poziomie Docker + cgroup kontenera (`OOMKilled=false`, `failcnt=0`).
- Ustalono FIRST_FAILURE_AT i mechanizm Exit 137 (SIGINT→SIGKILL).

⚠️ Znane problemy
- `docker events` puste; brak CM audit / kern.log (Permission denied) → bezpośredni sprawca `docker stop` o 02:08 = UNKNOWN.
- DB nadal w restart loop; produkcja nie naprawiona (zgodnie z zakresem).

❌ Co nie działa
- `ifg-db-1` nie osiąga READY; API w pętli restartów (skutek).

### A. Root cause
EXTERNAL_DOCKER_KILL (SIGINT/stop → SIGKILL/137); nie OOM. Korelacja E (Firmowe 02:05) + F (dockerd 02:33).

### B. Zmienione pliki
- `docs/reports/2026-08-14_GWO-IFG-INCIDENT-DB-SIGKILL-0002.md` (tylko raport lokalny)

### C. Deploy
NIE — produkcja READ-ONLY; brak deployu.

### D. Testy
Diagnostyka SSH read-only na DS723+ (inspect, logs, cgroup, df, ps, Task Scheduler files).

### E. Następny krok
Osobne GWO recovery DB (stop API loop → start DB → wait READY → API). DSM Log Center / sudo kern.log dla potwierdzenia aktora 02:08.

## Decyzje dla ChatGPT

1. Czy otworzyć GWO recovery przy MEDIUM data-integrity risk (bez `pg_resetwal`, tylko czysty start i obserwacja recovery)?
2. Czy przesunąć Task Scheduler id=10 (Firmowe Snapshot 02:05) poza okno nocne IFG mimo braku dowodu bezpośredniego związku?
3. Czy dodać `stop_grace_period` dla `db` w compose w kolejnym GWO hardening?

## Wygenerowane raporty

- `/Users/lukasz/projekty/ifg_standalone/docs/reports/2026-08-14_GWO-IFG-INCIDENT-DB-SIGKILL-0002.md`
