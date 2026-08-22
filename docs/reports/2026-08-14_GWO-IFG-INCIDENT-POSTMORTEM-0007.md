# GWO-IFG-INCIDENT-POSTMORTEM-0007

**Data forensyki:** 2026-08-14 ~22:29–22:32 CEST  
**Tryb:** READ-ONLY (bez restartów, stopów, dockerd/CM, deployu, migracji)  
**Host:** DS723+ (uptime **35 days** — brak rebootu hosta)

---

## STATUS

**POSTMORTEM_COMPLETE**

Bezpośredni aktor zdarzenia **02:08** pozostaje **UNKNOWN** (brak docker events / DSM messages / CM audit).  
Zdarzenie **02:33** to **potwierdzony restart dockerd+containerd**; aktor pakietu/operatora **UNKNOWN**.

## VERDICT

1. **02:08:** zewnętrzny `docker stop`-like wobec `ifg-db-1` (SIGINT → incomplete fast shutdown → SIGKILL/137). **Nie OOM.** Aktor **UNKNOWN**.
2. **02:33:** restart procesów `dockerd`/`containerd` + masowy Finished/Started kontenerów. Aktor **UNKNOWN**.
3. Relacja 02:08↔02:33: **POSSIBLY_RELATED** (wspólna noc / możliwa kaskada niestabilności), **nie** dowiedziony ten sam causal chain.
4. Firmowe 02:05: **CORRELATED ONLY** — mechanizm to share snapshot **bez** docker w skrypcie; IFG/PG poza share Firmowe.
5. Grace period: Compose **bez** `stop_grace_period`; `StopTimeout=<nil>` → default Docker **10 s**; PG nie dokończył shutdown before kill.

---

## PYTANIE 1 — Co wywołało stop DB o 02:08?

### CONFIRMED

| Fakt | Dowód |
|------|-------|
| `02:08:11.992 CEST` PG: `received fast shutdown request` | docker logs `ifg-db-1` |
| StopSignal kontenera = **SIGINT** | inspect (0002 + zgodne z obrazem postgres) |
| Exit **137**, `OOMKilled=false` | inspect |
| Brak PANIC / I/O / disk full w logach PG | logs |
| `docker events` dla okna = **0 linii** | synology CM nie zachował events |
| `/var/log/messages`, `synosystemd.log` | **Permission denied** dla `zdalny_admin` |
| `ContainerManager.log` | ostatnie wpisy lifecycle **2026-07-10**, brak 14.08 |

### STRONGLY SUPPORTED

- Mechanizm = **Docker container stop** (SIGINT → fast shutdown), nie crash Postgres.
- Dotknięty **co najmniej DB**; inne kontenery mają FinishedAt dopiero ~**02:33** → **nie** pełny `compose down` całego stacka ani stop całego dockerd o 02:08.

### CORRELATED ONLY

- Firmowe Snapshot **02:05:01** (task id=10).
- Historyczny wzorzec `fast shutdown request` w okolicach ~02:08–02:13 / noc:

```
2026-07-25 02:11, 07-26 02:10, 07-28 02:10, 07-29 01:45,
2026-08-04 02:10 + 02:13, 08-12 01:41, 08-14 02:08
```

(8 wystąpień w logach kontenera — wzorzec powtarzalnego zewnętrznego stopu DB.)

### UNKNOWN / wykluczone jako udowodnione

| Kandydat | Werdykt |
|----------|---------|
| Docker CLI/API / compose stop | **możliwe, niedowiedzione** |
| Container Manager UI/API | **możliwe, brak audit 14.08** |
| DSM Task Scheduler (Firmowe) | **korelacja; skrypt bez docker** |
| Hyper Backup / Snapshot Replication hook docker | **brak dowodu** |
| Guardian / IFG automation | **brak dowodu** |
| cron użytkownika z docker stop | **brak dowodu** |
| Host OOM / cgroup OOM | **NO** (0002) |

**ROOT_CAUSE_0208:** **UNKNOWN** (mechanizm: EXTERNAL_DOCKER_STOP → SIGKILL; **aktor: UNKNOWN**)  
**DIRECT_ACTOR_0208:** **UNKNOWN**

---

## PYTANIE 2 — Co stało się o 02:33?

