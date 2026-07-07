# Audyt: zależność auto-sync zakupów KSeF od aktywnej sesji

**Data:** 2026-07-07  
**Zakres:** read-only — bez zmian kodu, deployu i migracji  
**Kontekst produkcyjny:** scheduler wdrożony; recovery + `SCHEDULER_ENQUEUE` OK; job `sync_purchase_invoices` failed: `Brak aktywnej sesji KSeF dla NIP 9670402857`

---

## 🩷 STATUS KOŃCOWY

### ✅ Co działa (z perspektywy schedulera)

- Scheduler poprawnie enqueue'uje job `sync_purchase_invoices` z `incremental=true`.
- Worker poprawnie odbiera job i woła tę samą ścieżkę serwisową co ręczny sync.
- Błąd sesji jest **deterministyczny** i pochodzi z jawnej walidacji w `KSeFSessionService`.

### ⚠️ Znane problemy

- Auto-sync **nie jest samowystarczalny** — wymaga wcześniej utworzonej sesji w `ksef_sessions` (status `active`).
- UI zakłada model „najpierw Połącz, potem sync”; scheduler tego nie robi.
- `refresh_access_token` istnieje w integracji, ale **nie jest używany** w aplikacji — wygasłe sesje nie są odnawiane automatycznie.

### ❌ Co nie działa (dla auto-sync bez interwencji użytkownika)

- Planowe cykle 08:00 / 14:00 **nie pobiorą zakupów**, jeśli nikt nie otworzył sesji KSeF w UI (lub API) i token nie jest w DB.

---

## 1. Gdzie rzucany jest błąd

**Źródło komunikatu (dokładne):**

```217:221:app/services/ksef_session_service.py
    def get_active_session(self, nip: str) -> KSeFSessionORM:
        nip = _normalize_session_nip(nip)
        orm = self._get_active_db_session(nip)
        if orm is None:
            raise NotFoundError(f"Brak aktywnej sesji KSeF dla NIP {nip}.")
```

**Powiązany wariant (wygasła sesja):**

```225:238:app/services/ksef_session_service.py
        if expires_at is not None and expires_at <= now:
            orm.status = SESSION_EXPIRED
            ...
            raise NotFoundError(f"Sesja KSeF dla NIP {nip} wygasła.")
```

**Łańcuch wywołań przy sync zakupów:**

```
sync_purchase_invoices()
  → sync_received_invoices()
    → get_session_context(nip)
      → get_active_session(nip)   ← tutaj NotFoundError
```

```716:731:app/services/ksef_session_service.py
    def sync_received_invoices(...):
        ...
        ctx = self.get_session_context(nip)
```

**Uwaga:** Podobny komunikat dla **wysyłki sprzedaży** (inna ścieżka) występuje w `TransmissionService._ensure_ksef_session_connected()` — to osobny guard UI/sprzedaży, nie sync zakupów.

---

## 2. Kto wywołuje ten fragment

### A. Ręczny sync zakupów

| Wejście | Enqueue? | Wywołanie serwisu | Sesja sprawdzana |
|---------|----------|-------------------|------------------|
| `POST /api/v1/ksef/sync/purchases` | Nie (sync inline) | `ksef_session_service.sync_purchase_invoices(...)` | **Tak**, w trakcie wykonania |
| `POST /api/v1/ksef-sessions/sync-purchase` | Tak (202 + job_id) | Worker → `SyncPurchaseInvoicesJobHandler.handle()` → `sync_purchase_invoices(...)` | **Nie** przy enqueue; **Tak** w workerze |

**UI (frontend):**

- `KSeFConnectionTile` — klik „Połącz” → `openSession()` → dopiero potem `runPurchaseSync()`.
- `KSeFTopbarInfo` — „Odśwież KSeF” wymaga `ui_status === 'CONNECTED'` (czyli sesja już istnieje).
- `runPurchaseSync()` woła wyłącznie async enqueue — **nie otwiera sesji**.

### B. Job background `sync_purchase_invoices`

```49:86:app/worker/job_handlers/sync_purchase_invoices.py
    def handle(self, payload: dict) -> dict:
        ...
        report = self._ksef_session_service.sync_purchase_invoices(
            nip=nip,
            date_from=date_from,
            date_to=date_to,
            incremental=incremental,
            ...
        )
```

Job `max_attempts=1` — `NotFoundError` kończy się od razu `status=failed` (brak retry na brak sesji).

### C. Scheduler auto-sync

