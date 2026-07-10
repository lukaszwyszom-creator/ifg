# IFG — standard operacji długotrwałych (Long Running Operations)

**Data:** 2026-07-03  
**Branch:** `production`  
**Status:** dokument referencyjny projektowy  
**Kontekst:** doświadczenia z naprawy synchronizacji KSeF (429 / resume / deploy DS723+)

Powiązane dokumenty:
- [KSEF_PURCHASE_SYNC_429_RESUME_FIX.md](./KSEF_PURCHASE_SYNC_429_RESUME_FIX.md)
- [KSEF_PURCHASE_SYNC_PRE_DEPLOY_REVIEW.md](./KSEF_PURCHASE_SYNC_PRE_DEPLOY_REVIEW.md)
- [KSEF_PURCHASE_SYNC_429_RESUME_DEPLOY.md](./KSEF_PURCHASE_SYNC_429_RESUME_DEPLOY.md)

---

# 1. Cel

IFG integruje systemy zewnętrzne (KSeF, REGON, NBP), przetwarza dokumenty (OCR, PDF, JPK) i wykonuje operacje wsadowe (import, eksport, przeliczenia magazynu). Wiele z tych operacji trwa **dłużej niż timeout HTTP** (sekundy–godziny), podlega **limitom zewnętrznym** (HTTP 429), wymaga **wznowienia po restarcie** i musi być **audytowalna** operacyjnie.

Bez wspólnego standardu każdy moduł implementuje własny wariant:

- sync inline w API vs worker,
- „retry” przez sleep w procesie vs odroczenie joba,
- utrata postępu przy błędzie,
- fałszywy sukces mimo niekompletnych danych,
- równoległe joby uderzające w ten sam zasób zewnętrzny,
- brak spójnych logów do diagnostyki prod.

**Naprawa KSeF purchase sync (2026-07)** pokazała koszt braku standardu: dwie ścieżki pobierania XML (`bulk` bez resume vs `incremental` z resume), 429 traktowane jako `skipped_error`, brak faktur w DB mimo „zakończonego” raportu, równoległe sync API + worker.

**Cel tego dokumentu:** jeden wzorzec architektoniczny dla wszystkich modułów IFG wykonujących operacje długotrwałe. Programista implementujący nowy moduł **nie projektuje mechanizmu od zera** — stosuje ten standard i checklist z rozdz. 12.

---

# 2. Definicja Long Running Operation

## 2.1 Kiedy operacja jest „long running”

Operacja jest **long running**, jeśli spełnia **co najmniej jedno** z kryteriów:

| Kryterium | Próg orientacyjny |
|-----------|-------------------|
| Czas wykonania | > **3–5 s** typowo, lub nieprzewidywalny |
| Ryzyko timeoutu HTTP | > **30 s** lub zależność od API zewnętrznego |
| Wolumen danych | paginacja, setki/tysiące rekordów |
| Rate limiting | HTTP 429, quota, throttling |
| Wymaga wznowienia | restart procesu nie może kasować postępu |
| Efekt uboczny w DB | wieloetapowy zapis, częściowy sukces |

Operacja **nie jest** long running, jeśli: pojedyncze zapytanie SQL, CRUD jednego rekordu, walidacja formularza, generowanie PDF jednej faktury (< 2 s).

## 2.2 Przykłady w IFG

| Operacja | Dlaczego long running |
|----------|------------------------|
| Sync faktur zakupowych KSeF | metadata + N× GET XML, 429, minuty–godziny |
| Pobieranie UPO | polling statusu KSeF, defer |
| Submit faktury do KSeF | `submit_invoice` + `poll_ksef_status` joby |
| OCR dokumentów | przetwarzanie pliku, kolejka |
| Import CSV kontrahentów/faktur | wiele wierszy, walidacja, flush |
| Eksport JPK / zestawień | generowanie dużego pliku |
| Eksport danych (backup, raport) | duży SELECT + serializacja |
| Sync kontrahentów (REGON / zewn.) | wiele zapytań API |
| Przeliczenia magazynu (FIFO, salda) | wiele warstw, transakcje |

## 2.3 Zasada domyślna

**Domyślnie: long running → BackgroundJob + worker.**  
Wyjątek (sync krótki, < 5 s, bez resume): dopuszczalny endpoint inline **tylko** z tym samym serwisem co worker i z jasnym limitem wolumenu. Nie tworzyć osobnej ścieżki „bulk bez resume”.

