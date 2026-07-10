# KSEF_TRANSMISSIONS_UNIFIED_JOURNAL_PLAN

## Cel

Przekształcić istniejący moduł `Transmisje KSeF` w centralny dziennik komunikacji KSeF **bez tworzenia nowej tabeli** (`ksef_operation_logs`), przez rozszerzenie obecnej tabeli `transmissions`.

---

## 1) Analiza obecnego użycia `transmissions`

## Model ORM i schema

- `app/persistence/models/transmission.py`
  - `invoice_id` jest obecnie **required** (`nullable=False`) i FK do `invoices`.
  - Tabela jest historycznie modelowana pod submit sprzedaży.
  - Już istnieje `operation_type`, ale praktycznie używany głównie jako `"submit"` / `"invoice_submit"`.
- Migracje:
  - `alembic/versions/0001_6462f591b285_initial_schema.py` - bazowa tabela `transmissions`.
  - `alembic/versions/0004_c3d4e5f6a7b8_transmission_upo.py` - `upo_xml`, `upo_status`.
  - `alembic/versions/0007_f6a7b8c9d0e1_ksef_hardening.py` - unique `idempotency_key`.
  - `alembic/versions/0013_m3n4o5p6q7r8_transmission_xml_content.py` - `xml_content`.

## Repository

- `app/persistence/repositories/transmission_repository.py`
  - Kluczowe metody zakładają flow fakturowy: `list_for_invoice`, `get_active_for_invoice`.
  - `list_all_paginated` jest dziś źródłem dashboardu.
  - Brak filtrów po typie operacji/korelacji/job.

## Serwisy i workery

- `app/services/transmission_service.py`
  - Tworzy wpisy transmisji przy submit/retry sprzedaży.
  - Nie obsługuje centralnego logowania zdarzeń sesyjnych/sync zakupów.
- `app/worker/job_handlers/submit_invoice.py`
  - Aktualizuje statusy submit flow i retry.
- `app/worker/job_handlers/poll_ksef_status.py`
  - Aktualizuje statusy końcowe + pobiera UPO.
- `app/services/ksef_session_service.py`
  - Session open/close zapisuje do `audit_logs`, nie do `transmissions`.
  - Sync zakupów zapisuje w `ksef_sync_states`, `background_jobs`, logach aplikacyjnych.
- `app/worker/job_handlers/sync_purchase_invoices.py`
  - Obsługuje 429 defer/resume w job payload i logach.
  - Brak wpisów do `transmissions` dla operacji sync-level.

## API

- `app/api/routers/transmissions.py`
  - Endpointy listują i zwracają wpisy transmission-centric.
  - Brak dedykowanych filtrów journalowych.
- `app/api/routers/ksef_session.py`
  - Manual sync/session API nie zapisuje do `transmissions`.

## Frontend

- `frontend-react/src/components/dashboard/TransmissionTable.jsx`
  - Widok jest dostosowany do wysyłki sprzedaży (`nr faktury`, status, retry, ref KSeF, błąd).
  - Brak kolumn operacyjnych (`operation_type`, `correlation_id`, `job_id`, metadata).
- `frontend-react/src/api/transmissions.js`
  - Proste listowanie paginowane bez filtrów typu operacji.

## Dlaczego obecnie dominują transmisje sprzedaży

Bo tylko flow submit/poll/upo konsekwentnie zapisuje i aktualizuje rekordy w `transmissions`; sesje i sync zakupów są logowane poza tą tabelą.

---

## 2) Bezpieczna migracja schematu (bez nowej tabeli)

## Docelowe zmiany kolumn

W `transmissions`:

1. `invoice_id` -> `nullable=True` (zachować FK).
2. `operation_type` -> zachować kolumnę, dodać spójny słownik enum (warstwa aplikacji).
3. Dodać `correlation_id` (`String(128)`, `nullable=False` po backfillu, indeks).
4. Dodać `job_id` (`UUID`, `nullable=True`, indeks).
5. Dodać `sync_id` (`String(128)` lub `UUID`, `nullable=True`, indeks).
6. Dodać `metadata_json` (`JSONB`, `nullable=True`).

## Kolejność migracji (2-etapowo)

### Migracja A (expand, bezpieczna):
- dodać nowe kolumny jako nullable,
- zostawić `invoice_id` jeszcze bez zmiany constraintu,
- dodać indeksy (`correlation_id`, `job_id`, `sync_id`, opcj. composite po `created_at`).

### Backfill danych:
- `operation_type`:
  - jeśli null/puste -> `SALE_SEND`.
- `correlation_id`:
  - jeśli `invoice_id` istnieje -> `inv:<invoice_id>`,
  - w przeciwnym razie -> `tx:<transmission.id>`.