```196:211:app/worker/__main__.py
        job = BackgroundJob(
            id=uuid4(),
            job_type="sync_purchase_invoices",
            payload_json={
                "job_id": "",
                "nip": settings.seller_nip,
                "incremental": True,
                "force_full": False,
                "date_from": None,
                "date_to": None,
                "scheduler_slot": slot_key,
                "scheduler_recovery": decision.is_recovery,
            },
            ...
        )
```

Scheduler **nie** wywołuje `open_session()` ani nie sprawdza sesji przed enqueue — zakłada, że worker poradzi sobie z istniejącą sesją w DB.

---

## 3. Czy import zakupów technicznie wymaga sesji DB?

### Co wymaga KSeF API (wg implementacji klienta)

Sync zakupów używa wyłącznie **Bearer `access_token`**:

- `POST /invoices/query/metadata` — `query_purchase_metadata_refs(access_token=...)`
- `GET /invoices/ksef/{ref}` — `get_purchase_invoice_xml(access_token, ref)`

```767:771:app/services/ksef_session_service.py
            metadata_refs = self.ksef_client.query_purchase_metadata_refs(
                access_token=ctx.access_token,
                ...
            )
```

Komentarz w kliencie potwierdza, że **nie** używa się ścieżki `/sessions/online/{ref}/invoices/query` do zakupów.

### Czego wymaga IFG (implementacja)

IFG wymaga rekordu w `ksef_sessions` ze statusem `active` i tokenami w `token_metadata_json`, pobieranego przez `get_session_context()`.

`open_session()` wykonuje **dwa** kroki:

1. Uwierzytelnienie tokenem `KSEF_AUTH_TOKEN` → access + refresh token.
2. `open_online_session(access_token)` → sesja interaktywna FA(3) + klucz symetryczny (potrzebny do **wysyłki** faktur sprzedaży, nie do pobierania zakupów).

**Wniosek techniczny:** Pobranie zakupów w KSeF v2 wymaga **ważnego access tokena**, nie sesji online UI. Obecna architektura IFG **sztucznie wiąże** sync zakupów z pełnym modelem „sesji UI” w DB, mimo że do metadata/XML wystarczy token.

---

## 4. Istniejące mechanizmy sesji

| Mechanizm | Plik | Używany przez worker/schedulera? |
|-----------|------|----------------------------------|
| `open_session(nip)` | `ksef_session_service.py` | **Nie** |
| `close_session(nip)` | `ksef_session_service.py` | **Nie** |
| `get_active_session(nip)` | `ksef_session_service.py` | **Tak** (pośrednio przez sync) |
| `mark_session_expired(nip)` | `ksef_session_service.py` | **Nie** (tylko z handlerów sprzedaży przy 401) |
| `expire_stale_sessions()` | `ksef_session_service.py` | **Nie** (brak wywołań w workerze/cronie) |
| `refresh_access_token()` | `integrations/ksef/auth.py` | **Nie** (zdefiniowany, nigdzie niepodpięty) |

**Ręczny endpoint otwarcia sesji:**

- `POST /api/v1/ksef/session/open`
- `POST /api/v1/ksef-sessions/` (alias)

Oba wołają `open_session()` z `KSEF_AUTH_TOKEN` z konfiguracji środowiska.

**Worker** ma dostęp do `KSeFAuthProvider` i `KSEF_AUTH_TOKEN` (budowa w `_build_ksef_session_service`), ale **nie używa** ich do auto-otwarcia sesji przed sync.

---

## 5. Czy `POST /api/v1/ksef-sessions/sync-purchase` otwiera sesję?

**Nie.** Endpoint tylko:

1. Sprawdza duplikat joba `pending`/`processing` dla NIP.
2. Tworzy `BackgroundJob` i zwraca `202`.

```304:361:app/api/routers/ksef_session.py
def sync_purchase_invoices(body: SyncPurchaseRequest, ...):
    ...
    job = BackgroundJob(
        job_type="sync_purchase_invoices",
        payload_json={...},
        status="pending",
    )
```

Opis OpenAPI mówi „Wymaga aktywnej sesji KSeF”, ale **walidacja sesji nie jest w enforce na etapie enqueue** — błąd pojawia się dopiero w workerze (lub przy sync synchronicznym).

---

## 6. Porównanie endpointów sync

| | `POST /api/v1/ksef/sync/purchases` | `POST /api/v1/ksef-sessions/sync-purchase` |
|---|-----------------------------------|-------------------------------------------|
| Router | `router_status` (`/ksef`) | `router_sessions` (`/ksef-sessions`) |
| Tryb | **Synchroniczny** (blokuje request do końca) | **Asynchroniczny** (202 + job) |
| Serwis docelowy | `sync_purchase_invoices()` | Ten sam, via worker |
| Parametry | `nip`, `date_from/to`, `incremental`, `force_full`, `days_back` (opcjonalne) | **Wymagane** `nip`, `date_from`, `date_to` w body |
| Sesja | Wymagana przy wykonaniu | Wymagana przy wykonaniu joba |
| UI | Fallback przy 404 job API | **Primary** (`runPurchaseSync`) |