---

# 3. Standard architektury

```
UI (trigger + polling statusu)
        ↓
API (enqueue, 202 + job_id, conflict 409)
        ↓
BackgroundJob (payload, resume, partial_result)
        ↓
Worker (claim, handler, defer/done/failed)
        ↓
Serwis domenowy (logika + audit + flush per unit)
        ↓
Resume (payload_json.resume przy defer)
        ↓
Complete (done + opcjonalnie HWM)
```

## 3.1 UI

- **Trigger:** jeden przycisk/akcja → **async enqueue**, nie blokujący request na minuty.
- **Status:** polling `GET .../jobs/{job_id}` lub odświeżanie stanu modułu (np. KSeF topbar).
- **Komunikaty:** rozróżnia `pending`, `processing`, odroczony (`available_at` w przyszłości), `done`, `failed`, `deferred` (logicznie).
- **Guard:** nie wysyłać drugiego triggera, gdy job aktywny (UI disable + backend 409).
- **Nie** wołać inline endpointu długiej operacji jako primary path (lekcja KSeF: `/sync/purchases` vs `/sync-purchase`).

## 3.2 API

- **Enqueue:** `POST` → `202 Accepted`, body `{ job_id, status: "pending" }`.
- **Dedup:** jeśli aktywny job dla klucza (NIP, scope) → zwróć istniejący `job_id` (KSeF) lub `409 Conflict`.
- **Nie** wykonywać pełnej operacji synchronicznie w request lifecycle (uvicorn worker).
- Walidacja wejścia, auth, zapis joba, commit — **koniec** odpowiedzi API.
- Endpoint statusu joba: `status`, `last_error`, `partial_result`, opcjonalnie progress.

## 3.3 BackgroundJob

- Rekord w `background_jobs` (PostgreSQL JSONB).
- Trwały nośnik postępu, resume i partial result.
- Przetrwa restart API, workera, kontenera.

## 3.4 Worker

- Pętla poll (`app.worker`), claim z `FOR UPDATE SKIP LOCKED`.
- Jeden handler na `job_type`.
- Przy defer: `JobRateLimitDeferredError` → `pending` + `available_at` + `payload.resume`.
- Przy sukcesie: `done` + `payload.result`.
- Przy błędzie trwałym: `failed` po wyczerpaniu `max_attempts`.

## 3.5 Resume

- Stan w `payload_json.resume` — **jedyny** autorytatywny checkpoint po defer.
- Handler przekazuje `resume_state=payload.get("resume")` do serwisu.
- Serwis **nie** pobiera od początku listy, jeśli resume istnieje.

## 3.6 Complete

- `status=done`, wynik w `payload.result`.
- Opcjonalnie: aktualizacja **high-water-mark** (`ksef_sync_states`, analogiczne tabele scope) **tylko** przy pełnym sukcesie.
- Audit: marker `COMPLETE` / `SUMMARY`.

---

# 4. BackgroundJob

## 4.1 Model IFG (istniejący)

Tabela: `background_jobs` (`app/persistence/models/background_job.py`).

| Kolumna | Rola |
|---------|------|
| `id` | UUID joba |
| `job_type` | string, np. `sync_purchase_invoices` |
| `payload_json` | JSONB — parametry, resume, partial_result, result |
| `status` | `pending` \| `processing` \| `done` \| `failed` |
| `available_at` | kiedy job może być claimowany |
| `locked_at`, `locked_by` | claim workera |
| `attempts`, `max_attempts` | licznik prób |
| `last_error` | ostatni błąd (max 1024 znaków) |

## 4.2 Statusy — standard logiczny

| Status DB | Znaczenie operacyjne | Uwagi |
|-----------|----------------------|-------|
| `pending` | oczekuje / **deferred** | deferred = `pending` + `available_at > now()` |
| `processing` | worker wykonuje | `locked_at`, `locked_by` ustawione |
| `done` | sukces | `payload.result` |
| `failed` | błąd końcowy | `attempts >= max_attempts` lub błąd nienaprawialny |

**Deferred** nie wymaga osobnej wartości enum w DB — to **`pending` z przyszłym `available_at`**. W UI/API można mapować na `deferred` dla czytelności.

## 4.3 Standard `payload_json`

