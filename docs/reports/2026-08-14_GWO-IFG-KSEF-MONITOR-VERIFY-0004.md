# GWO-IFG-KSEF-MONITOR-VERIFY-0004

**Data diagnostyki:** 2026-08-14 ~21:31–21:35 CEST  
**Tryb:** READ-ONLY (bez sync, bez restartów, bez zmian schedulera/konfigu, bez deployu/migracji)  
**Host:** DS723+ `/volume1/docker/ifg_v2/ifg_standalone`

---

## STATUS

**DIAGNOSTIC_COMPLETE**

Monitor KSeF **nie wykonał żadnej sesji 14.08.2026**.  
Komponent schedulera (`ifg-worker-1`) jest **efektywnie martwy** mimo `docker ps` = Up.

## VERDICT

1. Produkcyjny monitor KSeF uruchamia **worker IFG** (`python -m app.worker`) — wbudowany tick schedulera, **nie** DSM Task Scheduler / cron hosta.
2. Harmonogram prod: `KSEF_AUTO_SYNC_ENABLED=true`, `KSEF_AUTO_SYNC_CRON=0 8,14,20 * * *` → **08:00, 14:00, 20:00** Europe/Warsaw.
3. Ostatnia poprawnie zakończona sesja: **2026-08-13 20:00:08.979 CEST**.
4. Dziś **08:00, 14:00 i 20:00 — MISSED** (0 rekordów `SCHEDULER_*` / `PURCHASE_SYNC_*` / jobów sync w DB).
5. Worker: kontener widoczny jako Up ~19h, ale **brak procesów w cgroup**, `docker inspect`/`logs`/`exec` wiszą lub puste — stan analogiczny do zombie Dockera z incydentu DB.
6. Brak sesji **nie powoduje trwałego pominięcia faktur** przy następnej poprawnej sync (incremental + overlap 2 dni) — potwierdzone kodem.

---

## 1. Komponent schedulera (dowód)

| Źródło | Fakt |
|--------|------|
| `docker/docker-compose.prod.yml` | service `worker` → `command: python -m app.worker` |
| `app/worker/__main__.py` | pętla: `_run_scheduler_tick()` → enqueue `sync_purchase_invoices` |
| `app/worker/ksef_auto_sync_scheduler.py` | evaluate cron minute/hour |
| `.env.production` | `KSEF_AUTO_SYNC_ENABLED=true`, `KSEF_AUTO_SYNC_CRON=0 8,14,20 * * *` |
| DSM Task Scheduler / crontab | **brak** wpisów KSeF/IFG sync (skan read-only) |

**SCHEDULER_COMPONENT:** `ifg-worker-1` (in-process KSeF auto-sync scheduler)

---

## 2. Czy komponent działa?

| Check | Wynik |
|-------|-------|
| `docker ps` worker | Up ~19 hours |
| Procesy w cgroup kontenera | **NO_PROCESSES_IN_WORKER_CGROUP** |
| `docker inspect ifg-worker-1` | **timeout** (hang) |
| `docker logs ifg-worker-1` | **timeout** |
| `docker exec … printenv` | puste / brak ENV |
| `ksef_sync_states` last_attempt | **2026-08-14 02:08:00.184 CEST** (ostatni tick DB) |
| Transmissions / jobs 14.08 | **0** |
| Porównanie API | inspect OK, Pid=13707, healthy |

**Wniosek:** scheduler **nie działa**. Kontener worker jest w stanie **zombie/empty** (Up bez procesu aplikacji).

---

## 3. Harmonogram produkcyjny

**CONFIGURED_SCHEDULE:** `0 8,14,20 * * *` (Europe/Warsaw via `TZ=Europe/Warsaw` na workerze)

| Slot | Godzina |
|------|---------|
| 1 | **08:00** |
| 2 | **14:00** |
| 3 | **20:00** |

---

## 4–6. Sesje 14.08.2026

Stan schedulera w DB (`scope=ksef_purchase_auto_scheduler`):

- `last_executed_slot` = **`2026-08-13T20:00`**
- `last_success_at` = 2026-08-13 20:00:04
- `last_attempt_at` = **2026-08-14 02:08:00** (tick minutowy tuż przy początku awarii; brak późniejszych commitów)

Stan sync zakupów (`scope=purchase_invoices`):

- `last_success_at` = 2026-08-13 20:00:08
- `last_date_from/to` = 2026-08-11 → 2026-08-13
- counts: ksef_returned=2, created=0, skipped_existing=2

### Tabela slotów dziś

| scheduled_at | Trigger | Job start | Rekord sesji / journal | Status | Faktury | Error | Przyczyna braku |
|--------------|---------|-----------|------------------------|--------|---------|-------|-----------------|
| **2026-08-14 08:00** | NIE | NIE | NIE | — | — | — | Worker martwy; DB dopiero READY 07:58:58; API start ~08:04 — ale worker i tak bez procesu |
| **2026-08-14 14:00** | NIE | NIE | NIE | — | — | — | Worker nadal bez procesu; DB/API już healthy |
| **2026-08-14 20:00** | NIE | NIE | NIE | — | — | — | Worker nadal bez procesu |

**background_jobs** typu `sync_purchase_invoices` utworzone 14.08: **0**  
**transmissions** 14.08 (dowolne): **0**  
**invoices created_at dziś:** **0**

### Korelacja ~08:00 vs recovery

| Czas CEST | Zdarzenie |
|-----------|-----------|
| 02:08 | Awaria DB; ostatni `last_attempt` schedulera |
| ~02:33 | Restart dockerd; worker „Up” od tego czasu (bez żywego procesu) |
| **07:58:58** | DB READY (kanoniczny) |
| ~08:04 | API start / healthy (recovery 0003) |
| **08:00** | Slot powinien wystartować — **nie wystartował** (worker dead) |
| 14:00 / 20:00 | Kolejne sloty — **missed** |

