# GWO-IFG-INCIDENT-API-RESTART-LOOP-0001

**Data diagnostyki:** 2026-08-14 07:23–07:25 CEST  
**Tryb:** READ-ONLY (brak zmian produkcji, brak deployu, brak restartów, brak migracji)  
**Host:** DS723plus (`zdalny_admin@ds723`)  
**Repo produkcyjne:** `/volume1/docker/ifg_v2/ifg_standalone`  
**Repo lokalne (kanoniczne):** `/Users/lukasz/projekty/ifg_standalone` (branch `production`)

---

## STATUS

**INCIDENT_ACTIVE / DIAGNOSIS_COMPLETE**

`ifg-api-1` i `ifg-db-1` są w pętli restartów. API nie startuje, bo nie może połączyć się z PostgreSQL. Użytkownicy IFG mają **pełną niedostępność API**.

## VERDICT

Restart loop `ifg-api-1` **nie jest** pierwotnym crashem logiki biznesowej IFG (KSeF/SMTP/scheduler aplikacji).

Jest to **wtórna pętla** wynikająca z:

1. niedostępności / niestabilnego startu `ifg-db-1`,
2. polityki `restart: always` na API,
3. twardego failu startu Uvicorn przy `OperationalError` do hosta `db`.

## ROOT_CAUSE

**C. DATABASE_DEPENDENCY** (bezpośrednia przyczyna pętli API)

z przyczyną nadrzędną dla DB:

**B. OOM_OR_RESOURCE_KILL** (ExitCode DB `137` = SIGKILL)  
oraz **D. EXTERNAL_RESTART_TRIGGER** (nocny `fast shutdown request` ~02:08 CEST, skorelowany z Task Scheduler DSM).

### Łańcuch przyczynowy (dowodowy)

```
~02:08 CEST  Postgres: "received fast shutdown request" (administrator command)
     ↓
02:15–02:31  DB próbuje startować wielokrotnie; przerywany (Exit 137 / SIGKILL)
             log: "database system was interrupted"
     ↓
~02:33        dockerd/ContainerManager procesy startują (nowy uptime ~5h)
     ↓
od ~02:30+   ifg-db-1 Status=restarting (RestartCount≈26), brak IP na sieci
     ↓
ifg-api-1    lifespan → bootstrap_initial_admin → connect host 'db'
             → "failed to resolve host 'db'" / OperationalError
             → "Application startup failed. Exiting." → ExitCode=3
     ↓
restart: always → setki restartów API → powiadomienia DSM (>60)
```

## CONFIDENCE

**90%** — bezpośrednia przyczyna pętli API (brak DB / DNS `db`)  
**75%** — dokładny agent SIGKILL na DB (host OOM vs Docker kill podczas nieudanego startu; `OOMKilled=false` w inspect, ale Exit `137` i profil RAM 1.9 GiB + 1 GiB swap użytego)

---

## Snapshot kontenerów (2026-08-14 ~07:25 CEST)

| Kontener | Status | RestartCount | ExitCode | OOMKilled | Restart policy | Uwagi |
|----------|--------|--------------|----------|-----------|----------------|-------|
| **ifg-api-1** | restarting | **272** | **3** | false | always | unhealthy; brak IP na `docker_ifg_prod` |
| **ifg-db-1** | restarting | **26** | **137** | false | always | unhealthy; brak IP; restartuje ~5 h |
| ifg-worker-1 | Up ~5 h | 0 | 0 | false | always | proces `python -m app.worker` żywy |
| ifg-frontend-1 | Up ~5 h | 0 | 0 | false | always | static up |
| cloudflared-ifg | Up ~5 h | — | — | — | — | tunnel up |

### Inspect `ifg-api-1` (istotne pola)

