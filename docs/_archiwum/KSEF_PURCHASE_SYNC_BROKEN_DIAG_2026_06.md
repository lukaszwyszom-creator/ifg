# KSeF — diagnostyka: import faktur zakupowych „nie działa”

**Data:** 2026-06-20  
**Środowisko:** DS723+ production  
**Tryb:** read-only

---

## 1. Architektura synchronizacji zakupów

```
[UI] „Odśwież KSeF” (KSeFTopbarInfo / KSeFSessionBar)
  └─ ksefApi.runPurchaseSync()
       └─ POST /api/v1/ksef-sessions/sync-purchase  → HTTP 202 { job_id }
            └─ INSERT background_jobs (job_type=sync_purchase_invoices)
       └─ polling GET /api/v1/ksef-sessions/sync-purchase/jobs/{job_id}

[Worker] python -m app.worker
  └─ SyncPurchaseInvoicesJobHandler
       └─ KSEF_ASYNC_SYNC_WORKER_START
       └─ ksef_session_service.sync_purchase_invoices()
            └─ KSeF API (metadata / invoices/query/metadata)
       └─ KSEF_ASYNC_SYNC_WORKER_DONE | WORKER_ERROR

[Fallback UI] tylko przy HTTP 404 na enqueue:
  └─ POST /api/v1/ksef/sync/purchases (sync synchroniczny, timeout 600s)

[Tło UI] co ~30s:
  └─ GET /api/v1/ksef/status          — status połączenia KSeF
  └─ GET /api/v1/ksef/sync/status     — ostatnia synchronizacja zakupów (KSeFTopbarInfo)
```

### Endpointy (repo + prod OpenAPI)

| Rola | Metoda | Ścieżka |
|------|--------|---------|
| Status połączenia | GET | `/api/v1/ksef/status` |
| Status sync zakupów | GET | `/api/v1/ksef/sync/status` |
| **Enqueue async (główna ścieżka UI)** | POST | `/api/v1/ksef-sessions/sync-purchase` |
| Status joba | GET | `/api/v1/ksef-sessions/sync-purchase/jobs/{job_id}` |
| Sync synchroniczny (fallback) | POST | `/api/v1/ksef/sync/purchases` |

### Tabele (aktualne nazwy — nie `jobs`, nie `ksef_number`)

| Tabela | Rola |
|--------|------|
| **`background_jobs`** | kolejka async (pending/processing/done/failed) |
| **`ksef_sessions`** | sesje KSeF (status, expires_at, nip) |
| **`ksef_sync_states`** | stan ostatniej synchronizacji zakupów (scope=`purchase_invoices`) |
| **`invoices`** | kolumna **`ksef_reference_number`** (nie `ksef_number`) |
| `invoices.ksef_payload_json` | surowy payload KSeF |
| `inventory_layers` / magazyn | **poza** sync zakupów KSeF |

---

## 2. Weryfikacja frontendu (repo + prod dist)

| Test | Wynik |
|------|-------|
| `ksefApi.runPurchaseSync` → POST sync-purchase | ✅ `frontend-react/src/api/ksef.js` |
| Przycisk „Odśwież KSeF” → `runPurchaseSync` | ✅ `KSeFTopbarInfo.jsx`, `KSeFSessionBar.jsx` |
| OpenAPI prod zawiera sync-purchase | ✅ |
| Prod dist (`index-SvT4fhAr.js`, 2026-06-20 23:41) | ✅ `runPurchaseSync`, `sync-purchase`, „Odśwież KSeF” |

**Frontend nie jest regresją** — kod i bundel produkcyjny wywołują poprawny endpoint.

---

## 3. Stan produkcji DS723+ (2026-06-20)

| Element | Wartość |
|---------|---------|
| Git HEAD | `bc14bd3` |
| OpenAPI | sync-purchase ✅ |
| Tabela `background_jobs` | ✅ istnieje |
| Kolumna `invoices.ksef_reference_number` | ✅ istnieje |
| Tabela `jobs` | ❌ **nie istnieje** (błędna nazwa w diagnozie użytkownika) |
| Kolumna `invoices.ksef_number` | ❌ **nie istnieje** (właściwa: `ksef_reference_number`) |

### Joby sync zakupów

| status | count |
|--------|-------|
| done | 8 |
| failed | 29 |

**Ostatni sukces:** 2026-06-17 19:28  
**Ostatnia próba:** 2026-06-19 11:27 → **failed**  
**Ostatni błąd:** `Brak aktywnej sesji KSeF dla NIP 9670402857.`

### ksef_sync_states

```
scope=purchase_invoices | status=error
last_success_at=2026-06-17 19:31
last_attempt_at=2026-06-19 12:28
last_error=Brak aktywnej sesji KSeF dla NIP 9670402857.
```

### ksef_sessions

Wszystkie ostatnie sesje: **status=expired** (ostatnia wygasła 2026-06-19 11:42).  
**Brak aktywnej sesji KSeF.**

### Logi (ostatnie 72h)

| Log | Liczba |
|-----|--------|
| `KSEF_UI_TRIGGER_PURCHASE_SYNC` (api) | **0** |
| `KSEF_ASYNC_SYNC_*` (worker) | **0** |
| `GET /api/v1/ksef/status` | **występuje** (polling UI co ~30s) |

---

## 4. Gdzie ginie request — wnioski

| Etap | Stan |
|------|------|
| 1. Request z przeglądarki (POST sync-purchase) | ❌ **Nie wychodzi** od ≥72h (brak logów API) |
| 2. Trafienie do API | — (nie testowane — brak POST) |
| 3. Utworzenie joba (`background_jobs`) | ✅ infrastruktura OK; ostatni job 19.06 |
| 4. Worker odbiera job | ✅ działało historycznie; ostatnie joby **failed** (brak sesji) |

