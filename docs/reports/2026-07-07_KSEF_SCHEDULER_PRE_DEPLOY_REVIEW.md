# 2026-07-07_KSEF_SCHEDULER_PRE_DEPLOY_REVIEW

Przegląd przed deployem implementacji KSeF auto-sync scheduler.  
Zakres: analiza read-only, bez deployu, bez migracji, bez zmian kodu.

---

🩷 STATUS KOŃCOWY

✅ CO DZIAŁA
- Logika schedulera (parser cron, idempotencja slotów, recovery, enqueue) jest spójna i pokryta testami jednostkowymi (9/9 w `test_ksef_auto_sync_scheduler.py`, 34/34 w pakiecie KSeF scheduler+sync).
- Żaden z 12 niezaliczonych testów pełnego `pytest` nie dotyczy plików zmienionych przez implementację schedulera.
- Blokada `FOR UPDATE` na wierszu `ksef_sync_states` (scope `ksef_purchase_auto_scheduler`) skutecznie serializuje decyzję enqueue przy istniejącym wierszu stanu.
- Produkcyjny `docker-compose.prod.yml` definiuje **jedną** instancję workera (brak replik).

⚠️ ZNANE PROBLEMY
- `SCHEDULER_TICK` zapisuje się do Monitora KSeF co minutę na worker — nadmierny wolumen wpisów (szac. ~2880/dzień/worker).
- Nieobsługiwany cron jest odrzucany w logice, ale **nie ma dedykowanego wpisu** w Monitorze (`invalid_cron` / `no_due_slot`).
- Metadane schedulera (`cron`, `slot`, `job_id`) są obcinane przez `_ALLOWED_METADATA_KEYS` w `KSeFTransmissionJournalService` — w DB zostaje głównie `description`.
- Brak testu integracyjnego dwóch workerów pod PostgreSQL (tylko testy czystej funkcji `evaluate_tick`).

❌ CO NIE DZIAŁA
- Pełny `pytest` repo: **12 failed, 1428 passed** — błędy historyczne (invoice PDF/numbering, Guardian workflows), niezwiązane ze schedulerem.
- Scheduler **nie jest jeszcze wdrożony** na DS723+ (implementacja lokalna).

---

## 1. Zależność 12 niezaliczonych testów od plików schedulera

### Pliki zmienione przez implementację schedulera

| Plik | Rola |
|------|------|
| `app/worker/ksef_auto_sync_scheduler.py` | Parser cron, ocena slotu, recovery |
| `app/worker/__main__.py` | Integracja ticka w pętli workera, `FOR UPDATE`, enqueue |
| `app/domain/enums.py` | Typy `SCHEDULER_*` |
| `app/worker/job_handlers/sync_purchase_invoices.py` | Opcjonalne `date_from`/`date_to`, `incremental` |
| `tests/unit/test_ksef_auto_sync_scheduler.py` | Testy schedulera |

### Lista 12 niezaliczonych testów (potwierdzone: `2026-07-07`)

| # | Test | Moduł | Zależność od schedulera |
|---|------|-------|-------------------------|
| 1 | `test_regression.py::test_legacy_tests_still_pass` | Guardian platform | **Brak** — pada na `test_workflows_contains_all_ifg_workflows` (workflow `ifg.release.evaluate`) |
| 2 | `test_guardian_plugins_sprint2.py::test_workflows_contains_all_ifg_workflows` | Guardian | **Brak** |
| 3 | `test_domain_invoice.py::test_sale_requires_number_local_before_send` | Invoice domain | **Brak** — regex `number_local` vs polski komunikat błędu |
| 4–6 | `test_invoice_api.py::TestInvoicePdf::*` (3 testy) | Invoice API/PDF | **Brak** |
| 7–9 | `test_invoice_numbering_regression.py::*` (3 testy) | Numeracja FV | **Brak** |
| 10–11 | `test_invoice_transitions.py::*` (2 testy) | Przejścia statusów FV | **Brak** |
| 12 | `test_transaction_hardening.py::test_same_invoice_mark_ready_idempotent_via_status_guard` | Numeracja / lock | **Brak** |

### Werdykt punktu 1

**Żaden z 12 testów nie dotyczy plików schedulera.**  
Grep po `tests/` pod kątem `ksef_auto_sync`, `scheduler`, `SCHEDULER`, `sync_purchase_invoices` w plikach invoice/guardian/transaction — brak trafień.