```json
{
  "job_id": "uuid",
  "actor_user_id": "uuid|null",
  "scope_key": "9670402857",
  "operation_params": {
    "date_from": "2026-06-01",
    "date_to": "2026-07-03",
    "force_full": true
  },
  "resume": { },
  "partial_result": { },
  "result": { }
}
```

Konwencje:
- **`scope_key`** — klucz deduplikacji (NIP, invoice_id, import_batch_id).
- **`operation_params`** — parametry niezmienne między resume (nie nadpisywać przy defer).
- **`resume`** — checkpoint; nadpisywany przy każdym defer.
- **`partial_result`** — ostatni znany postęp do UI/telemetrii.
- **`result`** — wynik końcowy przy `done`.

## 4.4 Progress

Minimalny zestaw w `partial_result` (ujednolicony dla modułów):

```json
{
  "processed": 44,
  "total": 68,
  "saved": 0,
  "skipped_existing": 44,
  "skipped_error": 0,
  "rate_limited": true,
  "current_offset": 44,
  "warning": "opcjonalny komunikat"
}
```

Opcjonalnie rozszerzenia per moduł (`pages_fetched`, `bytes_written`). UI pokazuje `processed/total` lub procent.

## 4.5 `partial_result`

- Aktualizowany przy **defer** i opcjonalnie okresowo (co N jednostek).
- Służy UI i Guardian bez parsowania pełnego `resume`.
- Nie zastępuje `resume` — resume jest do wznowienia, partial_result do wyświetlania.

## 4.6 `resume_state` (w payload jako `resume`)

Wzorzec KSeF (referencja):

```json
{
  "invoice_refs": ["KSEF-REF-001", "..."],
  "current_offset": 17,
  "current_reference": "KSEF-REF-017",
  "downloaded_count": 17,
  "subject_type": "subject2",
  "saved_accumulated": 15,
  "skipped_existing_accumulated": 2,
  "skipped_parse_accumulated": 0,
  "error_samples": [],
  "metadata_page_offset": 0,
  "continuation_token": null
}
```

Zasady:
- Pola **kumulatywne** (`*_accumulated`) — stan między deferami.
- Pola **pozycyjne** (`current_offset`, `current_reference`, `page`) — gdzie wznowić.
- Pola **cache** (`invoice_refs`, lista ID) — unikaj ponownego pobierania metadanych.
- **Wersjonowanie:** opcjonalne `resume_version: 1` przy zmianie schematu.

---

# 5. Resume

## 5.1 Zasada nadrzędna

**Resume nigdy nie może utracić postępu**, który został już **trwale zapisany** (flush/commit).

Każda jednostka pracy (1 faktura, 1 wiersz CSV, 1 strona API) powinna być:
1. przetworzona,
2. zapisana (`session.flush()` minimum),
3. dopiero potem zwiększony offset.

## 5.2 Typy checkpointów

| Typ | Pole resume | Przykład |
|-----|-------------|----------|
| offset | `current_offset` | lista ref KSeF, indeks w tablicy |
| cursor | `continuation_token`, `next_cursor` | paginacja API |
| page | `metadata_page_offset`, `page` | POST metadata pageOffset |
| token | `upload_session_id` | wieloetapowy upload |
| reference | `current_reference` | ostatni przetworzony ID (debug) |

## 5.3 `retry_after`

- Przechowywany **nie** w resume, lecz w **`available_at`** joba (`now + retry_after_seconds`).
- Źródło: nagłówek HTTP `Retry-After` (KSeF) lub backoff obliczony.
- Resume + defer: job wraca na `pending`, worker nie śpi w pętli.

## 5.4 Recovery po restarcie

| Zdarzenie | Zachowanie |
|-----------|------------|
| Restart workera mid-job | `processing` + stare `locked_at` → **stale reclaim** (`STALE_PROCESSING_SECONDS`, 30 min) |
| Restart API | job w DB bez zmian; worker kontynuuje |
| Recreate kontenera | j.w.; resume w `payload_json` |
| Restart NAS | po starcie DB + worker claimuje pending/deferred |

Po restarcie worker **nie** czyści resume. Serwis przy starcie joba czyta `payload.get("resume")`.

## 5.5 Antywzorce (KSeF)

- Pobieranie całej listy od początku po każdym 429.
- Traktowanie 429 jako `skipped_error` i kontynuacja → fałszywy postęp.
- Brak flush przed defer → utrata zapisanych rekordów w raporcie.

