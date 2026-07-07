# GWO-IFG-0032 — Final Review przed deployem

**Data:** 2026-07-07  
**Zakres:** read-only review implementacji (bez deployu, bez zmian architektury)  
**Kontekst:** `docs/reports/2026-07-07_KSEF_PURCHASE_AUTH_REFACTOR_DESIGN.md`

---

## 🩷 STATUS KOŃCOWY

### ✅ Co działa

- Rozdzielenie purchase auth vs online session jest spójne i backward compatible.
- `sync_received_invoices()` deleguje do `PurchaseAuthService.ensure_purchase_auth()`.
- Sprzedaż nadal wymaga `get_session_context()` / `ensure_online_session()`.
- **70 testów** jednostkowych KSeF-related — wszystkie przechodzą (stan z 2026-07-07).
- Guardian `ksef check` — exit 0.

### ⚠️ Znane problemy (przed deployem)

- Brak **fail-fast** przy starcie workera, gdy `KSEF_AUTO_SYNC_ENABLED=true` a `KSEF_AUTH_TOKEN` pusty.
- `refresh_access_token()` poprawnie nie oczekuje nowego refresh tokena (zgodnie z API MF), ale `build_token_metadata()` przy refresh **zeruje** `refresh_valid_until` w DB.
- Brak testu integracyjnego pełnego łańcucha scheduler → worker → auth → import.

### ❌ Co nie działa

- Brak blockerów kodowych w zakresie refaktoru — pod warunkiem poprawnej konfiguracji ENV produkcyjnego.

---

## 1. Startup validation — `KSEF_AUTH_TOKEN`

### Stan obecny

| Miejsce | Walidacja `KSEF_AUTH_TOKEN` |
|---------|----------------------------|
| `app/core/config.py` (`_validate_production_security`) | **Nie** — tylko JWT + DEBUG |
| `app/main.py` (`application_lifespan`) | **Nie** |
| `app/worker/__main__.py` (`main()`) | **Nie** |
| `PurchaseAuthService._authenticate_fresh()` | **Tak** — runtime `AppError` |
| `KSeFSessionService.open_session()` | **Tak** — runtime `AppError` |

Worker startuje bezwarunkowo:

```475:476:app/worker/__main__.py
    logger.info("Worker startuje. poll_interval=%ss batch=%s", POLL_INTERVAL_SECONDS, BATCH_SIZE)
    while _running:
```

Scheduler enqueue'uje job nawet bez tokena. Błąd pojawi się dopiero w jobie `sync_purchase_invoices`, gdy `ensure_purchase_auth()` nie znajdzie ważnego tokena w DB i spróbuje full auth.

### Propozycja minimalnej zmiany (fail-fast)

**Rekomendowane miejsce:** `app/worker/__main__.py` — na początku `main()`, przed pętlą:

```python
if settings.ksef_auto_sync_enabled and not (settings.ksef_auth_token or "").strip():
    raise SystemExit(
        "KSEF_AUTO_SYNC_ENABLED=true wymaga KSEF_AUTH_TOKEN w ENV workera."
    )
```

**Alternatywa (szersza):** rozszerzyć `_validate_production_security()` w `config.py` o ten sam warunek — wtedy fail-fast dotyczy też API przy `APP_ENV=production`.

### Wpływ na środowiska

| Środowisko | Wpływ |
|------------|-------|
| **Dev lokalny** | Brak — `KSEF_AUTO_SYNC_ENABLED` domyślnie `false` |
| **Staging z auto-sync OFF** | Brak |
| **Prod z auto-sync ON bez tokena** | **Pożądany fail** zamiast cichego fail jobów o 08:00/14:00 |
| **Prod bez auto-sync** | Brak — `open_session` nadal failuje runtime przy braku tokena |

### Ocena

- Obecnie: **late failure** (pierwszy slot schedulera lub pierwszy sync bez tokena w DB).
- Zalecenie: **minor fix przed deployem** — 3–5 linii w workerze, bez nowych mechanizmów.

---

## 2. `refresh_access_token()`

### Implementacja IFG