Jedyny pośredni kontakt: `sync_purchase_invoices.py` jest współdzielony, ale padające testy nie importują workera ani handlera sync zakupów; dotyczą sprzedaży FV, PDF i Guardian workflows.

---

## 2. Wolumen `SCHEDULER_TICK` w Monitorze KSeF

### Mechanizm

W `_run_scheduler_tick()` (`app/worker/__main__.py`):

1. Tick uruchamia się max raz na minutę per proces (`_last_scheduler_tick_key`).
2. **Każdy** tick zapisuje `SCHEDULER_TICK` do `transmissions` przez `KSeFTransmissionJournalService`.
3. Gdy slot już wykonany — dodatkowo `SCHEDULER_SKIP_ALREADY_EXECUTED` (kolejny wpis co minutę).

Pętla workera: `POLL_INTERVAL_SECONDS` (domyślnie 5 s), ale throttle minutowy jest po stronie `_last_scheduler_tick_key`.

### Szacunek wolumenu (cron `0 8,14 * * *`, 1 worker)

| Typ zdarzenia | Częstotliwość | Wpisy/dzień |
|---------------|---------------|-------------|
| `SCHEDULER_TICK` | 1/min | **1440** |
| `SCHEDULER_SKIP_ALREADY_EXECUTED` | ~1/min poza minutami slotów | **~1438** |
| `SCHEDULER_SLOT` + `SCHEDULER_ENQUEUE` | 2 sloty/dzień | **4** |
| `SCHEDULER_STARTED` | jednorazowo | **1** |

**Razem idle:** ~**2880 wpisów/dzień/worker** — dominują TICK + SKIP.

Przy **2 workerach:** ~**5760 wpisów/dzień** (każdy proces ma własny `_last_scheduler_tick_key`).

### Ocena

**TAK — `SCHEDULER_TICK` generuje nadmierną liczbę wpisów** w Monitorze KSeF w trybie produkcyjnym. Przy domyślnym cronie 2×/doba realna wartość operacyjna to 2 enqueue; reszta to szum diagnostyczny.

### Propozycje ograniczenia (bez implementacji)

1. **Nie zapisywać `SCHEDULER_TICK` do Monitora** — tylko `logger.debug` w procesie workera.
2. **Logować do Monitora wyłącznie zdarzenia semantyczne:** `SCHEDULER_STARTED`, `SCHEDULER_SLOT`, `SCHEDULER_ENQUEUE`, `SCHEDULER_RECOVERY`, `SCHEDULER_DISABLED`, `SCHEDULER_INVALID_CRON` (nowy typ).
3. **`SCHEDULER_SKIP_ALREADY_EXECUTED` — max 1× na slot**, nie co minutę (np. zapis w `state_json`: `last_skip_logged_slot`).
4. **Heartbeat w Monitorze** co 6–24 h zamiast co minutę (operacyjna widoczność „scheduler żyje”).
5. **Rozszerzyć `_ALLOWED_METADATA_KEYS`** o `cron`, `slot`, `reason`, `job_id` — obecnie metadane schedulera są obcinane przy zapisie.

Rekomendacja operacyjna: **punkt 1 + 2** — największa redukcja szumu przy zachowaniu audytu enqueue/recovery.

---

## 3. Weryfikacja parsera cron

### Obsługiwany format

5 pól: `minute hour * * *`  
Minute/hour: `*`, `*/n`, `a,b,c`, `a-b`.

### Testy odrzucenia (wykonane lokalnie)

| Wyrażenie | Wynik |
|-----------|-------|
| `0 8,14 * * *` | ✅ OK |
| `0 8 * * 1` | ❌ `day/month/dow must be '*'` |
| `0 8 1 * *` | ❌ j.w. |
| `0 8 * 1 *` | ❌ j.w. |
| `bad` | ❌ `expected 5 fields` |
| `0 8 * *` | ❌ `expected 5 fields` |
| `60 8 * * *` | ❌ `out of range: 60` |
| `0 25 * * *` | ❌ `out of range: 25` |
| `*/0 8 * * *` | ❌ `Invalid step` |
| `0 8-6 * * *` | ❌ `Invalid range` |
| `0 abc * * *` | ❌ `invalid literal for int()` |

`evaluate_tick()` mapuje błędy na `reason=invalid_cron:<msg>` i **nie enqueue'uje**.

### Luka observability

W `__main__.py` dla `should_enqueue=False` logowane są tylko:
- `disabled` → `SCHEDULER_DISABLED`
- `already_executed` → `SCHEDULER_SKIP_ALREADY_EXECUTED`

