# 2026-07-07_KSEF_SCHEDULER_IMPLEMENTATION

🩷 STATUS KOŃCOWY

✅ CO DZIAŁA
- Dodano kompletny mechanizm scheduler auto-sync jako część istniejącego workera (bez APScheduler/Celery/system cron).
- Scheduler działa w tym samym procesie co polling `background_jobs` i robi wyłącznie `enqueue(sync_purchase_invoices)`.
- Dodano idempotencję slotów oraz recovery pominiętego slotu (maksymalnie ostatni należny slot).
- Dodano telemetryczne wpisy do Monitora KSeF:
  - `SCHEDULER_STARTED`
  - `SCHEDULER_TICK`
  - `SCHEDULER_SLOT`
  - `SCHEDULER_ENQUEUE`
  - `SCHEDULER_SKIP_ALREADY_EXECUTED`
  - `SCHEDULER_RECOVERY`
  - `SCHEDULER_DISABLED`
- Dodano dokument architektury: `docs/architecture/KSEF_SCHEDULER.md`.

⚠️ ZNANE PROBLEMY
- Pełny `pytest` repo kończy się błędami niezwiązanymi z tym zakresem (historyczne/regresyjne moduły invoice/guardian).
- Implementacja scheduler cron wspiera 5 pól, ale aktywnie interpretuje minute/hour; day/month/dow muszą być `*`.

❌ CO NIE DZIAŁA
- Nie wszystkie testy całego repo przechodzą (lista w sekcji testów).

---

## 1. Wykonane zmiany

- Zaimplementowano moduł scheduler decyzyjny:
  - `app/worker/ksef_auto_sync_scheduler.py`
  - parser cron + ocena slotu + recovery + ochrona przed podwójnym uruchomieniem.
- Zintegrowano scheduler loop z workerem:
  - `app/worker/__main__.py`
  - tick co minutę (w ramach istniejącej pętli),
  - trwały stan slotu przez `ksef_sync_states` (`scope=ksef_purchase_auto_scheduler`),
  - enqueue `BackgroundJob(job_type="sync_purchase_invoices", incremental=true)`.
- Rozszerzono typy operacji KSeF dla Monitora:
  - `app/domain/enums.py`.
- Uelastyczniono handler joba sync zakupów:
  - `app/worker/job_handlers/sync_purchase_invoices.py`
  - obsługa payload z opcjonalnymi `date_from/date_to` i flagą `incremental`.
- Dodano testy scheduler:
  - `tests/unit/test_ksef_auto_sync_scheduler.py`.
- Dodano dokumentację architektury:
  - `docs/architecture/KSEF_SCHEDULER.md`.

---

## 2. Migracje

- Brak nowych migracji DB.
- Wykorzystano istniejącą tabelę `ksef_sync_states` do stanu schedulera.

---

## 3. Zmiany backend

- Scheduler uruchamia się automatycznie razem z workerem (bez osobnego procesu).
- Scheduler nie wykonuje syncu bezpośrednio; jedynie enqueue job do istniejącej kolejki.
- Worker i dotychczasowe handlery pozostają główną ścieżką wykonania logiki synchronizacji.

---

## 4. Zmiany ENV

- Brak nowych zmiennych ENV.
- Wykorzystane istniejące:
  - `KSEF_AUTO_SYNC_ENABLED`
  - `KSEF_AUTO_SYNC_CRON`

---

## 5. Testy

### Testy celowane (scheduler + KSeF sync)
- `PYTHONPATH=scripts pytest tests/unit/test_ksef_auto_sync_scheduler.py tests/unit/test_ksef_purchase_sync_resume.py tests/unit/test_ksef_sync_service.py tests/unit/test_ksef_sync_api.py`
- Wynik: **34 passed**.

### Pełny zestaw testów
- `PYTHONPATH=scripts pytest`
- Wynik: **12 failed, 1428 passed**.
- Niezaliczone testy (istniejące, poza zakresem tej implementacji):
  - `tests/guardian_platform/test_regression.py::TestLegacyGuardianRegression::test_legacy_tests_still_pass`
  - `tests/unit/test_guardian_plugins_sprint2.py::TestIFGPlugin::test_workflows_contains_all_ifg_workflows`
  - `tests/unit/test_domain_invoice.py::TestValidateForKSeF::test_sale_requires_number_local_before_send`
  - `tests/unit/test_invoice_api.py::TestInvoicePdf::*` (3 testy)
  - `tests/unit/test_invoice_numbering_regression.py::*` (3 testy)
  - `tests/unit/test_invoice_transitions.py::*` (2 testy)
  - `tests/unit/test_transaction_hardening.py::TestInvoiceNumberSequential::test_same_invoice_mark_ready_idempotent_via_status_guard`

---

## 6. Wpływ na produkcję

- Niski/średni wpływ architektony: zmiana dotyczy wyłącznie workera i enqueue jobów.
- Brak nowych zewnętrznych zależności i brak dodatkowych procesów.
- Zgodność z istniejącym modelem IFG (worker + background_jobs + Monitor KSeF).

---

## 7. Ryzyka

- Jeśli w środowisku uruchomionych będzie wiele instancji workera, scheduler opiera się na stanie DB; użyto blokady `FOR UPDATE` na rekordzie scope, ale zalecana operacyjnie jest pojedyncza instancja scheduler-enabled worker.
- Zły format cron (day/month/dow różne od `*`) skutkuje pominięciem enqueue i wpisem diagnostycznym.
- Tick co minutę dodaje wpisy monitorujące (`SCHEDULER_TICK`), co zwiększa wolumen logów transmisji.

---

## 8. Deploy

- Zgodnie z wymaganiem: **nie wykonywano deployu na DS723+**.