---

# 6. Retry

## 6.1 Definicje

| Mechanizm | Co robi | Kiedy |
|-----------|---------|-------|
| **retry** | ponowna próba **tej samej** operacji po krótkim czasie | błąd przejściowy w **tej samej** sesji handlera |
| **defer** | zakończenie bieżącej próby joba, `pending` + `available_at` | 429, quota, długi Retry-After |
| **resume** | kontynuacja od checkpointu w **nowej** próbie joba | po defer lub świadomym stop |
| **retry-after** | wartość sekund z API → `available_at` | HTTP 429 z nagłówkiem |
| **backoff** | exponential backoff gdy brak Retry-After | timeout, 503, własny limit |

## 6.2 Decyzja (drzewo)

```
Błąd przejściowy w pętli HTTP (krótki)?
  → retry in-process (max N prób, backoff) — np. metadata page

HTTP 429 / długi Retry-After / limit zewnętrzny?
  → defer job (NIE sleep 30+ min w workerze)
  → zapisz resume + partial_result
  → available_at = now + retry_after

Błąd trwały (401 expired session, 404, walidacja)?
  → failed (lub failed po max_attempts)
  → NIE aktualizuj HWM
  → audit ERROR + INCOMPLETE

Sukces częściowy + polityka „all or nothing”?
  → domyślnie IFG: defer/incomplete, NIE done
```

## 6.3 Attempts

- Przy **defer**: `attempts -= 1` (KSeF worker) — defer nie zużywa limitu jak failure.
- Przy **failed** trwałym: `attempts++`, po `max_attempts` → `status=failed`.
- `max_attempts=1` dla sync KSeF (prod) — operator uruchamia ponownie ręcznie; rozważyć wyższy limit z resume dla automatycznego domknięcia.

## 6.4 Retry-After — standard

1. Odczytaj `Retry-After` z odpowiedzi HTTP.
2. Parsuj jako sekundy (float); invalid → backoff.
3. Propaguj do `JobRateLimitDeferredError(retry_after_seconds=...)`.
4. Worker: `available_at = now + timedelta(seconds=retry_after_seconds)`.
5. Log: `WORKER_JOB_DEFERRED retry_after_seconds=...`.

**Nie** używać stałego fallbacku (np. 120 s) bez logu, gdy Retry-After był dostępny.

---

# 7. High Water Mark

## 7.1 Definicja

**High-water-mark (HWM)** — granica postępu inkrementalnego (np. `last_date_to`, `last_success_at` w `ksef_sync_states.state_json`), na podstawie której kolejne syncy wyznaczają okno „co pobrać”.

## 7.2 Kiedy wolno aktualizować

- **Wyłącznie** po **pełnym sukcesie** operacji (wszystkie jednostki w scope przetworzone lub świadomie pominięte jako `skipped_existing`).
- Wywołanie: `mark_success(scope, state_json={...})`.
- Audit: `COMPLETE`, `incomplete=false`.

## 7.3 Kiedy absolutnie nie wolno

- HTTP 429 / defer / incomplete.
- Częściowy zapis z błędami `skipped_error`.
- Wygaśnięcie sesji KSeF w trakcie.
- Przerwanie joba (`failed`, stale bez resume).
- Wywołanie: `mark_error(scope, message)` — HWM **bez zmian**.

## 7.4 Przykład KSeF

| Zdarzenie | HWM | `ksef_sync_states.status` |
|-----------|-----|---------------------------|
| 29 refs metadata, 13× 429, saved=0 (stary bulk) | bez zmian (błędnie wyglądało na postęp) | error / ok (błąd) |
| defer offset=44, saved częściowo | **bez zmian** | error |
| pełny sukces 68/68 | `last_date_to`, `last_counts` | success |

Okno inkrementalne (`resolve_purchase_sync_window_details`) czyta HWM — przedwczesny `mark_success` **ukrywa** brakujące faktury w kolejnych syncach.

---

# 8. Audit

## 8.1 Cel

Jeden grep na prod musi dać pełny obraz operacji: co zaplanowano, co pobrano, co zapisano, czego brakuje, dlaczego incomplete.

Wzorzec: `KSEF_PURCHASE_SYNC_AUDIT` (`app/services/ksef_purchase_sync_audit.py`).

