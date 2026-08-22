# GWO-IFG-KSEF-WORKER-NORMALIZATION-0006

**Data:** 2026-08-14 ~22:24–22:26 CEST  
**Tryb:** CONTROLLED PRODUCTION NORMALIZATION  
**Host:** DS723+ `/volume1/docker/ifg_v2/ifg_standalone`

---

## STATUS

**BLOCKED**

Normalizacja nazwy do kanonicznego `ifg-worker-1` **nie została wykonana**, ponieważ usunięcie/rename zombie wymaga operacji na poziomie Docker daemon / Container Manager, których ten GWO **zakazuje** automatycznie.

Stan produkcyjny **pozostawiony bez zmian** (bezpieczny singleton schedulera zachowany).

## VERDICT

1. Precheck PASS: DB/API healthy, `/health` 200, `ifg-worker-active` healthy + żywy `python -m app.worker`, scheduler ACTIVE.
2. `ifg-worker-1` = zombie (Up, **NO_PROCESSES** w cgroup, `docker inspect` timeout).
3. Compose na dysku prod **już** ma konfigurację z commita `2bcb29b` (PID1 python + healthcheck).
4. Próby `docker rename` / `docker rm -f` zombie → **timeout (exit 124)** — bez restartu dockerd nie da się zwolnić nazwy `ifg-worker-1`.
5. Zgodnie z Faza 2: **STOP** — nie restartowano dockerd/CM/NAS; nie zatrzymywano `ifg-worker-active` (uniknięto okna bez schedulera przy braku ścieżki powrotu do kanonicznej nazwy).

---

## FAZA 1 — PRECHECK

| Check | Wynik |
|-------|-------|
| DB | running / **healthy** |
| API | running / **healthy** |
| `/health` | **200** |
| `ifg-worker-active` | Up, **healthy**, Pid=9721, Cmd=`["python","-m","app.worker"]`, RC=0 |
| Proces active | `python -m app.worker` (1) |
| `ifg-worker-1` | Up 20h, CID `69858ab3bab4`, **NO_PROCESSES**, inspect **timeout** |
| Scheduler | `idle`, `last_executed_slot=2026-08-14T20:00`, `last_cron=0 8,14,20 * * *`, `last_attempt` świeży (ticki co min) |
| Compose prod na NAS | `command: ["python","-m","app.worker"]` + healthcheck `app.worker` (= commit **2bcb29b**) |

### Dlaczego zombie nie daje się zastąpić

- Po restarcie dockerd (incydent 14.08) kontener utknął w stanie Docker `Running` bez taska/procesów.
- `docker inspect` / `rename` / `rm -f` / `kill` **wiszą lub timeout** (brak exit event) — typowy zombie Synology Container Manager.
- Nazwa `/ifg-worker-1` jest **zajęta** przez ten rekord → `compose up` / rename live → conflict.
- Jedyna niezawodna droga zwolnienia nazwy na tym hoście w praktyce: **restart dockerd / Container Manager** (poza zakresem tego GWO).

---

## FAZA 2 — PLAN (nie wykonany poza probe)

Preferowana sekwencja (gdyby rm działał):

1. Stop `ifg-worker-active` (singleton=0 chwilowo)
2. `rm -f` zombie `ifg-worker-1`
3. `compose up -d --no-deps --no-build worker` → kanoniczny `ifg-worker-1`
4. Verify healthy + scheduler
5. Brak `ifg-worker-active`

**Wykonano wyłącznie probe:** rename/rm z krótkim timeout → FAIL.  
**Nie wykonano:** stop active, compose recreate, restart dockerd.

---

## FAZA 3 — NORMALIZACJA

**NIE WYKONANO** (BLOCKED).

| Docelowe | Aktualne |
|----------|----------|
| `ifg-worker-1` healthy kanoniczny | zombie empty |
| brak `ifg-worker-active` | **istnieje**, healthy, jedyny realny worker |