**Wniosek:** To **ta sama logika biznesowa** (`KSeFSessionService.sync_purchase_invoices`), różni się transport (inline vs kolejka) i kontrakt HTTP.

---

## 7. Scheduler — job i payload

| Pole payload | Wartość schedulera | Poprawność |
|--------------|-------------------|------------|
| `job_type` | `sync_purchase_invoices` | ✅ zgodne z handlerem |
| `nip` | `settings.seller_nip` | ✅ |
| `incremental` | `true` | ✅ (okno z `ksef_sync_states`) |
| `force_full` | `false` | ✅ |
| `date_from` / `date_to` | `null` | ✅ — serwis wylicza okno inkrementalne |
| `actor_user_id` | brak | OK dla auto |
| `scheduler_slot` | `YYYY-MM-DDTHH:MM` | telemetria |
| `max_attempts` | `1` | ⚠️ brak retry przy braku sesji |

Scheduler enqueue'uje **właściwy** job. Problem nie leży w schedulerze, leży w **braku credentials w DB** w momencie wykonania.

---

## 8. Modele docelowe

### A. Scheduler wymaga wcześniej otwartej sesji (obecne zachowanie de facto)

Operator klika „Połącz” w UI; sesja żyje w DB; auto-sync o 08:00/14:00 działa, dopóki token ważny.

### B. Scheduler/worker sam otwiera sesję na czas importu

Przed `sync_purchase_invoices` worker woła `ensure_session()`:
- auth przez `KSEF_AUTH_TOKEN` (+ ewentualnie refresh),
- opcjonalnie `open_online_session` tylko jeśli wymagane,
- po sync — `close_session` lub zostawienie sesji.

### C. Osobny mechanizm autoryzacji dla zakupów (bez sesji UI)

Rozdzielenie:
- **Purchase auth context** — sam access token (auth/refresh), bez sesji online.
- **Online session** — tylko dla wysyłki sprzedaży (`submit_invoice`).

Sync zakupów używa `get_purchase_access_token(nip)` zamiast `get_session_context()`.

### D. Hybryda B+C (rekomendowany kierunek)

1. `ensure_purchase_auth(nip)` przed sync (scheduler + worker + opcjonalnie API).
2. Refresh tokena z DB gdy wygasł access, pełny auth gdy brak sesji.
3. Online session **nie** otwierać dla samego importu zakupów.
4. Sprzedaż nadal wymaga jawnej sesji online (UI „Połącz” lub dedykowany flow).

---

## 9. Ocena ryzyk wariantów

| Wariant | Bezpieczeństwo | Zgodność KSeF | Odporność restart | Ryzyko otwartych sesji | Wpływ na ręczny sync |
|---------|----------------|---------------|-------------------|------------------------|----------------------|
| **A (status quo)** | Wysokie — sesja tylko po akcji użytkownika | OK | **Niska** — restart workera ≠ utrata sesji DB, ale **brak sesji / expiry** zatrzymuje auto-sync | Niskie — użytkownik kontroluje | Bez zmian |
| **B (auto open/close)** | Średnie — worker używa `KSEF_AUTH_TOKEN` bez UI | OK jeśli API MF na to pozwala | **Wysoka** | **Średnie/wysokie** — ryzyko wiszących sesji online przy błędach | Może ujednolicić ręczny i auto |
| **C (auth bez online)** | Dobre — minimalny scope tokena | **Najlepiej dopasowany** do API zakupów | **Wysoka** | **Niskie** — brak sesji online dla importu | Wymaga refaktoru `get_session_context` |
| **D (B+C)** | Dobre | Najlepsze rozdzielenie purchase vs sale | **Wysoka** | Niskie dla zakupów | Ręczny sync działa bez „Połącz” jeśli jest `KSEF_AUTH_TOKEN` |

**Dodatkowe ryzyka status quo (A):**

- Sesja access token ma `expires_at` — bez refresh **drugi slot (14:00) może paść** nawet po porannym „Połącz”.
- `expire_stale_sessions()` nie jest wywoływane periodycznie — stan „active” w DB może być mylący.
- Dokumentacja deployu schedulera już wskazuje ręczne otwarcie sesji — to **luka produktowa**, nie bug schedulera.

---

## 10. Rekomendacja

