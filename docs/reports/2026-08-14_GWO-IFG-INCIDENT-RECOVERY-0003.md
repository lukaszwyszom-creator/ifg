# GWO-IFG-INCIDENT-RECOVERY-0003

**Data:** 2026-08-14  
**Tryb:** CONTROLLED PRODUCTION RECOVERY  
**Host:** DS723+ `/volume1/docker/ifg_v2/ifg_standalone`  
**Compose:** `docker/docker-compose.prod.yml` (project `ifg`)

---

## STATUS

**RECOVERY_SUCCESS**

Produkcyjny stack IFG (db, api, worker, frontend) działa stabilnie po kontrolowanym odzyskaniu.  
**INCIDENT_ROOT_TRIGGER:** UNKNOWN / NOT INVESTIGATED IN THIS GWO.

## VERDICT

PostgreSQL wrócił do `ready to accept connections` po automatycznym WAL recovery.  
Kanoniczny kontener `ifg-db-1` jest `healthy`. API `/health` = **200**, bez restart loop.  
Obserwacja ≥10 min: RestartCount DB/API **bez wzrostu**, brak nowych SIGINT/SIGKILL/PANIC.

---

## Stan przed recovery (ETAP 0)

**Timestamp preserve:** 2026-08-14 07:40:24 CEST

| Kontener | Status | ExitCode | RestartCount | Health | OOMKilled |
|----------|--------|----------|--------------|--------|-----------|
| `ifg-db-1` | restarting | **137** | **26** | unhealthy | false |
| `ifg-api-1` | restarting | **3** | **311** (później 318 przed stop) | unhealthy | false |
| `ifg-worker-1` | Up ~5h | 0 | 0 | — | — |
| `ifg-frontend-1` | Up ~5h | 0 | 0 | — | — |

**DB StartedAt/FinishedAt (zombie):** `2026-08-14T00:31:13Z` / `00:31:25Z` (Pid=0, Restarting=true)  
**API:** fail zależności DB (wcześniejsza forensyka 0001/0002).

---

## ETAP 1 — Storage safety gate

| Check | Wynik |
|-------|-------|
| Free `/volume1` | 62 GiB free (36% used) — **PASS** |
| Volume `docker_postgres_data` | istnieje — **PASS** |
| PGDATA via RO alpine | `PG_VERSION=17`, `base`/`global`/`pg_wal` OK, ~66.6 MiB — **PASS** |
| Jawne błędy I/O/BTRFS | brak w dostępnym zakresie — **PASS** |
| Stale `postmaster.pid` | obecny (timestamp 00:31, stan `ready`) — **lockfile po zabitym procesie** |

**GATE: PASS**

---

## Wykonane operacje produkcyjne (bez deploy/migrate/rebuild)

1. **Stop `ifg-api-1`** — przerwanie restart loop / ciśnienie RAM (**PASS**, Status=exited).  
2. **Próba stop/kill `ifg-db-1`** — **FAIL**: `tried to kill container, but did not receive an exit event` (zombie Docker).  
3. **`synopkg start ContainerManager`** — **FAIL** (`failed to lock packages`; status pakietu raportowany jako `stop` mimo żywego `dockerd`).  
4. **ODSTĘPSTWO — sidecar `ifg-db-recovery`:**  
   - usunięto stale `postmaster.pid` (tylko lockfile),  
   - `docker run` Postgres 17 na tym samym volume + `--network docker_ifg_prod --network-alias db`,  
   - **bez** `pg_resetwal` / repair / migracji.  
5. Po sukcesie sidecar + wyjściu zombie: **stop recovery → `docker start ifg-db-1`** (kanoniczny kontener).  
6. **`docker start ifg-api-1`** po PASS DB.  
7. Worker: stop wcześniej timeoutował; kontener pozostał **Up** (bez dalszej ingerencji — unikać `docker inspect ifg-worker-1`, zawiesza API Dockera).