Dla `invalid_cron:*` i `no_due_slot`:
- enqueue **nie następuje** ✅
- w Monitorze zostaje wyłącznie ogólny `SCHEDULER_TICK` (bez `reason` w metadanych — `cron` jest odfiltrowywane) ⚠️
- brak wpisu w `logger` aplikacji (tylko `logger.exception` przy wyjątku całego ticka)

### Werdykt punktu 3

| Aspekt | Status |
|--------|--------|
| Jednoznaczne odrzucenie nieobsługiwanych wyrażeń | ✅ Tak (`ValueError` / `invalid_cron`) |
| Brak enqueue przy błędnym cron | ✅ Tak |
| Odpowiednie logowanie w Monitorze | ⚠️ **Niepełne** — brak dedykowanego zdarzenia dla `invalid_cron` |

Produkcja DS723+ ma `KSEF_AUTO_SYNC_CRON=0 8,14 * * *` — poprawne wyrażenie. Ryzyko realne przy przyszłej zmianie ENV bez wiedzy o ograniczeniach parsera.

---

## 4. Bezpieczeństwo przy dwóch równoległych workerach

### Architektura blokady

```python
state = session.execute(
    select(KSeFSyncStateORM)
    .where(KSeFSyncStateORM.scope == _SCHEDULER_SCOPE)
    .with_for_update()
).scalar_one_or_none()
```

- Scope: `ksef_purchase_auto_scheduler`
- Kolumna `scope` ma constraint **UNIQUE** (`ksef_sync_state.py`)
- Idempotencja: `state_json.last_executed_slot` (klucz `YYYY-MM-DDTHH:MM`)
- Commit atomowy: enqueue job + aktualizacja `last_executed_slot`

### Scenariusz: wiersz stanu już istnieje (steady state)

1. Worker A: `FOR UPDATE` — blokuje wiersz.
2. Worker B: czeka na lock.
3. A: `evaluate_tick` → enqueue → `last_executed_slot = slot` → commit.
4. B: dostaje lock, czyta zaktualizowany `last_executed_slot`, `evaluate_tick` → `already_executed` → brak enqueue.

**Podwójny enqueue wykluczony** — serializacja przez `FOR UPDATE` + check slotu.

### Scenariusz: cold start (brak wiersza)

`SELECT FOR UPDATE` na pustym wyniku **nie blokuje** w PostgreSQL.

1. Oba workery mogą zobaczyć `state is None`.
2. Oba próbują `INSERT` — **UNIQUE na `scope`** powoduje `IntegrityError` u drugiego.
3. Drugi worker: `rollback` + `logger.exception("KSeF scheduler tick failed.")`.
4. Pierwszy kończy tick normalnie.

**Podwójny enqueue przy cold start: wykluczony** (jeden wiersz, jeden lock holder).  
**Efekt uboczny:** jednorazowy błąd w logach workera przy równoległym starcie dwóch instancji.

### Scenariusz produkcyjny

`docker-compose.prod.yml` — **1 kontener `worker`**, bez `deploy.replicas`. Ryzyko dual-worker w prod jest niskie operacyjnie, ale kod musi być bezpieczny przy skalowaniu.

### Werdykt punktu 4

| Ryzyko | Mitigacja | Ocena |
|--------|-----------|-------|
| Podwójny enqueue (steady state) | `FOR UPDATE` + `last_executed_slot` | ✅ Wyeliminowane |
| Podwójny enqueue (cold start) | UNIQUE `scope` | ✅ Wyeliminowane |
| Szum logów przy cold start 2 workerów | IntegrityError | ⚠️ Akceptowalne, ale brzydkie |
| Test automatyczny dual-worker PG | — | ❌ Brak |

**Rekomendacja operacyjna:** utrzymać **jedną** instancję workera z schedulerem włączonym; ewentualne drugie instancje — z `KSEF_AUTO_SYNC_ENABLED=false` lub wydzielonym trybem „job-only worker”.

---

## 5. Gotowość do wdrożenia

### Ocena: **7 / 10**