- Status=`restarting`, Running=`true`, Restarting=`true`
- RestartCount≈270–272 (rosnący w trakcie diagnostyki)
- ExitCode=`3`
- OOMKilled=`false`
- Error=*(pusty)*
- StartedAt/FinishedAt: cykle ~kilka sekund (np. start `05:23:46Z`, finish `05:23:51Z`)
- Health=`unhealthy` (curl `/health` → connection refused podczas startu)
- RestartPolicy=`always`
- Cmd=`uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Memory limit=`0` (bez limitu cgroup)

### Znaczenie ExitCode

| Code | Znaczenie w tym incydencie |
|------|----------------------------|
| **0** | normalne wyjście — **nie** obserwowane dla API w pętli |
| **1** | ogólny błąd — widoczne w healthcheck curl fail |
| **3** | **API:** Uvicorn kończy proces po `Application startup failed` (crash startu, nie OOM) |
| **137** | **DB:** 128+9 = **SIGKILL** (zabicie procesu; typowo OOM killer / `docker kill -9` / host) |
| **139** | SIGSEGV — **nie** obserwowane |
| **143** | SIGTERM graceful — początkowy shutdown DB wyglądał na SIGTERM (`fast shutdown`), potem pętla kończy się **137** |

---

## Częstotliwość restartów API

- Interwał między kolejnymi `Application startup failed`: **~65–70 s** (backoff Docker `restart: always`).
- Przykład (UTC z logów):
  - `05:21:36Z` fail
  - `05:22:42Z` fail
  - `05:23:48Z` fail
- `COUNT_FAIL` w logach API: **283** wystąpień `Application startup failed`.
- RestartCount API: **≥270** → zgodne z nocnymi powiadomieniami DSM (>60).

Docker events history dla `ifg-api-1` (ostatnie 36 h): **puste** na tym hoście (Synology/Docker nie zwrócił historii events) — sekwencja die→start wnioskowana z inspect + timestamps logów.

---

## Najważniejsze fragmenty logów

### API (powtarzający się crash startu)

```text
File "/app/app/main.py", line 62, in application_lifespan
  auth_service.bootstrap_initial_admin(...)
...
sqlalchemy.exc.OperationalError: (psycopg.OperationalError)
  failed to resolve host 'db': [Errno -2] Name or service not known