**NIE wykonano:** deploy, git pull, Alembic, rebuild obrazów, zmiana restart policy / compose, `pg_resetwal`, vacuum/reindex, reboot NAS, usuwanie wolumenów.

---

## PostgreSQL recovery log (sidecar → kanoniczny)

### Sidecar `ifg-db-recovery` (2026-08-14 07:53 CEST)

```
database system was interrupted; last known up at 2026-08-14 02:31:39 CEST
database system was not properly shut down; automatic recovery in progress
redo starts at 0/92270E0
invalid record length at 0/9227118: expected at least 24, got 0
redo done at 0/92270E0
checkpoint complete: end-of-recovery ...
database system is ready to accept connections   ← 07:53:11.545 CEST
```

Interpretacja: normalne crash recovery; „invalid record length … got 0” = typowy koniec WAL po twardym kill — **nie** korupcja katalogu.

### Kanoniczny `ifg-db-1` (po przełączeniu)

```
database system was shut down at 2026-08-14 07:58:45 CEST
database system is ready to accept connections   ← 07:58:58.074 CEST
```

**DB_READY (kanoniczny):** `2026-08-14 07:58:58.074 CEST`  
**DB_READY (pierwszy po outage, sidecar):** `2026-08-14 07:53:11.545 CEST`

Stabilność DB: ≥5 min na sidecar (Pid stały, RC=0, brak PANIC), potem ≥5 min na kanonicznym (`healthy`, Pid=7769), łącznie ≫5 min przed API.

---

## ETAP 3 — Integrity gate

| Check | Wynik |
|-------|-------|
| Connect `ksef_backend` | PASS |
| `SELECT 1` | PASS |
| Alembic | `p6q7r8s9t0u1` |
| Kluczowe tabele | `invoices`, `invoice_items`, `users`, `warehouse_items`, `warehouse_documents`, `contractors`, `alembic_version` |
| Counts (read-only) | invoices **129**, invoice_items **170**, users **3**, warehouse_items **1**, warehouse_documents **5**, contractors **34** |
| PANIC / corruption w logu recovery | brak |

**DATA_INTEGRITY_STATUS:** **RECOVERED_OK** (crash recovery zakończony; dane odczytywalne; brak dowodu utraty — pełny audit vs backup poza zakresem).

---

## ETAP 4 — API recovery

| Moment | RestartCount | Status | `/health` |
|--------|--------------|--------|-----------|
| Przed | **318** (preserve: 311) | restarting / Exit 3 | n/a |
| Po `docker start` 08:04:46 CEST | **0** | running / healthy | **200** |
| +5 min (08:12) | **0** | healthy | **200** |

Body `/health` zawiera `db_timezone: Europe/Warsaw` → ścieżka DB działa.

Stabilność API ≥5 min: **PASS** (ten sam StartedAt, RC bez wzrostu).

---

## ETAP 5 — Stack

| Usługa | Stan końcowy (08:24 CEST) |
|--------|---------------------------|
| db | Up ~25 min (**healthy**) |
| api | Up ~19 min (**healthy**) |
| worker | Up ~6 h (bez restartu w recovery) |
| frontend | Up ~6 h, HTTP **200** na `:32768` |

**STACK_STATUS:** **HEALTHY**

---

## ETAP 6 — Functional smoke (bez mutacji)

| Test | Wynik |
|------|-------|
| Frontend `http://127.0.0.1:32768/` | **200** |
| API `/health` | **200** + DB timezone |
| `/api/v1/invoices/` bez tokenu | **401** (nie 500) |
| `SELECT count(*) FROM invoices` | **129** |

Brak: faktur testowych, KSeF, purchase sync, zapisów.

---

## ETAP 7 — Obserwacja 10 min

| | Start ~08:14 | End 08:24:43 |
|--|--------------|--------------|
| DB RC | 0 | **0** |
| DB Pid | 7769 | **7769** |
| API RC | 0 | **0** |
| `/health` | 200 | **200** |
| Nowe fast shutdown / SIGKILL | — | **brak** |
| Crash loops | — | **brak** |

