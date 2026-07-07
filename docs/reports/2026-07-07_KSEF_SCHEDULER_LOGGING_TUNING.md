# 2026-07-07_KSEF_SCHEDULER_LOGGING_TUNING

Ostatnia poprawka logowania schedulera KSeF przed deployem.  
Bez zmian logiki schedulera, recovery, idempotencji i enqueue. Bez deployu.

---

🩷 STATUS KOŃCOWY

✅ CO DZIAŁA
- `SCHEDULER_TICK` nie trafia już do Monitora KSeF — zastąpiony `logger.debug()`.
- `SCHEDULER_SKIP_ALREADY_EXECUTED` logowany max 1× na slot (`last_skip_logged_slot` w `state_json`).
- Nowy typ monitora `SCHEDULER_INVALID_CRON` przy odrzuceniu wyrażenia cron przez parser.
- Testy schedulera + KSeF sync: **34 passed**.

⚠️ ZNANE PROBLEMY
- Enum `SCHEDULER_TICK` pozostaje w `KSeFOperationType` (kompatybilność wsteczna ze starymi wpisami w `transmissions`).
- `SCHEDULER_INVALID_CRON` deduplikowany po wyrażeniu cron (`last_invalid_cron_logged`) — zapobiega szumowi przy stałym błędnym ENV; nie jest to zmiana logiki schedulera, tylko warstwy logowania.
- Metadane schedulera (`slot`, `cron`) nadal są częściowo obcinane przez `_ALLOWED_METADATA_KEYS` w journal service — poza zakresem tej poprawki.

❌ CO NIE DZIAŁA
- Deploy nie wykonany (zgodnie z wymaganiem).

---

## 1. Wykonane zmiany

### `app/worker/__main__.py`

| Przed | Po |
|-------|-----|
| `_scheduler_log_event(SCHEDULER_TICK)` co minutę | `logger.debug("KSeF scheduler tick cron=... tick_key=...")` |
| `SCHEDULER_SKIP_ALREADY_EXECUTED` co minutę przy `already_executed` | Log tylko gdy `last_skip_logged_slot != decision.slot_key`, potem zapis slotu |
| Brak obsługi `invalid_cron` w Monitorze | `SCHEDULER_INVALID_CRON` (WARNING) z komunikatem parsera |

### `app/domain/enums.py`

- Dodano `SCHEDULER_INVALID_CRON = "SCHEDULER_INVALID_CRON"`.

### Bez zmian

- `app/worker/ksef_auto_sync_scheduler.py` — parser, `evaluate_tick`, recovery, idempotencja.
- Ścieżka enqueue (`SCHEDULER_SLOT`, `SCHEDULER_RECOVERY`, `SCHEDULER_ENQUEUE`).
- `last_executed_slot` i mechanizm `FOR UPDATE`.

---

## 2. Szacowany wpływ na wolumen Monitora

Cron produkcyjny: `0 8,14 * * *`, 1 worker.

| Typ zdarzenia | Przed (wpisy/dzień) | Po (wpisy/dzień) |
|---------------|---------------------|------------------|
| `SCHEDULER_TICK` | ~1440 | **0** |
| `SCHEDULER_SKIP_ALREADY_EXECUTED` | ~1438 | **~2** (1× na slot 08:00 i 14:00) |
| `SCHEDULER_ENQUEUE` + `SCHEDULER_SLOT` | ~4 | ~4 (bez zmian) |
| `SCHEDULER_INVALID_CRON` | 0 | 0 przy poprawnym cron; 1 przy błędnym ENV |

**Redukcja:** z ~2880 do ~6 wpisów/dzień (poza recovery/disabled/started).

---

## 3. Zachowanie `SCHEDULER_INVALID_CRON`

Gdy `evaluate_tick()` zwraca `reason=invalid_cron:<msg>`:

1. Zapis do Monitora: `operation_type=SCHEDULER_INVALID_CRON`, `severity=WARNING`.
2. `short_description`: `Invalid scheduler cron: <msg>` (np. `Only minute/hour cron is supported...`).
3. Deduplikacja: wpis tylko gdy `last_invalid_cron_logged != KSEF_AUTO_SYNC_CRON` w `state_json`.
4. Enqueue **nie następuje** (bez zmian w logice decyzyjnej).

Przykładowe odrzucone wyrażenia (bez zmian w parserze):

- `0 8 * * 1` — day/month/dow muszą być `*`
- `bad` — oczekiwane 5 pól
- `60 8 * * *` — wartość poza zakresem

---

## 4. Zachowanie `SCHEDULER_SKIP_ALREADY_EXECUTED`

Pole `state_json.last_skip_logged_slot` przechowuje slot, dla którego już zalogowano skip.

- Pierwszy tick po wykonaniu slotu `2026-07-07T08:00` → 1 wpis SKIP.
- Kolejne ticki w tej samej minucie/slota → brak kolejnych wpisów SKIP.
- Nowy slot `2026-07-07T14:00` → ponownie 1 wpis SKIP (inny `slot_key`).

---

## A. ROOT CAUSE (dlaczego tuning)

Pre-deploy review wykazał ~2880 zbędnych wpisów/dzień z `SCHEDULER_TICK` + `SCHEDULER_SKIP_ALREADY_EXECUTED`, oraz brak widoczności błędnego cron w Monitorze.

## B. ZMIENIONE PLIKI

- `app/worker/__main__.py`
- `app/domain/enums.py`
- `docs/reports/2026-07-07_KSEF_SCHEDULER_LOGGING_TUNING.md` (ten raport)

## C. DEPLOY

**Nie wykonano.**

## D. TESTY

```bash
PYTHONPATH=scripts pytest \
  tests/unit/test_ksef_auto_sync_scheduler.py \
  tests/unit/test_ksef_purchase_sync_resume.py \
  tests/unit/test_ksef_sync_service.py \
  tests/unit/test_ksef_sync_api.py
```

Wynik: **34 passed in 0.47s**.

Logika `evaluate_tick` / `parse_minute_hour_cron` — bez zmian, wszystkie 9 testów schedulera przechodzą.

## E. NASTĘPNY KROK

1. Deploy workera z tuningiem logowania.
2. Po restarcie: w Monitorze oczekiwany `SCHEDULER_STARTED`, brak `SCHEDULER_TICK`.
3. O 08:00 / 14:00: `SCHEDULER_SLOT` + `SCHEDULER_ENQUEUE`.
4. Przy celowym błędnym `KSEF_AUTO_SYNC_CRON`: jeden wpis `SCHEDULER_INVALID_CRON`.

---

*Wykonano: 2026-07-07. Bez deployu, bez migracji.*