### Werdykt

**Obecne zachowanie nie jest poprawne jako docelowy model auto-sync**, ale jest **zgodne z istniejącą implementacją** `KSeFSessionService` zaprojektowaną pod model UI-first. Scheduler został dodany jako cienka warstwa enqueue **bez** uzupełnienia warstwy credentials — to **luka implementacyjna / dług architektoniczny**, nie zamierzona funkcja „auto-sync wymaga kliknięcia”.

**Nie zostawiać** wyłącznie wariantu A jako docelowego rozwiązania auto-sync.

### Rekomendowany kierunek: **wariant D (hybryda)**

#### Faza 1 — minimalna (najmniejsze ryzyko, szybki efekt)

W `sync_purchase_invoices()` / workerze (ścieżka `incremental=true` + scheduler):

1. Dodać `ensure_purchase_auth(nip)` **przed** `sync_received_invoices()`:
   - jeśli brak aktywnej sesji → `auth_provider.get_tokens(nip, settings.ksef_auth_token)` i zapis tokenów do DB (status `active`);
   - jeśli sesja wygasła a jest `refresh_token` → `refresh_access_token()` i aktualizacja DB;
   - **nie** wołać `open_online_session` na tej ścieżce.
2. Przy błędzie auth — journal `PURCHASE_SYNC_AUTO` + `ERROR`, job `failed` z czytelnym komunikatem operacyjnym.
3. Zwiększyć `max_attempts` dla schedulerowych jobów (np. 2–3) **tylko** dla błędów auth przejściowych.

#### Faza 2 — porządkowa

1. Rozdzielić API:
   - `get_purchase_access_token(nip)` — zakupy,
   - `get_online_session_context(nip)` — sprzedaż.
2. Podpiąć `expire_stale_sessions()` do ticka workera.
3. Zaktualizować dokumentację operacyjną: auto-sync nie wymaga UI, wymaga `KSEF_AUTH_TOKEN` w ENV.

#### Faza 3 — opcjonalnie

- Health check schedulera: „czy da się uzyskać purchase auth?” bez pełnego syncu.
- Alert w Monitorze KSeF przy `SCHEDULER_ENQUEUE` + job failed `NO_KSEF_SESSION`.

### Tymczasowo operacyjnie (do wdrożenia Fazy 1)

1. Przed 08:00 / 14:00 — **Połącz KSeF** w UI (lub `POST /ksef-sessions/`).
2. Monitoruj `ksef_sessions` dla NIP `9670402857` (`status=active`, `expires_at`).
3. Po każdym failed job — sprawdź `background_jobs.last_error` i journal `PURCHASE_SYNC_AUTO`.

---

## A. Root cause

Auto-sync enqueue działa; wykonanie pada, bo `sync_received_invoices()` wymaga rekordu `ksef_sessions.status=active`, a po restarcie workera / bez interakcji UI taki rekord nie istnieje. Scheduler nie był zaprojektowany do samodzielnego uwierzytelnienia w KSeF.

## B. Pliki kluczowe (audyt)

| Plik | Rola |
|------|------|
| `app/services/ksef_session_service.py` | `get_active_session`, `open_session`, `sync_purchase_invoices`, `sync_received_invoices` |
| `app/worker/job_handlers/sync_purchase_invoices.py` | Handler joba |
| `app/worker/__main__.py` | Scheduler enqueue |
| `app/api/routers/ksef_session.py` | Endpointy sync + open session |
| `app/integrations/ksef/auth.py` | Auth + refresh (refresh nieużywany) |
| `app/integrations/ksef/client.py` | Metadata/XML zakupów (Bearer only) |
| `frontend-react/src/components/layout/KSeFConnectionTile.jsx` | UI: open → sync |
| `frontend-react/src/api/ksef.js` | `runPurchaseSync` bez open |

## C. Deploy / migracje

Nie wykonywano (zgodnie z zakresem audytu).

## D. Testy istniejące (kontekst)

- `tests/unit/test_ksef_session_worker.py` — scenariusz „Brak aktywnej sesji” dla `submit_invoice`.
- `tests/unit/test_ksef_sync_api.py` — API sync (mock serwisu, bez prawdziwej sesji).
- Brak testu integracyjnego „scheduler enqueue → brak sesji → failed”.

## E. Następny krok

Implementacja **Fazy 1** wariantu D: `ensure_purchase_auth()` na ścieżce auto-sync / worker, bez wymogu kliknięcia UI.

---

*Audyt read-only. Scheduler uznany za poprawny; naprawa dotyczy warstwy sesji/uwierzytelnienia dla background sync zakupów.*