---

## FAZA 4 — SINGLETON GATE (stan bieżący, bez normalizacji)

| Metryka | Wartość |
|---------|---------|
| Kontenery „worker” w `docker ps` | 2 (`ifg-worker-active` + zombie `ifg-worker-1`) |
| **ACTIVE_WORKER_COUNT** (proces `app.worker`) | **1** |
| **ACTIVE_KSEF_SCHEDULER_COUNT** | **1** (tylko active; zombie nie tyka DB) |
| TEMP_WORKER_EXISTS | **YES** (`ifg-worker-active`) |
| ZOMBIE_WORKER_EXISTS | **YES** (`ifg-worker-1`) |

---

## FAZA 5 — SCHEDULER

- Harmonogram: **08:00 / 14:00 / 20:00** Europe/Warsaw (`0 8,14,20 * * *`)
- `last_executed_slot`: `2026-08-14T20:00`
- **NEXT_SCHEDULED_SESSION:** `2026-08-15 08:00 CEST`
- Ręcznej sync / recovery **nie uruchamiano**

**SCHEDULER_STATUS:** ACTIVE

---

## FAZA 6 — STABILNOŚĆ

Normalizacji nie wdrożono → brak 10-min observe nowego kanonicznego kontenera.  
Stan wyjściowy po probe (bez zmian runtime):

- `ifg-worker-active` nadal healthy, RC=0
- API `/health` 200
- Scheduler tick kontynuowany (`last_attempt` 22:25)

---

## Rekomendacja (osobne GWO)

**GWO dockerd/CM maintenance window** (poza 08/14/20):

1. Stop `ifg-worker-active`
2. Restart **tylko** Container Manager / dockerd (nie cały NAS, jeśli możliwe)
3. Usuń pozostałości zombie
4. `docker compose -f docker/docker-compose.prod.yml up -d --no-deps --no-build worker`
5. Singleton gate + observe 10 min
6. Usuń ewentualny leftover temp name

Nie robić tego ad-hoc w godzinach sync bez okna utrzymaniowego.

---

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED  
- [ ] READY_FOR_DEPLOY  
- [ ] DEPLOYED_TO_DS723  
- [ ] PRODUCTION_VERIFIED  

(Normalization zablokowana; runtime bez zmian.)

---

🩷 STATUS KOŃCOWY

✅ Co działa  
- Singleton schedulera (1 żywy worker).  
- DB/API/health OK.  
- Compose na dysku już zgodny z 2bcb29b.

⚠️ Znane problemy  
- Zombie `ifg-worker-1` blokuje kanoniczną nazwę.  
- Temp `ifg-worker-active` musi zostać do czasu GWO dockerd.

❌ Co nie działa  
- Normalizacja nazwy kontenera bez restartu dockerd.

### A. Root cause (bloku)
Docker zombie `ifg-worker-1` nieobsługiwalny przez `rm`/`rename`/`kill` bez dockerd restart.

### B. Zmienione pliki
- `docs/reports/2026-08-14_GWO-IFG-KSEF-WORKER-NORMALIZATION-0006.md` (tylko raport)

### C. Deploy
Brak.

### D. Testy
Precheck + probe rename/rm (timeout); weryfikacja że active nadal healthy.

### E. Następny krok
Zaplanować GWO maintenance: CM/dockerd restart → compose worker → usunięcie temp.

## Decyzje dla ChatGPT

1. Czy zaakceptować BLOCKED i żyć z `ifg-worker-active` do okna utrzymaniowego?  
2. Kiedy zaplanować restart Container Manager względem slotu 15.08 08:00?  
3. Czy Guardian ma alertować na obecność >1 kontenera `*worker*` w `docker ps`?

## Wygenerowane raporty

- `/Users/lukasz/projekty/ifg_standalone/docs/reports/2026-08-14_GWO-IFG-KSEF-WORKER-NORMALIZATION-0006.md`