**Wynik:** **SUCCESS** (nie RECOVERY_UNSTABLE).

---

## RestartCount przed / po

| | BEFORE | AFTER |
|--|--------|-------|
| DB | **26** | **0** |
| API | **311→318** | **0** |

Uwaga: Docker zeruje RestartCount po udanym czystym starcie po `exited` — spadek nie oznacza „cofnięcia historii”, tylko nowy cykl życia kontenera.

---

## Odstępstwa i ryzyka operacyjne

1. **Sidecar recovery** wymagany przez zombie `ifg-db-1` (kill bez exit event).  
2. **Usunięcie stale `postmaster.pid`** — standardowy krok; nie jest `pg_resetwal`.  
3. **`docker inspect ifg-worker-1` zawiesza** klienta Dockera — unikać do czasu porządku Container Manager.  
4. **`synopkg status ContainerManager` = stop** przy żywym `dockerd` (PID z `/var/run/docker.pid`, sock od 02:33) — niespójność DSM; wymaga osobnego GWO (sudo / UI).  
5. Hasło DB pojawiło się w sesji diagnostycznej `docker inspect` Env — **nie logować w ticketach**; rozważyć rotację w osobnym GWO.

---

## Rekomendacje (NIE w tym GWO)

1. Post-mortem aktora 02:08 (osobne GWO).  
2. Naprawa stanu pakietu Container Manager (sudo/`synopkg`).  
3. Usunięcie/unikanie zombie: procedura `stop` timeout + audit.  
4. `stop_grace_period` dla Postgres.  
5. Monitoring: alert gdy DB nie-READY > N minut.

---

## RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED  
- [ ] READY_FOR_DEPLOY  
- [x] **DEPLOYED_TO_DS723** *(odzyskanie runtime, bez nowego kodu)*  
- [x] **PRODUCTION_VERIFIED** *(health + smoke + 10 min observe)*  

---

🩷 STATUS KOŃCOWY

✅ Co działa  
- DB healthy, READY, Pid stabilny  
- API healthy, `/health` 200  
- Frontend 200, worker Up  
- Integrity SELECT + Alembic OK  

⚠️ Znane problemy  
- ContainerManager synopkg metadata = stop  
- Worker inspect hang  
- Root trigger 02:08 nierozpoznany  

❌ Co nie działa  
- Brak (w zakresie smoke); pełny E2E UI użytkownika nie był wykonywany  

### A. Root cause (tego GWO — recovery blocker)
Zombie Docker state `ifg-db-1` (Pid=0, kill bez exit event) uniemożliwiał start kanonicznego kontenera; obejście: sidecar + clean start kanonicznego po zwolnieniu volume.

### B. Zmienione pliki
- `docs/reports/2026-08-14_GWO-IFG-INCIDENT-RECOVERY-0003.md` (lokalnie)

### C. Deploy
Brak deployu kodu. Operacje: stop/start kontenerów + tymczasowy sidecar Postgres.

### D. Testy
`/health` 200, frontend 200, invoices 401, SQL counts, 5+5+10 min observe.

### E. Następny krok
GWO post-mortem 02:08 + porządek Container Manager (sudo). Opcjonalnie rotacja hasła DB jeśli wyciek w logach sesji.

## Decyzje dla ChatGPT

1. Czy akceptować sidecar jako standardową procedurę przy zombie CM na Synology?  
2. Czy otworzyć natychmiast GWO na naprawę `synopkg ContainerManager=stop` vs żywy dockerd?  
3. Czy rotować `POSTGRES_PASSWORD` po ekspozycji w inspect podczas recovery?

## Wygenerowane raporty

- `/Users/lukasz/projekty/ifg_standalone/docs/reports/2026-08-14_GWO-IFG-INCIDENT-RECOVERY-0003.md`