### Timeline CONFIRMED (CEST)

| Czas | Zdarzenie | Dowód |
|------|-----------|-------|
| **02:33:06** | start procesu **dockerd** | `ps` LSTART pid 6388 |
| **02:33:07** | start **containerd** | `ps` LSTART pid 6423 |
| **02:33:08** | mtime `/var/run/docker.pid`, `docker.sock` | `stat` |
| **02:33:13** | mtime `/volume1/@docker` | `stat` |
| **~02:33:27–32** | FinishedAt wielu kontenerów (UTC 00:33) | inspect |
| **~02:34:39–52** | StartedAt tych kontenerów | inspect |

Kontenery z Finished≈02:33 / Started≈02:34:

- `ifg-frontend-1`, `cloudflared-ifg`, `syncthing-1`, `rustmailer-bichon-1`
- (historycznie też `ifg-worker-1` — 0002; obecnie zombie, inspect hang)

`ifg-db-1` w tym czasie był już w pętli restartów (próby od 02:15).

### Rozstrzygnięcie dockerd

| Hipoteza | Werdykt |
|----------|---------|
| Crash → auto-restart | **możliwe, niedowiedzione** |
| Zatrzymany przez DSM/synopkg | **możliwe**; `synopkg status ContainerManager` dziś: `status=stop` / code **263** „failed to get unit status” przy **żywym** dockerd — niespójność metadata |
| Restart przez operatora/skrypt | **brak dowodu** |
| Zatrzymany „razem” z CM package stop | **brak logu pakietu z 14.08** (`ContainerManager.log` kończy się 10.07) |

**ROOT_CAUSE_0233:** **DOCKERD_RESTART** (CONFIRMED effect); **przyczyna restartu = UNKNOWN**  
**DIRECT_ACTOR_0233:** **UNKNOWN**

Host **nie** rebootował (uptime 35d).

---

## PYTANIE 3 — Czy 02:08 i 02:33 to jeden incydent?

### Timeline A — 02:08 (DB stop)

```
02:04:46  PG checkpoint OK
02:05:01  Firmowe snapshot artifact (korelacja)
02:08:11  SIGINT / fast shutdown DB
02:08:18  shutdown checkpoint starting (nie dokończony w logu)
~02:08:22  est. SIGKILL (default 10s stop timeout) → Exit 137
02:15+    DB restart loop, brak READY
```

### Timeline B — 02:33 (daemon)

```
02:30     Task Foto Snapshot scheduled (artifact 14.08 nie znaleziony w @sharesnap/Foto)
02:33:06  dockerd start (nowy PID)
02:33:07  containerd start
02:33–34  masowy die/start kontenerów non-DB
```

### Klasyfikacja relacji

**RELATION_0208_0233: POSSIBLY_RELATED**

Uzasadnienie:

- **Nie SAME_CAUSAL_CHAIN:** brak dowodu, że ten sam aktor/komendą wywołał oba; 02:08 nie zabija całego daemona (inne kontenery żyją do 02:33).
- **Nie INDEPENDENT z pewnością:** ta sama noc, DB w crash-loop, możliwa presja I/O/RAM, potem restart dockerd.
- Dowód związku przyczynowego: **brak**.

---

## PYTANIE 4 — Firmowe 02:05

| Element | Fakt |
|---------|------|
| Mechanizm | DSM Task Scheduler **id=10**, app `SYNO.SDS.Share.Snapshot` |
| Komenda | `/usr/syno/bin/synosnapschedtask.sh local share Firmowe` |
| Artefakt 14.08 | `/volume1/@sharesnap/Firmowe/GMT+02-2026.08.14-02.05.01` **istnieje** |
| Zakres | **Share Firmowe** (Btrfs share snapshot) |
| Docker/CM w skrypcie | **`grep -c docker` = 0** — **brak** wywołań docker/container |
| freeze/thaw app | tylko locki snapshot share/LUN; **brak** pre/post docker hooks w skrypcie |
| Pre/post scripts użytkownika | **brak** w task file (tylko synosnap) |
| Dowód hooka docker 14.08 | **brak** |

**FIRMOWE_RELATION: CORRELATED ONLY** (czas + nocny wzorzec stopów DB; **nie** udowodniona przyczynowość)

