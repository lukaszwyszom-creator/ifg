# KSeF „Odśwież KSeF” — naprawa UX synchronizacji zakupów

Data: 2026-05-22

## Problem

Przycisk **„Odśwież KSeF”** kręcił się długo (minuty) i kończył błędem w UI, mimo że backend potrafił dokończyć import (np. `ksef_returned=33`, `created=20`, `errors=0`).

## Przyczyna błędu UI

1. Oba komponenty UI wywoływały **`ksefApi.syncPurchasesNow()`** → synchroniczny **`POST /api/v1/ksef/sync/purchases`**.
2. Globalny axios w `frontend-react/src/api/client.js` ma **`timeout: 30000`** (30 s).
3. Import zakupów trwa znacznie dłużej (metadata + pobieranie XML + retry 429/401) → klient przerywa request (`ECONNABORTED`) → UI pokazywało **„Błąd”**, choć serwer mógł nadal pracować lub zakończyć import poprawnie.
4. Istniejący fallback na async job uruchamiał się **tylko przy HTTP 404**, nie przy timeout — więc w produkcji (endpoint 200) użytkownik zawsze trafiał w ścieżkę synchroniczną.

## Rozwiązanie

Przełączenie głównego przepływu UI na **asynchroniczny job**:

| Krok | Endpoint | Opis |
|------|----------|------|
| 1 | `POST /api/v1/ksef-sessions/sync-purchase` | Natychmiast **202** + `job_id` |
| 2 | `GET /api/v1/ksef-sessions/sync-purchase/jobs/{job_id}` | Polling co 3 s, max ~6 min |
| 3 | (opcjonalnie) `GET /api/v1/ksef/sync/status` | Odświeżenie metadanych sync po zakończeniu |

**Fallback** (tylko gdy job API zwraca **404**): synchroniczny `POST /api/v1/ksef/sync/purchases` z **`timeout: 600000`** — bez fałszywego „w tle” po 30 s.

> **Aktualizacja (force async):** patrz `docs/KSEF_FORCE_ASYNC_PURCHASE_SYNC.md` — `runPurchaseSync()` zawsze woła `syncPurchaseInvoices()` + polling; fallback sync **wyłącznie** przy 404 na enqueue (nie przy timeout/429/500).

### Czy async używa sync v2?

**Tak, dla pobierania z KSeF.** Worker `sync_purchase_invoices` wywołuje `KSeFSessionService.sync_received_invoices()`, które korzysta z `ksef_client.query_received_invoices()` — tej samej ścieżki metadata + download XML co sync produkcyjny.

**Różnica względem sync synchronicznego:**

| Aspekt | Sync synchroniczny | Async job |
|--------|-------------------|-----------|
| Pobieranie KSeF | `query_received_invoices` (v2) | `query_received_invoices` (v2) |
| Okno dat | `days_back` z ustawień (domyślnie 90) | UI wysyła `date_from`/`date_to` (90 dni) |
| `KSeFSyncStateRepository` | `mark_running` / `mark_success` | `mark_running` / `mark_success` (po patchu workera) |
| `GET /ksef/sync/status` | pokazuje `running` → `success` | status może pozostać bez zmian podczas joba |

Nie przepinano workera na `sync_purchase_invoices()` — to osobna, większa zmiana backendu; import faktur działa poprawnie na v2.

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `frontend-react/src/api/ksef.js` | `runPurchaseSync()`, polling joba, normalizacja liczników, fallback sync z długim timeoutem |
| `frontend-react/src/components/layout/KSeFTopbarInfo.jsx` | Async flow + komunikaty „uruchomiona / trwa” |
| `frontend-react/src/components/dashboard/KSeFSessionBar.jsx` | j.w. |
| `frontend-react/src/api/ksef.purchase-sync.test.mjs` | Testy regresji (źródło) |
| `docs/KSEF_SYNC_REFRESH_UX_FIX.md` | Ten raport |

**Bez zmian:** `app/api/routers/ksef_session.py`, worker, parser FA(3), KSeF client metadata/download.

## Używany endpoint (po fixie)

- **Primary (async):** `POST /api/v1/ksef-sessions/sync-purchase` + `GET .../jobs/{job_id}`
- **Fallback:** `POST /api/v1/ksef/sync/purchases` (tylko 404 na job API)
- **Status (display):** `GET /api/v1/ksef/sync/status` — odświeżany po zakończeniu, nie jako główny mechanizm pollingu joba

## Testy

### Automatyczne (frontend, bez buildu)

```bash
node --test frontend-react/src/api/ksef.purchase-sync.test.mjs
```

Sprawdza: obecność `runPurchaseSync`, preferencję job API, brak `syncPurchasesNow` w komponentach, wydłużony timeout fallbacku.

### Ręczna weryfikacja

1. Zaloguj się, upewnij się że sesja KSeF = **CONNECTED**.
2. Kliknij **„Odśwież KSeF”** w topbarze lub Advanced Dashboard.
3. **Oczekiwane:**
   - Spinner tylko przez ~1 s (enqueue).
   - Komunikat **„Synchronizacja uruchomiona…”** → **„Synchronizacja trwa…”**.
   - Przycisk pokazuje **„Sync…”** / **„Sync trwa…”**, nie kręci się przez cały import.
   - Po zakończeniu: **„+N”** (topbar) lub pełny raport liczników (session bar).
   - Lista faktur zakupowych odświeża się automatycznie.
4. **Brak fałszywego błędu** po ~30 s (wcześniejszy timeout axios).
5. W DevTools → Network: brak długiego wiszącego `POST /ksef/sync/purchases` (chyba że backend bez job API → fallback).
6. Przy działającym workerze: `GET .../jobs/{id}` przechodzi `pending` → `processing` → `done`.

### Wymagania środowiska

- **Worker** musi być uruchomiony, inaczej job zostanie w `pending` do timeoutu poll (~6 min) — wtedy UI pokaże komunikat o przekroczeniu czasu (bez fałszywego sukcesu „w tle”).

## Rebuild

| Warstwa | Wymagany rebuild? |
|---------|-------------------|
| **Frontend** | **Tak** — zmiany tylko w React (`npm run build` / redeploy frontend) |
| **Backend** | **Nie** — wykorzystano istniejące endpointy jobowe |