## 8.2 Prefiks markera

```
{MODULE}_{OPERATION}_AUDIT
```

Przykłady:
- `KSEF_PURCHASE_SYNC_AUDIT`
- `WAREHOUSE_RECALC_AUDIT`
- `CSV_IMPORT_AUDIT`

Stały prefix ułatwia Guardian i `docker compose logs | grep`.

## 8.3 Markery obowiązkowe

| Marker | Kiedy | Minimalna treść |
|--------|-------|-----------------|
| **WINDOW** | start operacji | scope_key, date_from/to, source (fresh/resume/force_full), resume summary |
| **PAGE** | każda strona API / batch | page_offset, received, has_more, token |
| **PROGRESS** | co N jednostek (opcjonalnie) | offset, saved, skipped |
| **SUMMARY** | koniec próby | counts, sync_path, incomplete flag |
| **MISSING** | parzystość | refs/metadata not in DB, db_extra |
| **ERROR** | błąd paginacji / krytyczny | komunikat, status HTTP |
| **COMPLETE** | pełny sukces | final_database_count |
| **INCOMPLETE** | defer / partial | rate_limited, skipped_error, pagination_errors |

## 8.4 Pola SUMMARY (minimum)

```
nip / scope_key
date_from, date_to
sync_path (incremental | bulk_resume | ...)
metadata_returned / total_input
saved, skipped_existing, skipped_invalid, skipped_error
xml_downloaded / processed_units
rate_limited, incomplete
final_database_count
```

## 8.5 Poziomy logów

- `INFO` — WINDOW, PAGE, SUMMARY, REFS (sample first/last 20)
- `WARNING` — defer, rate limit
- `ERROR` — INCOMPLETE, PAGINATION_ERROR, ERROR

## 8.6 Telemetria operacyjna (worker)

Osobno od audit domenowego — markery workera:
- `WORKER_JOB_CLAIMED`
- `WORKER_JOB_DEFERRED`
- `WORKER_JOB_SKIPPED`
- `WORKER_POLL_TICK`
- `{MODULE}_ASYNC_WORKER_START` / `_DONE` / `_ERROR`

---

# 9. Locking

## 9.1 Zasada

**Thread lock (`threading.Lock`) nie jest wystarczającym zabezpieczeniem** — działa tylko w jednym procesie Pythona. IFG: API (uvicorn) i worker to **osobne kontenery/procesy**.

Lock musi być **współdzielony** — minimum przez **BackgroundJob w PostgreSQL**.

## 9.2 Warstwy (od najsłabszej do najsilniejszej)

| Warstwa | Zasięg | Zastosowanie |
|---------|--------|--------------|
| UI guard | sesja użytkownika | disable przycisku |
| Enqueue dedup | DB | zwróć istniejący job_id |
| Active job query | DB | `pending`/`processing` + `scope_key` → 409 |
| Advisory lock PostgreSQL | DB cross-process | `(job_type, scope_key)` — **rekomendowane** |
| Thread lock | proces | tylko jako dodatek w API |

## 9.3 Klucze locka

| Scope | Klucz | Przykład |
|-------|-------|----------|
| Per NIP | `payload_json.nip` | sync KSeF |
| Per firma | `tenant_id` / seller_nip | import wsadowy |
| Per użytkownik | `actor_user_id` | eksport „mój plik” |
| Per zasób | `invoice_id`, `batch_id` | submit, OCR |

## 9.4 BackgroundJob jako lock

Aktywny job = lock logiczny:
```sql
WHERE job_type = ? AND status IN ('pending', 'processing')
  AND payload_json->>'nip' = ?
```

Worker wywołujący sync: `exclude_job_id=self_job_id` (nie blokować siebie).

## 9.5 Advisory lock (docelowo)

```sql
SELECT pg_try_advisory_lock(hashtext('sync_purchase_invoices'), hashtext(nip));
```

Zwalnianie w `finally`. Odporność na inline API bez rekordu job (luka KSeF pre-deploy).

## 9.6 Antywzorzec

- Dwa endpointy (inline + async) bez wspólnego locka DB.
- Równoległe joby tego samego NIP w KSeF — podwaja 429.

---

# 10. Recovery

## 10.1 Scenariusze