IFG/PG data: `/volume1/@docker/volumes/docker_postgres_data` — **poza** share Firmowe.

---

## PYTANIE 5 — Czy dotknięty był tylko IFG?

### 01:55–02:40 CEST (dowody inspect + PG)

| Kontener | ~02:08 | ~02:33 |
|----------|--------|--------|
| `ifg-db-1` | **STOP/SIGINT** CONFIRMED | restart loop |
| `ifg-api-1` | wtórne fail (DNS/DB) — FinishedAt nadpisany recovery | restart z daemonem / later recovery |
| `ifg-worker-1` | brak dowodu stop 02:08 | Finished~02:33 → Started~02:34 → później **zombie empty cgroup** |
| `ifg-frontend-1` | przeżył do 02:33 | die/start z daemonem |
| `cloudflared-ifg` | przeżył | die/start |
| `syncthing-1` | przeżył | die/start |
| `rustmailer-bichon-1` | przeżył | die/start |
| `gma-dovecot` | exited wcześniej (Jul 25) | n/a |

**CONTAINERS_AFFECTED:**

- **02:08:** co najmniej **`ifg-db-1`** (IFG-scoped stop) — STRONGLY SUPPORTED  
- **02:33:** **wszystkie działające kontenery Dockera** (daemon-wide) — CONFIRMED

Źródło 02:08 ≠ „cały Docker daemon”; źródło 02:33 = warstwa **dockerd/CM**.

---

## PYTANIE 6 — Dlaczego Postgres dostał SIGKILL?

| Parametr | Wartość |
|----------|---------|
| SIGINT | **2026-08-14 02:08:11.992 CEST** |
| Ostatni log shutdown | **02:08:18.040** `checkpoint starting: shutdown immediate` |
| Brak | `database system is shut down` |
| Compose `stop_grace_period` | **nie ustawione** |
| `StopTimeout` inspect | **`<nil>`** → Docker default **10 sekund** |
| Est. SIGKILL | **~02:08:21.992 CEST** (SIGINT+10s) |
| **POSTGRES_GRACE_PERIOD** | **~10 s (default)** |

**CONFIRMED:** PG **nie zdążył** dokończyć fast shutdown w oknie stop timeout → Docker wysłał SIGKILL → Exit 137.  
To **nie** wymaga OOM.

---

## PYTANIE 7 — Zombie worker

| Fakt | Klasyfikacja |
|------|-------------|
| Worker Finished/Started ~02:33/02:34 (0002) | CONFIRMED (forensics 0002) |
| Później: `Up` + **empty cgroup**, inspect hang | CONFIRMED (0004/0005/0006) |
| Związek z restartem dockerd 02:33 | **STRONGLY SUPPORTED** jako typowy skutek uszkodzonej reconciliacji containerd/CM po restarcie daemona |
| Alternatywne przyczyny zombie | możliwe, bez dodatkowego logu |

**ZOMBIE_WORKER_RELATION:** **STRONGLY SUPPORTED** link do **02:33 dockerd restart** (nie do samego 02:08).

---

## PYTANIE 8 — Logi DSM (01:55–02:40)

| Źródło | Dostęp | Treść 14.08 02:xx |
|--------|--------|-------------------|
| `/var/log/messages` | **Permission denied** | niedostępne |
| `/var/log/synosystemd.log` | **Permission denied** | niedostępne |
| `/var/log/packages/ContainerManager.log` | readable | **tylko Jul 10 2026** — brak 14.08 |
| `docker events` | empty | brak historii |
| CM package var/log | Permission denied | — |

**Jednoznacznie:** przy uprawnieniach `zdalny_admin` **nie da się** ustalić aktora 02:08 ani 02:33 z logów DSM. Wymagany dostęp root/Log Center UI / sudo.

---

## CAUSAL CHAIN (tylko potwierdzone + oznaczenia)

