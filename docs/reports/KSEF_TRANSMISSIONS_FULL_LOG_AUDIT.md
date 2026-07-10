# KSEF_TRANSMISSIONS_FULL_LOG_AUDIT

## Cel i zakres

Audit modułu `Transmisje KSeF` w IFG, z odpowiedzią:

1. Dlaczego dziś widać głównie wysyłkę faktur sprzedaży.
2. Gdzie backend zapisuje logi sesji/sync/błędów/retry/resume.
3. Jak rozszerzyć moduł do pełnego dziennika operacji KSeF.

Zakres: analiza kodu backend + frontend, bez zmian runtime i bez deployu.

## Stan obecny - dlaczego widać głównie sprzedaż

### 1) Tabela `transmissions` jest zdefiniowana pod wysyłkę faktur

Model `TransmissionORM` ma:
- obowiązkowe `invoice_id` (FK do `invoices`),
- statusy procesu submit/poll (`queued`, `processing`, `submitted`, `waiting_status`, `success`, ...),
- pola specyficzne dla wysyłki/UPO (`xml_content`, `upo_xml`, `upo_status`, `ksef_reference_number`).

To naturalnie faworyzuje flow sprzedażowy "submit invoice -> poll -> UPO".

### 2) Tworzenie wpisów `transmissions` odbywa się praktycznie w `TransmissionService.submit_invoice()`

`TransmissionService` tworzy rekord transmisji dla wysyłki faktury sprzedaży i retry.
Następnie worker (`submit_invoice`, `poll_ksef_status`) aktualizuje ten sam rekord.

Skutek: dashboard "Transmisje KSeF" pokazuje przede wszystkim zdarzenia tej ścieżki.

### 3) Operacje zakupowe i sesyjne są logowane gdzie indziej

- Sesje KSeF (`open_session`, `close_session`) -> `audit_logs` przez `AuditService` (`ksef_session.opened`, `ksef_session.closed`).
- Sync zakupów manualny/async, 429, resume -> głównie logi aplikacyjne (`logger.info/error`), `background_jobs.payload_json`, `ksef_sync_states`.
- Import pojedynczych faktur zakupowych nie tworzy wpisu w `transmissions`.

Wniosek: to nie brak danych o KSeF, tylko brak centralnego, wspólnego storage dla "journal view".

## Gdzie dziś zapisywane są wymagane logi

| Obszar | Aktualny zapis | Czy widoczne w `Transmisje KSeF` |
|---|---|---|
| Otwarcie sesji KSeF | `audit_logs` (`event_type=ksef_session.opened`) | NIE |
| Zamknięcie sesji KSeF | `audit_logs` (`event_type=ksef_session.closed`) | NIE |
| Ręczna synchronizacja zakupów | logi aplikacyjne + `ksef_sync_states` + job async | NIE |
| Automatyczna synchronizacja zakupów | logi workera + `background_jobs` + `ksef_sync_states` | NIE |
| Pobrane faktury zakupu | zapis do `invoices` (`direction=purchase`) + logi audit sync | NIE |
| Błędy KSeF (submit/poll) | częściowo `transmissions.error_*`, częściowo logi worker/session/sync | CZĘŚCIOWO |
| Retry / resume po 429 | job payload (`resume`), `available_at`, logi `KSEF_ASYNC_SYNC_*` | NIE |

## Wnioski architektoniczne

1. `transmissions` to dziś "journal wysyłki sprzedaży", nie "journal KSeF".
2. Dane o pozostałych operacjach istnieją, ale są rozproszone i niespójne dla UI.
3. Brakuje jednego modelu zdarzeń KSeF, który łączy:
   - submit/poll/upo (sprzedaż),
   - session lifecycle,
   - purchase sync (manual/auto),
   - 429 deferral + resume,
   - błędy i recovery.

## Projekt rozszerzenia - pełny dziennik operacji KSeF

## Założenia

- Nie usuwać obecnych wpisów sprzedażowych.
- Zachować kompatybilność endpointu listowania transmisji.
- Dodać semantyczny typ operacji i pola kontekstowe.
- Umożliwić przyszły harmonogram auto-sync 2x/dzień.

## Proponowany model danych

### Opcja rekomendowana: nowa tabela `ksef_operation_logs`

Oddzielić dziennik operacji od stricte "transmission transport".

Proponowane pola:
- `id` UUID
- `created_at` (czas zdarzenia)
- `operation_type` enum/string:
  - `sale_send`
  - `upo_fetch`
  - `session_open`
  - `session_close`
  - `purchase_sync_manual`
  - `purchase_sync_auto`
  - `purchase_invoice_fetch`
  - `error`
  - `retry`
  - `resume`
- `status` enum/string (`started`, `success`, `failed`, `deferred`, `resumed`, ...)
- `short_description` text (krótki opis do UI)
- `invoice_id` nullable
- `ksef_reference_number` nullable
- `job_id` nullable
- `error_message` nullable
- `metadata_json` (szerszy kontekst: nip, zakres dat, retry_after_seconds, current_offset, source=manual/auto, itp.)