| Zdarzenie | Oczekiwane zachowanie |
|-----------|------------------------|
| Restart API | brak utraty jobów; enqueue działa |
| Restart workera | claim kolejnego pending/deferred; stale processing reclaim |
| Recreate kontenera Docker | j.w.; resume w JSONB |
| Restart NAS / PostgreSQL | po `healthy` worker wznawia; job deferred z `available_at` |
| Deploy nowej wersji kodu | stary job z resume — nowy kod kontynuuje od offset (test regresji) |
| Wygaśnięcie sesji zewn. (KSeF) | job `failed`, resume zachowany, operator reconnect |

## 10.2 Stale processing

IFG: `STALE_PROCESSING_SECONDS = 1800` — job w `processing` z `locked_at` starszym niż 30 min może być reclaimowany.

## 10.3 Idempotencja

Przed ponownym pobraniem z zewnątrz: sprawdź istnienie w DB (`exists_by_ksef_number`, unikalny klucz importu). Resume + idempotencja = brak duplikatów i mniej obciążenia API.

## 10.4 Operator recovery

1. Sprawdź logi audit + `last_error` joba.
2. Napraw prerequisite (sesja KSeF, token).
3. **Nie** twórz równoległego joba — wznów ten sam (deferred pending) lub enqueue po `failed` (z resume jeśli polityka modułu pozwala).

---

# 11. Guardian

Guardian / Guardian2 (`scripts/guardian2.py`, `scripts/guardian.py`) — warstwa operacyjna deploy i sanity check, rozszerzalna o monitoring jobów.

## 11.1 Deploy długich operacji

- Testy jednostkowe modułu przed push.
- Post-deploy: commit hash, `docker compose ps`, `/health`.
- **Uwaga:** post-check na hoście NAS (Python 3.8) vs kontener (3.13) — check w kontenerze API.

## 11.2 Monitorowanie jobów (docelowe / manualne)

| Sygnał | Detekcja | Akcja |
|--------|----------|-------|
| deferred jobs | `pending` + `available_at > now()` | normalne; log `WORKER_JOB_DEFERRED` |
| stuck processing | `processing` + `locked_at` > 30 min | stale reclaim / alert |
| failed jobs | `status=failed` | alert, `last_error` |
| retry storm | wiele defer w krótkim czasie | rate limit audit, backoff |
| incomplete sync | audit `INCOMPLETE` | nie uznawać deploy/sync za sukces |

## 11.3 Telemetry / health

- `/health` — API alive, DB, integracje skonfigurowane.
- Worker: `WORKER_POLL_TICK pending_count claimable_count`.
- KSeF: grep `KSEF_PURCHASE_SYNC_AUDIT`, `KSEF_RATE_LIMIT_DEFER`.

## 11.4 Recovery (Guardian recover-prod)

- Sprawdzenie kontenerów api/worker/db.
- Logi ostatniej godziny.
- Nie restartować workera w trakcie `processing` bez świadomości stale policy.

---

# 12. Checklist dla programisty

Przed merge modułu long running:

- [ ] **BackgroundJob** — enqueue 202, `job_type`, payload ze `scope_key`
- [ ] **Resume** — checkpoint w `payload.resume`, test wznowienia od offsetu
- [ ] **Retry** — rozróżnienie retry in-process vs defer job
- [ ] **Retry-After** — propagacja do `available_at`
- [ ] **Lock** — DB (active job / advisory), nie sam thread lock
- [ ] **Audit** — WINDOW, PAGE, SUMMARY, INCOMPLETE/COMPLETE, stały prefix
- [ ] **Progress** — `partial_result` dla UI
- [ ] **Recovery** — flush per unit; test restart/resume
- [ ] **Tests** — defer, resume offset, skip existing, parallel lock, no HWM on incomplete
- [ ] **Telemetry** — worker START/DONE/DEFERRED/ERROR
- [ ] **Guardian** — dokumentacja grep / SQL weryfikacji dla modułu

---

# 13. Wnioski

## 13.1 Doświadczenia z naprawy KSeF (2026-07)

**Problem prod:** metadata OK (29 refs), XML 429, 0 nowych zapisów, brak faktur lipcowych, raport sugerujący zakończenie.

**Przyczyna architektoniczna:** dwie ścieżki sync (inline bulk vs worker incremental), brak resume na API, 429 jako kontynuacja z błędami.

## 13.2 Decyzje trafne