- `metadata_json` domyślnie null (bez sztucznego fillu).

### Migracja B (contract):
- zmienić `invoice_id` na nullable,
- ustawić `correlation_id` jako non-null,
- opcjonalnie check constraint: `length(correlation_id) > 0`.

Ta sekwencja minimalizuje ryzyko locków i regresji podczas migracji danych.

---

## 3) Proponowany enum `operation_type`

Minimalny wymagany zestaw:

- `SALE_SEND`
- `SALE_STATUS`
- `UPO_DOWNLOAD`
- `SESSION_OPEN`
- `SESSION_CLOSE`
- `PURCHASE_SYNC_MANUAL`
- `PURCHASE_SYNC_AUTO`
- `PURCHASE_METADATA_FETCH`
- `PURCHASE_INVOICE_FETCH`
- `RETRY`
- `RESUME`
- `ERROR`

Rekomendacja dodatkowa (opcjonalna):
- `PURCHASE_SYNC_SUMMARY` (agregat końca joba),
- `SESSION_STATUS_CHECK` (jeśli chcemy ślad probe/health).

---

## 4) Strategia dla istniejących rekordów

1. `operation_type`:
   - brak/niejednoznaczne -> `SALE_SEND`.
2. `correlation_id`:
   - preferencja `inv:<invoice_id>`, fallback `tx:<id>`.
3. Zachować wszystkie obecne wpisy i statusy.
4. Nie zmieniać mechaniki submit/poll sprzedaży poza dodaniem uzupełniającego logowania typów.

Wpływ na flow sprzedaży: neutralny, jeśli:
- nie zmienimy semantyki istniejących statusów,
- nie usuniemy pól obecnie używanych przez API/FE,
- zachowamy backward-compatible odpowiedzi API.

---

## 5) Warstwa serwisowa (bez duplikacji)

## Rekomendacja: `KsefTransmissionJournalService`

Nowy serwis aplikacyjny oparty o istniejące repo `TransmissionRepository`, z metodą:

- `log_event(...)`:
  - `operation_type`
  - `status`
  - `short_description`
  - `invoice_id?`
  - `ksef_reference_number?`
  - `job_id?`
  - `sync_id?`
  - `correlation_id?` (auto-wyliczenie jeśli brak)
  - `error_message?`
  - `metadata_json?`

Implementacja:
- Tworzy nowy rekord `TransmissionORM` dla eventów dziennika.
- Dla flow submit/poll może:
  - albo aktualizować istniejący rekord transmisji biznesowej,
  - albo dopisywać wpis journalowy (preferowane dla pełnego timeline).

Minimalizacja duplikacji:
- jeden helper mapujący status/opis/metadata,
- cienkie wywołania w serwisach i workerach.

---

## 6) Konkretne miejsca instrumentacji

1. **Submit faktury sprzedaży**
   - `app/services/transmission_service.py`
   - log: `SALE_SEND` (`queued`), `RETRY` (manual retry), `ERROR` gdy walidacja blokuje.

2. **Polling statusu/UPO**
   - `app/worker/job_handlers/poll_ksef_status.py`
   - log: `SALE_STATUS` (status transitions), `UPO_DOWNLOAD` (`fetched`/`failed`), `ERROR`.

3. **Open/close session**
   - `app/services/ksef_session_service.py`
   - log: `SESSION_OPEN`, `SESSION_CLOSE`, ew. `ERROR`.

4. **Manual sync zakupów**
   - `app/api/routers/ksef_session.py` + `KSeFSessionService.sync_purchase_invoices`
   - log: `PURCHASE_SYNC_MANUAL` (`started`, `success`, `failed`, `deferred`).

5. **Async worker sync zakupów**
   - `app/worker/job_handlers/sync_purchase_invoices.py`
   - log: `PURCHASE_SYNC_AUTO` (dla schedulera), `PURCHASE_SYNC_MANUAL` (dla UI-trigger async), plus wynik.

6. **429 retry/resume**
   - `sync_purchase_invoices.py` + worker main (`JobRateLimitDeferredError` handling)
   - log: `RETRY` (defer), `RESUME` (wznowienie), `ERROR` (gdy limit utrzymuje się lub inne błędy).

7. **Pobranie pojedynczej faktury zakupu**
   - `_process_purchase_invoice_xml` w `KSeFSessionService`
   - log: `PURCHASE_INVOICE_FETCH` (`saved` / `skipped_existing` / `skipped_parse`), z `ksef_reference_number`.

8. **Pobranie metadata zakupów**
   - `_sync_received_invoices_incremental` / `query_purchase_metadata_refs`
   - log: `PURCHASE_METADATA_FETCH`.

---