```
[CORRELATED ONLY] 02:05 Firmowe share snapshot (bez docker w skrypcie)

[CONFIRMED] 02:08:11  Docker StopSignal=SIGINT → PG fast shutdown
[CONFIRMED] ~02:08:22 SIGKILL po ~10s default stop timeout → Exit 137
[CONFIRMED]        OOMKilled=false; nie host/cgroup OOM
[STRONGLY SUPPORTED] aktor = zewnętrzny docker stop DB (nie pełny daemon)
[UNKNOWN]          kto wydał stop

[CONFIRMED] 02:15–02:33 DB restart loop, brak READY
[STRONGLY SUPPORTED] API fail dependency (brak db DNS/connect) → Exit 3 loop

[CONFIRMED] 02:33:06 dockerd + containerd restart
[CONFIRMED] 02:33–34 masowy restart kontenerów
[UNKNOWN]          kto/co zrestartowało dockerd
[STRONGLY SUPPORTED] worker → zombie empty cgroup po tym restarcie
```

---

## RECURRENCE_RISK

**HIGH** dla wzorca nocnego stopu DB (~02:05–02:15), na podstawie **8** historycznych `fast shutdown request`.  
**MEDIUM** dla ponownego zombie po restarcie dockerd przy niespójnym stanie CM (`synopkg status=stop` + żywy dockerd).

## RECOMMENDED_PREVENTION (bez wykonania)

1. Root/Log Center: audit **kto** wywołał `container stop` 02:08 (CM / API / CLI).
2. Zwiększyć `stop_grace_period` dla `db` (np. 60–120s).
3. Alert gdy `ifg-db-1` nie-READY > N min; alert `last_attempt` schedulera.
4. Okno utrzymaniowe: naprawa CM metadata + usunięcie zombie worker (GWO-0006 BLOCKED).
5. Oddzielić I/O snapshotów od volume Docker **lub** przesunąć Firmowe z dala od okna DB — **tylko jako hipoteza operacyjna**, nie jako udowodniona przyczyna.
6. Zachować docker events / CM audit retention.

## CONFIDENCE

| Twierdzenie | % |
|-------------|---|
| Mechanizm 02:08 = docker stop → SIGINT → SIGKILL | **95** |
| Aktor 02:08 | **0** (UNKNOWN) |
| 02:33 = dockerd restart | **99** |
| Aktor 02:33 | **0** (UNKNOWN) |
| Firmowe = bezpośredni sprawca | **15** (tylko korelacja) |
| Zombie worker ↔ 02:33 | **80** |

---

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED  
- [ ] READY_FOR_DEPLOY  
- [ ] DEPLOYED_TO_DS723  
- [ ] PRODUCTION_VERIFIED  

(Forensyka docs-only.)

---

🩷 STATUS KOŃCOWY

✅ Co działa  
- Produkcja obecnie healthy (po recovery 0003/0005); postmortem nie ingerował.

⚠️ Znane problemy  
- Aktorzy 02:08 i 02:33 UNKNOWN bez logów DSM.  
- Wzorzec nocnych stopów DB — ryzyko nawrotu.  
- Zombie `ifg-worker-1` + niespójny status CM.

❌ Co nie działa  
- Brak możliwości odczytu `/var/log/messages` / synosystemd jako `zdalny_admin`.

### A. Root cause
02:08 UNKNOWN actor + CONFIRMED docker stop/SIGKILL; 02:33 UNKNOWN actor + CONFIRMED dockerd restart; Firmowe CORRELATED ONLY.

### B. Zmienione pliki
- `docs/reports/2026-08-14_GWO-IFG-INCIDENT-POSTMORTEM-0007.md`

### C. Deploy
NIE. `PRODUCTION_CHANGED: NO`

### D. Testy
Read-only SSH: ps/stat/inspect/logs/task files/snap script.

### E. Następny krok
Sudo/Log Center audit 01:55–02:40; osobne GWO CM+zombie; rozważyć `stop_grace_period`.

## Decyzje dla ChatGPT

1. Czy uznać Firmowe za wystarczający powód do przesunięcia harmonogramu mimo braku dowodu przyczynowości?  
2. Czy otworzyć GWO z sudo wyłącznie pod odczyt `messages`/`synosystemd`?  
3. Priorytet: grace period DB vs naprawa zombie CM?

## Wygenerowane raporty

- `/Users/lukasz/projekty/ifg_standalone/docs/reports/2026-08-14_GWO-IFG-INCIDENT-POSTMORTEM-0007.md`