ERROR:    Application startup failed. Exiting.
```

Brak dowodów w aktualnej pętli na: KSeF exception, SMTP crash, segfault, worker timeout aplikacji jako pierwotny trigger.

### DB — inicjacja kryzysu (~02:08 CEST)

```text
2026-08-14 02:08:11.992 CEST [1] LOG:  received fast shutdown request
2026-08-14 02:08:12.599 CEST ... FATAL: terminating connection due to administrator command
2026-08-14 02:08:17.102 CEST [33] LOG:  shutting down
2026-08-14 02:08:18.040 CEST [33] LOG:  checkpoint starting: shutdown immediate
```

### DB — nieudane próby powrotu

```text
2026-08-14 02:15:00 ... starting PostgreSQL 17.9 ... listening on 0.0.0.0:5432
(kilka kolejnych "Skipping initialization" / start bez dojścia do "ready to accept connections")
2026-08-14 02:24:56 ... starting PostgreSQL ...
2026-08-14 02:24:57 ... database system was interrupted; last known up at 2026-08-14 02:24:41 CEST
```

Historycznie w logach DB widać **powtarzalny wzorzec nocny ~02:08–02:23** (broken pipe / connection lost) przez wiele dni — silna korelacja z nocnymi zadaniami DSM.

---

## Compose produkcyjny (read-only)

Plik: `docker/docker-compose.prod.yml` (prod HEAD `9b4d187…`, branch `production`)

- project `name: ifg`
- **api:** `restart: always`, `depends_on: db (service_healthy)`, healthcheck curl `/health` co 30s
- **worker:** `restart: always`, depends_on db healthy
- **db:** `restart: always`, postgres:17, healthcheck `pg_isready`
- sieć external `docker_ifg_prod`, volume external `docker_postgres_data`

W trakcie pętli oba kontenery (api/db) mają **puste** `EndpointID`/`IPAddress` na `docker_ifg_prod` → DNS alias `db` nie działa → API failuje zanim w ogóle dojdzie do TCP 5432.

---

## Zasoby NAS

| Metryka | Wartość |
|---------|---------|
| RAM | **1.9 GiB** total; ~850 MiB used; ~230 MiB free; ~850 MiB available |
| Swap | **3.1 GiB**; **~1.0 GiB used** |
| Load | ~0.4 (niski w momencie pomiaru) |
| Disk `/volume1` | 96 G, 36% used — **nie** jest przyczyną |
| OOM w `kern.log`/`dmesg` | **brak czytelnych wpisów** (ograniczony dostęp / rotacja) |

Host jest **ciasny pamięciowo** jak na Postgres 17 + API + worker + cloudflared + Synology services. Exit **137** DB jest spójny z zabiciem przy starcie pod presją RAM, nawet gdy Docker `OOMKilled=false`.

---

## Możliwe zewnętrzne źródła restartu

| Źródło | Ocena |
|--------|--------|
| DSM Task Scheduler (`/etc/crontab` → `synoschedtask`) | **PRAWDOPODOBNY współczynnik** — m.in. `5 2 * * *` id=10 (~02:05), `30 2 * * *` id=11 (~02:30); korelacja z shutdown DB 02:08 i restartem dockerd ~02:33 |
| Guardian scripts w repo | obecne na dysku; **brak dowodu** że uruchamiały się tej nocy (nie ruszano tasków) |
| Deploy/release automation | **brak** oznak deployu w trakcie incydentu |
| Container Manager `restart: always` | **wzmacnia** pętlę (nie jest pierwotnym triggerem nocnym) |
| Ręczne stop w CM | możliwe („administrator command”), ale wzorzec wielodniowy ~02:xx wskazuje raczej na automat |

---

## Wpływ na użytkowników / dane

| Obszar | Ocena |
|--------|-------|
| Działanie IFG (API) | **DOWN** — użytkownicy nie mogą korzystać z backendu |
| Frontend / tunnel | kontenery „Up”, ale bez API funkcjonalność biznesowa martwa |
| Utrata danych | **niskie–średnie ryzyko**: volume `docker_postgres_data` istnieje; DB nie dochodzi do stabilnego „ready”; powtarzane hard-kille podczas recovery **zwiększają** ryzyko uszkodzenia, ale nie stwierdzono PANIC/korupcji w dostępnych logach |
| Integralność transakcji nocnych | możliwe przerwane połączenia klientów (historyczne broken pipe) |

---

## Proponowana naprawa (**NIE WYKONYWAĆ w tym GWO**)

Kolejność bezpieczna (osobny GWO recovery):

1. **Zatrzymać pętlę kontrolowanie** (np. `compose stop api` / tymczasowo ograniczyć restart) — świadoma zmiana stanu, wymaga akceptacji.
2. **Zwolnić RAM** na NAS (wyłączyć zbędne kontenery/usługi nocne, nie kasować volume DB).
3. **Uruchomić wyłącznie `ifg-db-1`**, czekać na log: `database system is ready to accept connections` + `pg_isready`.
4. Dopiero potem start `api` i `worker`; weryfikacja `/health`.
5. Przegląd Task Scheduler DSM (backup/space reclaim ~02:00) — rozdzielić w czasie od Postgres.
6. Rozważyć limity pamięci / monitoring RAM / alert gdy DB unhealthy > N minut.
7. Osobno: hardening startu API (retry DB zamiast natychmiastowego exit 3) — zmiana kodu, poza incydentem.

**Zakaz w recovery bez osobnej decyzji:** `docker rm`, rebuild obrazów, migracje Alembic, kasowanie volume `docker_postgres_data`.

---

## Klasyfikacja (wymagana)

**PRIMARY:** `C. DATABASE_DEPENDENCY`  
**CONTRIBUTING:** `B. OOM_OR_RESOURCE_KILL` (DB Exit 137), `D. EXTERNAL_RESTART_TRIGGER` (shutdown ~02:08), `E. DOCKER_OR_CONTAINER_MANAGER` (`restart: always` + brak historii events)

Nie: czysty A jako root (brak tracebacku biznesowego), nie F jako root (healthcheck tylko potwierdza down), nie G samodzielnie (host żywy; problem w stacku kontenerów + pamięć).

---

## RELEASE STATE

N/A (incydent diagnostyczny; brak wdrożenia).

## PRODUCTION_CHANGED

**NO**

## Decyzje dla ChatGPT

1. Czy natychmiast otwierać GWO recovery (stop pętli + start DB-only), mimo że to zmieni stan produkcji?
2. Czy priorytetem jest najpierw zwolnienie RAM / przegląd Task Scheduler przed jakimkolwiek `docker start`?
3. Czy akceptowalne jest tymczasowe `restart: on-failure` dla API po recovery (zmiana compose — wymaga osobnego GWO)?