| Kryterium | Waga | Ocena | Uzasadnienie |
|-----------|------|-------|--------------|
| Poprawność logiki schedulera | Wysoka | 9/10 | Testy 34/34 KSeF, idempotencja, recovery |
| Integracja z workerem | Wysoka | 8/10 | Enqueue only, bez nowych procesów/migracji |
| Bezpieczeństwo współbieżności | Wysoka | 8/10 | `FOR UPDATE` + UNIQUE; brak testu integracyjnego 2 workerów |
| Observability / Monitor | Średnia | 5/10 | TICK co minutę = szum; słabe logowanie `invalid_cron` |
| Testy regresji repo | Średnia | 6/10 | 12 failów niezwiązanych ze schedulerem |
| Gotowość operacyjna prod | Średnia | 7/10 | ENV już ustawione na DS723+, kod nie wdrożony |
| Ryzyko rollbacku | Niska | 9/10 | Brak migracji; wyłączenie przez `KSEF_AUTO_SYNC_ENABLED=false` |

### Uzasadnienie skali 7/10

**Za wdrożeniem (+):**
- Scheduler wypełnia lukę z audytu (auto-sync ENV bez runtime).
- Brak nowych zależności i migracji DB.
- Pakiet testów KSeF scheduler+sync: **34 passed**.
- Produkcja ma jednego workera i poprawny cron `0 8,14 * * *`.
- Mechanizm enqueue jest zgodny z istniejącą kolejką `background_jobs`.

**Przeciw / ograniczenia (−):**
- `SCHEDULER_TICK` zanieczyszcza Monitor (~3k wpisów/dzień/worker).
- Brak jawnego logu `invalid_cron` w Monitorze.
- Brak testu integracyjnego podwójnego workera na PostgreSQL.
- Pełny `pytest` nie jest zielony (choć nie przez scheduler).
- Kod nie był jeszcze weryfikowany end-to-end na DS723+ po deployu schedulera.

**Nie blokuje deployu**, ale przed produkcją warto zaakceptować szum logów lub zaplanować szybką iterację redukcji TICK (punkt 2).

---

## A. ROOT CAUSE (podsumowanie ryzyk)

1. **Szum Monitora:** projektowa decyzja logowania każdego ticka do `transmissions`, nie do `logger` only.
2. **Słabe logowanie błędnego cron:** gałąź `invalid_cron` w `evaluate_tick` nie ma dedykowanego handlera w `__main__.py`.
3. **12 failów pytest:** historyczne regresje invoice/guardian, nie regresja schedulera.
4. **Dual-worker:** teoretycznie bezpieczne dzięki DB lock + UNIQUE; cold start może dać jednorazowy IntegrityError.

## B. ZMIENIONE PLIKI (zakres schedulera — bez edycji w tym przeglądzie)

- `app/worker/ksef_auto_sync_scheduler.py`
- `app/worker/__main__.py`
- `app/domain/enums.py`
- `app/worker/job_handlers/sync_purchase_invoices.py`
- `tests/unit/test_ksef_auto_sync_scheduler.py`
- `docs/architecture/KSEF_SCHEDULER.md`

## C. DEPLOY

**Nie wykonano** — zgodnie z wymaganiem.

Przed faktycznym deployem zalecane:
1. `python scripts/guardian.py` (zgodnie z regułami IFG Guardian).
2. Deploy workera z nowym kodem schedulera.
3. Restart workera (bez migracji).
4. Weryfikacja w Monitorze: po restarcie `SCHEDULER_STARTED`, o 08:00/14:00 `SCHEDULER_ENQUEUE` + job `sync_purchase_invoices`.

```bash
# Po deployu — ręczna weryfikacja (przykład)
docker compose -f docker/docker-compose.prod.yml logs worker --since 5m | grep -i scheduler
```

## D. TESTY (dowód z przeglądu)

```text
# Pakiet schedulera + KSeF sync
PYTHONPATH=scripts pytest tests/unit/test_ksef_auto_sync_scheduler.py \
  tests/unit/test_ksef_purchase_sync_resume.py \
  tests/unit/test_ksef_sync_service.py \
  tests/unit/test_ksef_sync_api.py
→ 34 passed

# Pełny zestaw (12 failów — poza schedulerem)
PYTHONPATH=scripts pytest
→ 12 failed, 1428 passed
```

## E. NASTĘPNY KROK

1. **Deploy workera** z implementacją schedulera (bez migracji).
2. **Monitorować** pierwszy cykl 08:00 / 14:00 — oczekiwane: `SCHEDULER_ENQUEUE` + wykonanie joba sync.
3. **Opcjonalnie przed/po deployu:** redukcja logowania `SCHEDULER_TICK` (propozycje w sekcji 2).
4. **Opcjonalnie:** dodać `SCHEDULER_INVALID_CRON` przy błędnym ENV cron.

---

*Przegląd wykonano: 2026-07-07. Bez zmian kodu, bez deployu, bez migracji.*