Dlaczego osobna tabela:
- obecna `transmissions.invoice_id` jest obowiązkowa, więc nie pasuje do eventów sesji i sync-level,
- nie ryzykujemy regresji istniejącej logiki submit/poll.

### Alternatywa (mniej zalecana): przebudować `transmissions`

Wymagałoby m.in.:
- `invoice_id` -> nullable,
- większych zmian semantyki i migracji kodu workerów/API/FE.

To podnosi ryzyko regresji istniejącej ścieżki sprzedaży.

## Mapa źródeł eventów -> nowe wpisy dziennika

1. `TransmissionService.submit_invoice()`:
   - `sale_send` (`started` / `queued`)
   - `retry` przy ręcznym ponowieniu
2. `SubmitInvoiceJobHandler`:
   - `sale_send` (`success`/`failed`)
   - `error` przy błędach mapowania/sesji/KSeF
3. `PollKSeFStatusJobHandler`:
   - `upo_fetch` (`success`/`failed`)
4. `KSeFSessionService.open_session()/close_session()`:
   - `session_open`, `session_close`
5. `sync_purchase_invoices` (manual endpoint):
   - `purchase_sync_manual` (`started`/`success`/`failed`/`deferred`)
6. async worker `sync_purchase_invoices`:
   - `purchase_sync_auto` dla trybu harmonogramu
   - `retry`/`resume` przy 429 + defer
7. import pojedynczej faktury zakupu:
   - `purchase_invoice_fetch` (na każdą pobraną lub agregowane paczką)

## API i backend

1. Dodać repo + serwis dziennika:
   - `KSeFOperationLogRepository`
   - `KSeFOperationLogService.log(...)`
2. Instrumentacja punktów krytycznych (jak wyżej).
3. Dodać endpoint listowania dziennika:
   - np. `GET /ksef/operations?types=&status=&from=&to=&page=&size=`
4. Opcjonalnie zostawić `GET /transmissions/` jako legacy lub rozszerzyć odpowiedź o pola unified-log.

## Frontend - docelowy widok "pełny dziennik"

W `TransmissionTable`/nowym komponencie:
- kolumny:
  - czas
  - typ operacji (badge)
  - status
  - opis
  - invoice_id / nr faktury (jeśli jest)
  - ksef_reference_number
  - job_id
  - error_message (skracane + tooltip)
- filtry:
  - typ operacji
  - status
  - zakres czasu
  - tylko błędy
- grupowanie opcjonalne po `job_id` dla sync batch.

Ważne: nie usuwać obecnego kontekstu sprzedaży - pokazać go jako jeden z typów (`sale_send`, `upo_fetch`).

## Harmonogram auto-sync 2x dziennie - gotowość modelu

Aby obsłużyć plan "2 razy dziennie":
- każde wywołanie harmonogramu loguje `purchase_sync_auto started`,
- po zakończeniu: `success` lub `deferred`/`failed`,
- przy 429:
  - `retry` z `retry_after_seconds`,
  - `resume` po wznowieniu z `job_id` i `offset`.

To da pełną oś zdarzeń niezależnie od tego, czy sync uruchomił operator czy scheduler.

## Plan wdrożenia (bez deployu w tym kroku)

### Etap 1 - model i zapis
- migracja DB: `ksef_operation_logs`,
- serwis logowania + instrumentacja punktów backend.

### Etap 2 - API
- endpoint listowania + filtrowanie/paginacja.

### Etap 3 - frontend
- nowy widok dziennika (lub refactor `TransmissionTable`) oparty o operation logs.

### Etap 4 - kompatybilność i testy
- testy jednostkowe i integracyjne:
  - sale send,
  - session open/close,
  - purchase sync manual/auto,
  - 429 defer/retry/resume,
  - import faktur zakupu.

## Odpowiedzi na pytania z zadania (jednoznacznie)

1. Dlaczego głównie wysyłka sprzedaży?
   - Bo `transmissions` i UI są zbudowane pod submit/poll sprzedaży; inne operacje KSeF nie zapisują się do tej tabeli.

2. Czy backend zapisuje logi wymaganych obszarów?
   - Tak, ale rozproszone:
     - sesje -> `audit_logs`,
     - sync/retry/resume -> logi aplikacyjne + `background_jobs` + `ksef_sync_states`,
     - błędy submit/poll -> częściowo `transmissions`.
   - Nie ma jednego pełnego dziennika dostępnego dla obecnego modułu UI.

3. Jak zrobić pełny dziennik "Transmisje KSeF"?
   - Wprowadzić dedykowany model `ksef_operation_logs` z `operation_type`, `status`, `short_description` i polami kontekstowymi.
   - Zasilać go z całego lifecycle KSeF (sale, UPO, session, purchase sync, 429 retry/resume).
   - Frontend przełączyć na ten dziennik (z zachowaniem obecnych wpisów sprzedażowych).

## Rekomendacja końcowa

Wdrożyć osobny, unified log operacji KSeF zamiast przeciążania obecnej tabeli `transmissions`.
To najbezpieczniej zachowa aktualny flow sprzedaży i jednocześnie da pełną obserwowalność operacyjną przed uruchomieniem harmonogramu auto-sync 2x/dzień.