Uwaga architektury recovery slotów: po ożywieniu workera enqueue’owany jest **tylko najnowszy** due slot (`latest_due_slot_key`, test `test_scheduler_recovers_only_latest_missed_slot`). Sloty 08:00 i 14:00 **nie zostaną osobno „dobiłe”** jako wpisy monitora; faktury i tak wejdą w oknie overlap (pkt 10).

---

## 7. Logi komponentu

- `docker logs ifg-worker-1` — **niedostępne** (timeout / hang klienta Dockera).
- Dowody z DB są wystarczające: brak jakichkolwiek zdarzeń `SCHEDULER_SLOT` / `SCHEDULER_ENQUEUE` / `PURCHASE_SYNC_AUTO` po 13.08 20:01.
- Ostatni wzorzec zdrowy (13.08 20:00): SLOT → ENQUEUE → PURCHASE_SYNC_AUTO started → metadata → summary → ok; SKIP_ALREADY_EXECUTED o :01.

---

## 8. Ostatnia poprawnie zakończona sesja

**LAST_SUCCESSFUL_SESSION:** `2026-08-13 20:00:08.979659 CEST`  
- `operation_type=PURCHASE_SYNC_AUTO`, `status=ok`  
- metadata: downloaded=2, saved=0, duplicates=2  
- job `4b830c05-…`, `scheduler_slot=2026-08-13T20:00`, `scheduler_recovery=false`

---

## 9. Następna automatyczna sesja

| Pojęcie | Wartość |
|---------|---------|
| Następny **kalendarzowy** slot cron | **2026-08-15 08:00** CEST |
| Gdyby worker ożył **teraz** (po 20:00 14.08) | enqueue recovery **`2026-08-14T20:00`** (jedyny latest missed), potem normalnie 15.08 08:00 |
| Warunek | wymaga naprawy/restartu workera (poza tym GWO) |

**NEXT_SCHEDULED_SESSION (kalendarz):** `2026-08-15 08:00 CEST`  
**NEXT_IF_WORKER_RECOVERS_NOW:** `2026-08-14T20:00` (recovery)

---

## 10. Ryzyko trwałego pominięcia faktur

Kod (`resolve_purchase_sync_window_details`, incremental):

```
date_from = last_date_to - overlap_days
```

Prod: brak override `KSEF_PURCHASE_SYNC_OVERLAP_DAYS` w `.env.production` → default **`overlap_days=2`** (`app/core/config.py`).  
Obecne `last_date_to=2026-08-13` → następna sync: **2026-08-11 … dziś**.

Scheduler auto job zawsze: `incremental=True`, `force_full=False`.

**MISSED_INVOICES_RISK:** **LOW** (brak trwałego skip faktur przy następnej udanej sync).  
**Ryzyko UX/monitor:** HIGH dla widoku „dzisiejsze sesje” — sloty 08/14/20 nie pojawią się wstecz jako osobne sesje (recovery tylko latest slot).

Email notify: ostatnie SENT 2026-08-12 (gdy `saved>0`); 13.08 bez nowych faktur → brak maila (oczekiwane).

---

## Klasyfikacja

| Pole | Wartość |
|------|---------|
| **KSEF_MONITOR_STATUS** | **STOPPED** |
| **TODAY_SESSIONS** | **MISSED** |
| **REPAIR_REQUIRED** | **YES** (nie w tym GWO) |

Rekomendowana naprawa (NIE wykonana): controlled restart `ifg-worker-1` (uwaga na hang Docker API / zombie), weryfikacja ticków `SCHEDULER_*` i jednej sesji recovery; bez ręcznego full sync o ile recovery wystarczy.

---

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED  
- [ ] READY_FOR_DEPLOY  
- [ ] DEPLOYED_TO_DS723  
- [ ] PRODUCTION_VERIFIED  

(Diagnostyka read-only; produkcja runtime bez zmian kodu.)

---

🩷 STATUS KOŃCOWY

✅ Co działa  
- API/DB healthy (po recovery 0003).  
- Konfiguracja auto-sync czytelna i historycznie działała do 13.08 20:00.  
- Lookback/overlap chroni przed trwałą utratą faktur.

⚠️ Znane problemy  
- Worker „Up” bez procesu; inspect/logs wiszą (jak zombie DB wcześniej).  
- Wszystkie 3 sloty 14.08 missed.

❌ Co nie działa  
- Produkcyjny monitor/scheduler KSeF (worker).

### A. Root cause
Worker IFG (nosiciel schedulera KSeF) jest martwy od okna awarii ~02:08/02:33; brak ticków → brak sesji 08/14/20.

### B. Zmienione pliki
- `docs/reports/2026-08-14_GWO-IFG-KSEF-MONITOR-VERIFY-0004.md`

### C. Deploy
NIE.

### D. Testy
Read-only: DB SQL, compose/env, cgroup scan, docker ps (bez mutacji).

### E. Następny krok
Osobne GWO: recovery workera + weryfikacja enqueue recovery slotu i `/health` monitora; nie ręczny purchase sync bez potrzeby.

## Decyzje dla ChatGPT

1. Czy natychmiast otworzyć GWO recovery `ifg-worker-1` (analog sidecar/zombie jak DB)?  
2. Czy po ożywieniu workera akceptować brak osobnych wpisów sesji 08:00/14:00 przy recovery tylko `20:00`?  
3. Czy dodać alert gdy `ksef_sync_states.last_attempt_at` > N minut względem teraz?

## Wygenerowane raporty

- `/Users/lukasz/projekty/ifg_standalone/docs/reports/2026-08-14_GWO-IFG-KSEF-MONITOR-VERIFY-0004.md`