| Decyzja | Dlaczego |
|---------|----------|
| Jedna ścieżka incremental + resume (API = worker) | brak rozjazdu semantyki |
| Defer zamiast sleep w workerze | worker nie blokuje kolejki 30+ min |
| `payload_json.resume` bez migracji DB | szybki deploy, trwałość w PostgreSQL |
| Flush po każdej fakturze | postęp przetrwa defer |
| `exists_by_ksef_number` przed GET | mniej 429, szybsze resume |
| `mark_error` + brak HWM przy incomplete | kolejny sync nie pomija okna |
| Audit `KSEF_PURCHASE_SYNC_AUDIT` | szybka diagnoza prod (29 vs saved vs DB) |
| Async enqueue jako primary UI path | unika timeoutów i równoległości z workerem |
| Testy: offset 17, parallel NIP, no mark_success on defer | regresja udokumentowana |

## 13.3 Czego unikać

| Antywzorzec | Skutek |
|-------------|--------|
| Osobna ścieżka „szybka” bez resume | utrata postępu, fałszywy sukces |
| 429 → `skipped_error` + continue | incomplete dane w DB |
| `mark_success` przy partial | błędny HWM, brak retry okna |
| Thread lock jako jedyny lock | równoległość API vs worker |
| Inline sync > 5 s jako default | timeout, 429, brak defer |
| Brak audit SUMMARY/INCOMPLETE | niediagnozowalny prod |
| Różne max_attempts bez polityki resume | failed bez możliwości domknięcia |
| Post-check Guardian tylko na hoście NAS | fałszywy fail deploy (Python 3.8 vs 3.13) |

## 13.4 Stan po deploy (referencja)

- Deploy `a405646`: kod OK, resume działa (offset 44, skipped_existing 44).
- Sync nie domknięty: sesja KSeF expired — prerequisite poza kodem.
- 3 faktury lipca w DB z wcześniejszego resume — dowód, że mechanizm zapisuje.

---

# Możliwe przyszłe usprawnienia

## bulk_resume

Dla >500–1000 jednostek: fazy metadata → batch download → batch persist, **z tym samym** `resume_state`. Nie przywracać bulk bez resume. Próg konfigurowalny per `job_type`.

## batch persist

Flush co N rekordów (50–100) zamiast per-row — mniejszy narzut DB przy zachowaniu checkpointu co batch.

## advisory lock PostgreSQL

Wspólny lock `(job_type, scope_key)` między API a workerem — zamknięcie luki inline vs async.

## distributed worker

Wiele replik workera z `SKIP LOCKED` — już wspierane przez claim query; wymaga silniejszego lock scope i idempotencji.

## kolejka priorytetowa

Priorytet jobów: submit faktury > sync > eksport. Kolumna `priority` + order by w claim.

## automatyczne recovery

Po `failed` z resume: auto re-enqueue jeśli `attempts < max` i błąd przejściowy (expired session → nie). Po reconnect KSeF: trigger sync z ostatniego resume.

## metrics

Prometheus / structured metrics: `ifg_job_duration_seconds`, `ifg_job_deferred_total`, `ifg_sync_incomplete_total`, histogram `retry_after_seconds`.

## dashboard operacyjny

Panel admin: aktywne joby, deferred count, ostatni audit SUMMARY, status sesji KSeF, HWM per scope.

## observability

- Korelacja `job_id` we wszystkich logach (API enqueue → worker → audit).
- OpenTelemetry trace dla wywołań KSeF.
- Alert na `INCOMPLETE` + `rate_limited=true` w oknie > X godzin.

## Guardian rozszerzony

- `--jobs-check`: pending deferred, stuck processing, failed last 24h.
- Post-deploy check **w kontenerze API** (Python 3.13), nie na hoście Synology.
- Automatyczny raport Markdown po deploy (wzór: `KSEF_PURCHASE_SYNC_429_RESUME_DEPLOY.md`).

## metadata defer + resume

Osobny checkpoint fazy paginacji metadata (page_offset, continuation_token) przy 429 na POST metadata — dziś retry in-process only.

## unified job status API

`GET /api/v1/jobs/{id}` generyczny dla wszystkich `job_type` z mapowaniem `deferred` = pending + future `available_at`.

---

**Koniec dokumentu.**  
Implementacje nowych modułów IFG powinny odwoływać się do tego standardu w PR i w testach jednostkowych.