```71:95:app/integrations/ksef/auth.py
    def refresh_access_token(self, refresh_token: str) -> KSeFSession:
        ...
        return KSeFSession(
            access_token=data["accessToken"]["token"],
            refresh_token=refresh_token,
            access_valid_until=_parse_dt(data["accessToken"].get("validUntil")),
            refresh_valid_until=None,
        )
```

Kod **świadomie** ponownie używa przekazanego `refresh_token` zamiast czytać go z odpowiedzi.

### Co mówi API KSeF (dowody)

| Źródło | Treść |
|--------|-------|
| [CIRFMF/ksef-docs — uwierzytelnianie.md](https://github.com/CIRFMF/ksef-docs/blob/main/uwierzytelnianie.md) §5 | „Odpowiedź zawiera **nowy accessToken**” — bez wzmianki o nowym refreshToken |
| OpenAPI KSeF v2 — `POST /auth/token/refresh` | Schema odpowiedzi 200: **tylko `accessToken`** (token + validUntil) |
| OpenAPI — `POST /auth/token/redeem` | Zwraca **obie** pary: `accessToken` + `refreshToken` |

Oficjalna dokumentacja MF **nie gwarantuje** nowego `refreshToken` w odpowiedzi refresh. Refresh token może być używany wielokrotnie (do 7 dni) — redeem to inny endpoint.

### Czy warunkowy zapis `if response.refresh_token` jest potrzebny?

| Aspekt | Ocena |
|--------|-------|
| Zgodność z API MF dziś | Obecny kod **poprawny** — reużycie wejściowego refresh tokena |
| Warunek `if data.get("refreshToken")` | **Opcjonalny hardening** na przyszłość — nie wymagany przed deployem |
| `build_token_metadata()` w `_refresh_tokens` | Przekazuje `tokens.refresh_token` (stary) — OK |

### Drobna uwaga (post-deploy)

`build_token_metadata(..., refresh_valid_until=None)` **nadpisuje** `refresh_valid_until` na `null` w JSON. `refresh_token_valid()` wtedy traktuje brak daty jako „ważny” (`return True`). Nie blokuje syncu, ale osłabia precyzję wygaszania refresh tokena. Poprawka po deployu: zachować istniejące `refresh_valid_until` gdy odpowiedź refresh go nie zawiera.

---

## 3. Tabela `ksef_sessions`

### Model rozróżnienia

| `status` | `session_reference` | Semantyka |
|----------|---------------------|-----------|
| `auth_active` | `NULL` | Purchase auth only |
| `active` | ustawione | Online session (sprzedaż) |
| `expired` / `terminated` | dowolne | Historia |

Dodatkowy filtr online: `_get_active_online_session()` wymaga `session_reference IS NOT NULL`.

### Czy rozwiązanie jest akceptowalne?

**Tak** — dla obecnej skali i wymogu braku migracji:

- Jedna tabela, jeden NIP → jeden „aktywny” rekord logiczny (z upgrade path `auth_active` → `active`).
- Sprzedaż i zakupy mogą współdzielić tokeny na rekordzie `active` — zamierzone.
- Statusy historyczne (`expired`, `terminated`) mogą się kumulować — indeks `(nip, status)` istnieje.

### Ograniczenia za 1–2 lata

| Ograniczenie | Ryzyko |
|--------------|--------|
| Mieszanie semantyk w jednej tabeli | Nowy developer musi znać konwencję `auth_active` + `session_reference` |
| Wiele historycznych rekordów per NIP | Zapytania `order_by created_at desc limit 1` — OK przy małej liczbie NIPów |
| Brak osobnej audytowej ścieżki purchase vs sale auth | Trudniejsze raportowanie compliance bez filtrowania po status/metadata |
| `SESSION_ACTIVE` używany i dla online, i jako źródło tokenów w `PurchaseAuthService._find_purchase_auth_record` | Wymaga dyscypliny przy zmianach statusów |

### Czy warto kiedyś wydzielić storage?

**Tak, opcjonalnie w przyszłości** — gdy:

- wiele NIPów / wielu tenantów,
- potrzeba osobnych polityk retencji tokenów vs sesji online,
- osobne RBAC dla „connect sales” vs „background purchase sync”.

Na dziś **nie jest wymagane** — koszt migracji > korzyść przy jednym NIPie sprzedawcy.

---

## 4. `PurchaseAuthService` — jakość architektury

### SRP

| Odpowiedzialność | Gdzie |
|------------------|-------|
| Cykl życia tokenów zakupowych | `PurchaseAuthService` ✅ |
| Sesja online, szyfrowanie, submit | `KSeFSessionService` ✅ |
| Wspólne statusy / metadata | `ksef_token_store` ✅ |

Podział jest czytelny i testowalny.

### Ukryte zależności

| Problem | Ważność |
|---------|---------|
| `KSeFSessionService.open_session()` woła `purchase_auth._find_purchase_auth_record()` — **metoda prywatna** | Niska — coupling wewnątrz modułu KSeF |
| `PurchaseAuthService` szuka rekordów `SESSION_ACTIVE` bez `session_reference` check w query — polega na statusie | Akceptowalne przy obecnej konwencji |
| `PurchaseAuthService` nie importuje `KSeFSessionService` | ✅ Brak cyklu importów |

### Ryzyko wycieku odpowiedzialności

- `KSeFSessionService` nadal jest „fasadą” KSeF (sync, connection status, open/close) — **uzasadnione** dla API/UI.
- Logika auth zakupów **nie wraca** do `get_session_context()` — dobrze.
- `open_session()` duplikuje część flow auth (upgrade path) — akceptowalne jako orchestracja, nie duplikacja refresh.

**Wniosek:** Brak poważnych naruszeń SRP. Jedyna rekomendacja utrzymaniowa (post-deploy): publiczny `find_purchase_auth_record()` zamiast `_find_*`.

---

## 5. Test coverage — pełny przepływ schedulera

### Co jest pokryte

| Warstwa | Plik testowy | Zakres |
|---------|--------------|--------|
| Scheduler tick / enqueue | `test_ksef_auto_sync_scheduler.py` | `evaluate_tick()` — **bez** workera i bez auth |
| Purchase auth | `test_ksef_purchase_auth_service.py` | ensure / refresh / fallback |
| Sync incremental | `test_ksef_sync_service.py`, `test_ksef_purchase_sync_resume.py` | metadata + XML + resume 429 (mocki auth) |
| Delegacja w serwisie | `test_ksef_session_service.py::TestSyncReceivedInvoicesUsesPurchaseAuth` | `purchase_auth.ensure_purchase_auth` |
| Worker claim + handler | `test_background_job_claim.py` | `_process_batch` z **mockowanym** handlerem |
| Handler defer | `test_ksef_purchase_sync_resume.py` | `SyncPurchaseInvoicesJobHandler` z mock `sync_purchase_invoices` |

### Czego **nie ma**

Testu łączącego w jednym scenariuszu:

```
scheduler tick → enqueue → worker _process_batch
  → ensure_purchase_auth() [prawdziwy lub stub HTTP]
  → query_purchase_metadata_refs
  → get_purchase_invoice_xml
  → zapis InvoiceORM
```

**Brak potwierdzony** — najbliżej są testy resume z SQLite + mockowanym `purchase_auth`, ale bez schedulera i bez pełnego łańcucha auth→import w workerze.

Ryzyko operacyjne jest **umiarkowane** — warstwy są testowane osobno; luka to integracja między nimi.

---

## 6. Deploy readiness — decyzja

### **B) READY AFTER MINOR FIXES**

### Uzasadnienie

| Kryterium | Status |
|-----------|--------|
| Architektura GWO-IFG-0032 | ✅ Zaimplementowana zgodnie z designem |
| Bezpieczeństwo sprzedaży | ✅ Online session nadal wymagana |
| Backward compatibility | ✅ Bez migracji DB |
| Testy jednostkowe | ✅ 70 passed |
| Guardian | ✅ OK |
| Fail-fast ENV | ⚠️ Brak — ryzyko operacyjne przy auto-sync |
| Refresh token handling | ✅ Zgodne z API MF; drobna poprawka `refresh_valid_until` opcjonalna |
| Test E2E schedulera | ⚠️ Brak — nie blokuje przy pokryciu warstwowym |

**Nie jest NOT READY** — kod produkcyjny jest spójny.  
**Nie jest czysto READY FOR PRODUCTION** — bez fail-fast lub potwierdzenia `KSEF_AUTH_TOKEN` w ENV workera deploy auto-sync jest ryzykowny.

### Warunek przejścia na A) READY FOR PRODUCTION

- Deploy **po** dodaniu fail-fast w workerze (3–5 linii), **lub**
- Pisemne potwierdzenie ops: `KSEF_AUTH_TOKEN` ustawiony w ENV workera DS723+ **i** `KSEF_AUTO_SYNC_ENABLED=true`.

---

## Oceny końcowe

| Metryka | Wartość |
|---------|---------|
| **Ocena architektury** | **8 / 10** |
| **Ocena ryzyka wdrożenia** | **Niskie–średnie** (zależne od ENV; bez tokena = średnie) |

### Blockery deployu

**Brak blockerów kodowych**, pod warunkiem:

1. `KSEF_AUTH_TOKEN` obecny w ENV workera produkcyjnego.
2. Guardian green przed deployem.
3. Akceptacja braku testu E2E pełnego łańcucha.

### Zalecane poprawki **przed** deployem (minor)

1. Fail-fast w `app/worker/__main__.py` gdy `KSEF_AUTO_SYNC_ENABLED && !KSEF_AUTH_TOKEN`.

### Zalecane poprawki **po** deployie

1. Zachowanie `refresh_valid_until` w `build_token_metadata` przy refresh (gdy response nie zwraca daty).
2. Publiczna metoda zamiast `_find_purchase_auth_record` w `open_session`.
3. Test integracyjny: scheduler enqueue → worker → auth stub → import 1 faktury.
4. Monitoring pierwszych slotów: `SCHEDULER_ENQUEUE` → `KSEF_ASYNC_SYNC_WORKER_DONE` / `PURCHASE_IMPORT_SUMMARY`.
5. Opcjonalnie: warunek `if data.get("refreshToken")` w `refresh_access_token()` — forward-compatible.

---

## Lista wykonanych analiz

1. Przegląd `app/core/config.py`, `app/main.py`, `app/worker/__main__.py` — startup validation ENV.
2. Analiza `app/integrations/ksef/auth.py::refresh_access_token()` vs dokumentacja MF (ksef-docs, OpenAPI v2).
3. Analiza `app/services/ksef_purchase_auth_service.py` i `app/services/ksef_token_store.py`.
4. Analiza `app/services/ksef_session_service.py` — podział online vs purchase, upgrade path.
5. Przegląd modelu `app/persistence/models/ksef_session.py` i zapytań `_get_active_online_session`.
6. Przegląd `app/worker/job_handlers/sync_purchase_invoices.py` i schedulera.
7. Inwentaryzacja testów: `test_ksef_*`, `test_background_job_claim.py`.
8. Weryfikacja Guardian `ksef check` (exit 0).
9. Ocena SRP, coupling i braku cykli importów między serwisami.

---

## A. Root cause (review)

Główne pozostałe ryzyko to **operacyjne**, nie architektoniczne: worker startuje z włączonym auto-sync bez walidacji `KSEF_AUTH_TOKEN`, co odkrywa problem dopiero przy pierwszym jobie.

## B. Zmienione pliki (review)

**Brak zmian kodu w ramach tego review** — tylko dokument.

## C. Deploy

**Nie wykonano** (zgodnie z wymaganiami).

## D. Testy

```bash
python -m pytest tests/unit/test_ksef_purchase_auth_service.py \
  tests/unit/test_ksef_session_service.py \
  tests/unit/test_ksef_sync_service.py \
  tests/unit/test_ksef_purchase_sync_resume.py \
  tests/unit/test_ksef_poll_session_lookup.py \
  tests/unit/test_ksef_session_worker.py -q
# 70 passed (stan referencyjny implementacji)
```

## E. Następny krok

1. Zastosować fail-fast w workerze **lub** potwierdzić ENV produkcyjny.
2. Deploy backend + worker (bez migracji).
3. Obserwacja pierwszego slotu auto-sync po deployu.