## 7) Frontend - plan zmiany widoku na centralny dziennik

## Aktualny stan

- `TransmissionTable` pokazuje dane sprzedażowe (znacznik, nr faktury, status, próby, ref KSeF, błąd, retry button).

## Docelowy widok dziennika operacji

Kolumny:
- czas (`created_at`)
- typ operacji (`operation_type`)
- status
- opis (`short_description` z backendu lub fallback z metadata/status)
- numer faktury / `invoice_id` (jeśli istnieje)
- `ksef_reference_number`
- `job_id`
- `correlation_id`
- `error_message`

Dodatkowo:
- panel szczegółów (expand row) pokazujący `metadata_json` (pretty JSON),
- filtry po:
  - `operation_type`,
  - statusie,
  - zakresie dat,
  - `correlation_id`,
  - tylko błędy.

Kompatybilność:
- nie usuwać widoczności istniejących zdarzeń sprzedażowych;
- stare rekordy (`SALE_SEND`) nadal czytelne.

---

## 8) Testy wymagane

## Backend

1. **Migracja i backfill**
   - poprawne ustawienie `operation_type=SALE_SEND` dla legacy,
   - poprawny `correlation_id`,
   - `invoice_id` nullable działa.
2. **Repo/API**
   - listowanie rekordów bez `invoice_id`,
   - filtrowanie po `operation_type` i `correlation_id`.
3. **Journal service**
   - logowanie eventu bez faktury,
   - logowanie z `job_id`/`sync_id`/`metadata_json`.
4. **Flow sprzedaży**
   - brak regresji submit/retry/poll/upo.
5. **Sync/session flow**
   - `SESSION_OPEN/CLOSE`,
   - `PURCHASE_SYNC_MANUAL/AUTO`,
   - `RETRY/RESUME` przy 429.

## Frontend

1. Render nowej tabeli z nowymi polami.
2. Poprawny fallback dla rekordów legacy bez nowych pól.
3. Filtry i sortowanie po typie/czasie/statusie.
4. Szczegóły metadata (expand/collapse).
5. Brak regresji retry action dla sprzedażowych wpisów, jeśli nadal wspierane.

---

## Proponowana lista plików do zmiany

## Migracje / modele

- `alembic/versions/<new>_transmissions_unified_journal_expand.py`
- `alembic/versions/<new>_transmissions_unified_journal_backfill_contract.py`
- `app/persistence/models/transmission.py`
- `app/domain/enums.py` (enum operation type)
- `app/schemas/transmission.py`

## Repository / serwisy

- `app/persistence/repositories/transmission_repository.py`
- `app/services/transmission_service.py`
- `app/services/ksef_session_service.py`
- `app/worker/job_handlers/submit_invoice.py`
- `app/worker/job_handlers/poll_ksef_status.py`
- `app/worker/job_handlers/sync_purchase_invoices.py`
- `app/worker/__main__.py` (resume/defer instrumentation)
- **nowy** `app/services/ksef_transmission_journal_service.py`

## API

- `app/api/routers/transmissions.py`
- opcjonalnie `app/api/deps.py` (DI nowego serwisu)
- opcjonalnie `app/api/routers/ksef_session.py` (wzbogacone payloady)

## Frontend

- `frontend-react/src/api/transmissions.js`
- `frontend-react/src/components/dashboard/TransmissionTable.jsx`
- `frontend-react/src/components/dashboard/TransmissionTable.module.css`
- opcjonalnie `frontend-react/src/pages/advanced/AdvancedDashboard.jsx` (filtry/UX)

## Testy

- `tests/unit/test_transmission_service.py`
- `tests/unit/test_transmission_api.py`
- `tests/unit/test_submit_invoice_handler.py`
- `tests/unit/test_poll_ksef_status_handler.py`
- `tests/unit/test_ksef_purchase_sync_resume.py`
- `tests/unit/test_ksef_session_worker.py`
- **nowe** testy migracji/transmission journal (np. `tests/unit/test_transmission_journal_migration.py`)
- frontend: nowe testy komponentu TransmissionTable (brak obecnie dedykowanych testów)

---

## Plan implementacji (kolejność)

1. Dodać enum `operation_type` + migracje expand/backfill/contract.
2. Wprowadzić `KsefTransmissionJournalService` i podłączyć DI.
3. Zinstruować flow submit/poll/sesja/sync/429.
4. Rozszerzyć API listowania i payload response.
5. Przebudować `TransmissionTable` na centralny dziennik.
6. Dodać testy backend i frontend.
7. Uruchomić regresję kluczowych testów KSeF/transmission.

Ten plan spełnia wymaganie: centralny dziennik na bazie `transmissions` bez nowej tabeli.

