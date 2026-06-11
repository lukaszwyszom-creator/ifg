# KSeF — wymuszenie async job w „Odśwież KSeF”

Data: 2026-05-22

## Problem produkcyjny

Po kliknięciu **„Odśwież KSeF”** UI pokazywało **„Błąd”** po ~10–20 s.

Obserwacje:
- W logach API **brak** `POST /api/v1/ksef-sessions/sync-purchase`
- Worker działa, ale **nie dostaje joba**
- Wskazuje to na stary bundle frontendu lub przypadkowy fallback na synchroniczny sync (timeout axios 30 s)

## Przyczyna

1. Stary frontend mógł nadal wołać `syncPurchasesNow()` → `POST /ksef/sync/purchases` (blokujący, timeout 30 s).
2. Wcześniejsza wersja `runPurchaseSync()` owijała enqueue **i polling** w jednym `try/catch` — teoretycznie błąd poll mógł być mylony ze ścieżką fallback (naprawione przez rozdzielenie bloków).

## Rozwiązanie

### Diagnostyka E2E (aktualizacja)

Patrz **`docs/KSEF_ASYNC_SYNC_E2E_DIAGNOSTIC.md`** — logi `KSEF_ASYNC_SYNC_*` (API/worker), `[ksef-purchase-sync]` (frontend), Guardian `--ksef-async-check`, tabela „gdzie ginie request”.

### Jedyny punkt wejścia UI

Komponenty używają **`ksefApi.runPurchaseSync()`** — bez bezpośredniego `syncPurchasesNow()`.

### Przepływ `runPurchaseSync()`

```
1. syncPurchaseInvoices(nip, dateFrom, dateTo)
   → POST /api/v1/ksef-sessions/sync-purchase
2. poll getSyncPurchaseJobStatus(jobId) co 3 s
3. TYLKO jeśli krok 1 → HTTP 404:
   syncPurchasesNowFallback → POST /ksef/sync/purchases (timeout 600000)
```

**Nie** fallbackuje przy: 429, 500, timeout, ECONNABORTED, błędach pollingu.

### Diagnostyka (dev)

W trybie Vite dev konsola loguje:
```
[ksef-purchase-sync] enqueue { nip, dateFrom, dateTo }
[ksef-purchase-sync] async-started { jobId }
[ksef-purchase-sync] async-done { jobId, status }
```

W produkcji: DevTools → Network → pierwszy request to **`POST .../ksef-sessions/sync-purchase`**.

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `frontend-react/src/api/ksef.js` | Rozdzielony enqueue/poll/fallback; jawne `syncPurchaseInvoices` + `getSyncPurchaseJobStatus`; log dev |
| `frontend-react/src/components/layout/KSeFTopbarInfo.jsx` | Komentarz ścieżki (już używa `runPurchaseSync`) |
| `frontend-react/src/components/dashboard/KSeFSessionBar.jsx` | j.w. |
| `frontend-react/src/api/ksef.purchase-sync.test.mjs` | Testy: brak `syncPurchasesNow` w UI, fallback tylko 404 |
| `docs/KSEF_SYNC_REFRESH_UX_FIX.md` | Odnośnik do tego raportu |

## Testy

```bash
node --test frontend-react/src/api/ksef.purchase-sync.test.mjs
```

Sprawdza:
- `runPurchaseSync` → `syncPurchaseInvoices` + polling
- brak `syncPurchasesNow(` w komponentach
- fallback sync tylko przy `404` na enqueue
- brak fallbacku w sekcji pollingu

## Ryzyko wdrożenia

| Ryzyko | Ocena | Uwagi |
|--------|-------|-------|
| Stary bundle w produkcji | **Wysokie** | **Wymagany rebuild + redeploy frontendu** — bez tego fix nie działa |
| Worker nie działa | **Średnie** | Job zostanie w `pending`; UI pokaże timeout po ~6 min (nie fałszywy sync) |
| Backend bez job API (404) | **Niskie** | Fallback sync z długim timeoutem — jak wcześniej |
| Błąd enqueue (401/422/500) | **Niskie** | UI pokaże błąd od razu — bez cichego fallbacku |

## Weryfikacja po deploy

1. Klik „Odśwież KSeF”
2. Network: `POST /api/v1/ksef-sessions/sync-purchase` → **202** + `job_id`
3. Następnie cykliczne `GET .../jobs/{id}`
4. Worker log: `Job ... (sync_purchase_invoices) zakończony`
5. Brak długiego `POST /ksef/sync/purchases` (chyba że backend bez job API)
