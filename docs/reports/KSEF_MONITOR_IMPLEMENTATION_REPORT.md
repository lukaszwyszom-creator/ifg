# KSEF_MONITOR_IMPLEMENTATION_REPORT

🩷 STATUS KOŃCOWY

## ✅ CO DZIAŁA

- Zmieniono nazwę UI zakładki na **„Monitor KSeF”**.
- Rozszerzono istniejącą tabelę `transmissions` (bez nowej tabeli) o:
  - `severity`,
  - `correlation_id` (UUID),
  - `job_id`,
  - `metadata_json`.
- Przygotowano migrację z backfillem:
  - `invoice_id` -> nullable,
  - `idempotency_key` -> nullable (dla eventów bez submit),
  - `operation_type` legacy -> `SALE_SEND`,
  - `correlation_id` legacy -> `COALESCE(invoice_id, id)`.
- Dodano enumy domenowe:
  - `KSeFOperationType` (wymagany zestaw + `PURCHASE_IMPORT_SUMMARY`),
  - `KSeFSeverity` (`INFO`, `SUCCESS`, `WARNING`, `ERROR`, `RUNNING`, `PAUSED`).
- Wdrożono centralny serwis logowania zdarzeń:
  - `KSeFTransmissionJournalService` z kontrolowanym schematem `metadata_json`.
- Zinstruowano kluczowe przepływy:
  - submit/retry sprzedaży,
  - polling statusu/UPO,
  - open/close/expired sesji,
  - manual/auto sync zakupów,
  - 429 defer (`RETRY`) i resume (`RESUME`),
  - metadata fetch + invoice fetch + import summary.
- Frontend `TransmissionTable` został rozszerzony do roli **Monitora KSeF**:
  - badge typu operacji,
  - kolor/severity badge,
  - filtr „Tylko błędy i ostrzeżenia”,
  - liczniki (`sukcesy/ostrzeżenia/błędy/w toku`),
  - rozwijane szczegóły `metadata_json`,
  - zachowana kompatybilność wpisów sprzedażowych.
- Dodano konfigurację auto-sync przez ENV:
  - `KSEF_AUTO_SYNC_ENABLED`,
  - `KSEF_AUTO_SYNC_CRON`.

## ⚠️ ZNANE PROBLEMY

- Harmonogram cron 2x dziennie został przygotowany konfiguracyjnie (ENV), ale sam scheduler nie był częścią tego zakresu i nie został uruchomiony.
- API listy transmisji ma obecnie podstawowy filtr `warnings_or_errors_only`; pełna filtracja po typie/correlation/job może być rozwinięta w kolejnym kroku.
- Klasa CSS `running/paused` opiera się na istniejącym `neutral` badge (czytelne, ale można dopracować wizualnie).

## ❌ CO NIE DZIAŁA

- Brak wdrożenia/deployu na DS723+ (zgodnie z wymaganiem).

---

## A. ROOT CAUSE

Stary moduł „Transmisje KSeF” był technicznie sprzężony z flow wysyłki sprzedaży (`invoice_id` required, statusy submit/poll), przez co zdarzenia sesji i sync zakupów były logowane poza tabelą `transmissions`. To powodowało niepełny obraz operacji KSeF w UI.

---

## B. ZMIENIONE PLIKI

- `alembic/versions/a9b1c2d3e4f5_ksef_monitor_transmissions_unified.py`
- `app/domain/enums.py`
- `app/persistence/models/transmission.py`
- `app/services/ksef_transmission_journal_service.py`
- `app/api/deps.py`
- `app/services/transmission_service.py`
- `app/services/ksef_session_service.py`
- `app/worker/__main__.py`
- `app/worker/job_handlers/submit_invoice.py`
- `app/worker/job_handlers/poll_ksef_status.py`
- `app/schemas/transmission.py`
- `app/api/routers/transmissions.py`
- `app/core/config.py`
- `frontend-react/src/pages/advanced/AdvancedDashboard.jsx`
- `frontend-react/src/api/transmissions.js`
- `frontend-react/src/components/dashboard/TransmissionTable.jsx`
- `frontend-react/src/components/dashboard/TransmissionTable.module.css`
- `frontend-react/src/components/common/StatusBadge.jsx`
- `tests/unit/test_transmission_api.py`

---

## C. DEPLOY

- Nie wykonano deployu.
- Nie wykonano zmian na DS723+.

---

## D. TESTY

Uruchomiono testy backendowe adekwatne do zmian:

```bash
python3 -m pytest \
  tests/unit/test_transmission_service.py \
  tests/unit/test_transmission_api.py \
  tests/unit/test_submit_invoice_handler.py \
  tests/unit/test_poll_ksef_status_handler.py \
  tests/unit/test_ksef_purchase_sync_resume.py -q
```

Wynik:
- **84 passed**

Uruchomiono build frontendu:

```bash
cd frontend-react && npm run build
```

Wynik:
- **build success (vite)**.

---

## E. NASTĘPNY KROK

1. Dodać rozszerzone filtry API/FE (`operation_type`, `correlation_id`, `job_id`, zakres dat).
2. Dodać testy migracji DB (backfill `correlation_id` i `operation_type`).
3. Dodać testy frontendowe komponentu Monitor KSeF (filtry/liczniki/metadata expand).
4. Po akceptacji: przygotować osobny krok deployu.