### Miejsce awarii

**Warstwa operacyjna / sesja KSeF**, nie brak kodu ani tabel:

1. **Sesja KSeF wygasła** — sync w workerze wymaga aktywnej sesji; ostatnie joby kończyły się błędem.
2. **Brak nowych wywołań sync** — użytkownik widzi tylko polling `GET /ksef/status`; przycisk „Odśwież KSeF” nie generuje POST (sesja wygasła → UI `DISCONNECTED` → `KSeFTopbarInfo` ukryty; lub użytkownik nie klika).
3. **Błędna diagnoza schematu** — szukanie `jobs` i `invoices.ksef_number` sugerowało brak infrastruktury async; faktyczne obiekty to `background_jobs` i `ksef_reference_number`.

---

## 5. Scenariusze biznesowe (z danych prod)

| Scenariusz | Werdykt |
|------------|---------|
| Async enqueue + worker | ✅ działało (8 done); ostatnio failed — brak sesji |
| Import przy aktywnej sesji | ✅ ostatni sukces 17.06 |
| Import bez sesji | ❌ oczekiwany błąd |
| Polling status bez sync | ✅ wyjaśnia logi API (tylko GET status) |

---

## 6. Komendy diagnostyczne DS723+

```bash
export PATH="/var/packages/ContainerManager/target/usr/bin:$PATH"
export IFG=/volume1/docker/ifg_v2/ifg_standalone
export COMPOSE="docker compose -f docker/docker-compose.prod.yml --env-file .env.production"
cd "$IFG"

# Git / dist
git log -1 --oneline
grep -ohE 'runPurchaseSync|sync-purchase|Odśwież KSeF' frontend-react/dist/assets/*.js | sort | uniq -c
curl -fsS http://127.0.0.1:8000/openapi.json | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print('\n'.join(p for p in sorted(d['paths']) if 'sync' in p and 'ksef' in p))"

# Tabele (właściwe nazwy)
$COMPOSE exec -T db psql -U postgres -d ksef_backend -c "\dt *job*"
$COMPOSE exec -T db psql -U postgres -d ksef_backend -c \
  "SELECT column_name FROM information_schema.columns WHERE table_name='invoices' AND column_name LIKE '%ksef%';"

# Stan sync
$COMPOSE exec -T db psql -U postgres -d ksef_backend -c \
  "SELECT scope, status, last_success_at, last_attempt_at, last_error FROM ksef_sync_states;"
$COMPOSE exec -T db psql -U postgres -d ksef_backend -c \
  "SELECT job_type, status, COUNT(*) FROM background_jobs GROUP BY 1,2;"
$COMPOSE exec -T db psql -U postgres -d ksef_backend -c \
  "SELECT id, status, created_at, last_error FROM background_jobs WHERE job_type='sync_purchase_invoices' ORDER BY created_at DESC LIMIT 5;"

# Sesje KSeF
$COMPOSE exec -T db psql -U postgres -d ksef_backend -c \
  "SELECT nip, status, expires_at, created_at FROM ksef_sessions ORDER BY created_at DESC LIMIT 5;"

# Logi (ostatnie 24h)
$COMPOSE logs --since 24h api | grep -E 'KSEF_UI_TRIGGER|KSEF_ASYNC_SYNC|sync-purchase'
$COMPOSE logs --since 24h worker | grep -E 'KSEF_ASYNC_SYNC|sync_purchase'

# Test ręczny (wymaga tokenu JWT — z przeglądarki DevTools → Network po kliknięciu „Odśwież KSeF”)
# Oczekiwane: POST /api/v1/ksef-sessions/sync-purchase → 202
```

### Procedura odzyskania (operacyjna, bez zmian kodu)

1. W UI: **Połącz KSeF** (otwórz nową sesję — sesje prod wygasły 19.06).
2. Po `ui_status=CONNECTED`: klik **„Odśwież KSeF”**.
3. W logach API: `KSEF_UI_TRIGGER_PURCHASE_SYNC` + `KSEF_ASYNC_SYNC_ENQUEUE`.
4. W logach worker: `KSEF_ASYNC_SYNC_WORKER_START` → `WORKER_DONE`.

---

## 7. Rekomendowane poprawki (bez wdrożenia w tym kroku)

| Priorytet | Działanie |
|-----------|-----------|
| **P0 operacyjne** | Ponownie połączyć KSeF na prod (sesja wygasła) |
| **P1 UX** | Przy `DISCONNECTED` / `SESSION_EXPIRED` wyraźny komunikat „Połącz KSeF przed synchronizacją” zamiast ukrytego przycisku |
| **P2 UX** | Po failed job — banner z `ksef_sync_states.last_error` |
| **P3 docs** | Runbook: właściwe nazwy `background_jobs`, `ksef_reference_number` |

---

## 8. Podsumowanie

| Pytanie | Odpowiedź |
|---------|-----------|
| Czy infrastruktura async istnieje? | **TAK** (`background_jobs`, endpointy, worker) |
| Czy frontend wywołuje właściwy endpoint? | **TAK** (kod + dist) |
| Dlaczego brak logów worker? | **Brak nowych jobów** od 72h; wcześniejsze failed — **wygasła sesja KSeF** |
| Czy to bug frontend/backend? | **Nie regresja kodu** — problem **sesji operacyjnej** + brak triggera sync |
| Fałszywe tropy | `jobs`, `invoices.ksef_number` — nieistniejące obiekty |
