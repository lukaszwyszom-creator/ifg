# KSeF async sync — diagnostyka E2E

Data: 2026-05-22

## Cel

Jednoznacznie ustalić, gdzie ginie request „Odśwież KSeF”, bez zgadywania (stary bundle vs brak POST vs worker vs polling).

## Zmienione pliki

| Warstwa | Plik | Zmiana |
|---------|------|--------|
| Frontend | `frontend-react/src/api/ksef.js` | Logi `[ksef-purchase-sync]`, `formatPurchaseSyncError`, metadane błędu |
| Frontend | `KSeFTopbarInfo.jsx`, `KSeFSessionBar.jsx` | „Uruchamiam async sync…”, konkretny komunikat błędu |
| Backend | `app/api/routers/ksef_session.py` | `KSEF_ASYNC_SYNC_ENQUEUE`, `KSEF_ASYNC_SYNC_JOB_STATUS` |
| Worker | `app/worker/job_handlers/sync_purchase_invoices.py` | `KSEF_ASYNC_SYNC_WORKER_START/DONE/ERROR` |
| Guardian | `scripts/guardian.py` | `--ksef-async-check` |
| Test | `frontend-react/src/api/ksef.purchase-sync.test.mjs` | Skan wszystkich komponentów |

## Ścieżka requestu (frontend → API → worker)

```
[UI] Klik „Odśwież KSeF”
  → komunikat „Uruchamiam async sync…”
  → console.info [ksef-purchase-sync] enqueue { endpoint, nip, dateFrom, dateTo }

[Browser] POST /api/v1/ksef-sessions/sync-purchase
  → [API log] KSEF_ASYNC_SYNC_ENQUEUE nip=... date_from=... date_to=... job_id=...
  → HTTP 202 { job_id }

[Browser] console.info [ksef-purchase-sync] enqueue-ok { ..., jobId }
  → polling co 3 s: GET /api/v1/ksef-sessions/sync-purchase/jobs/{job_id}
  → [API log] KSEF_ASYNC_SYNC_JOB_STATUS job_id=... status=pending|processing|done|failed

[Worker] pobiera job sync_purchase_invoices
  → [Worker log] KSEF_ASYNC_SYNC_WORKER_START job_id=...
  → sync_purchase_invoices() (bez zmian logiki KSeF)
  → [Worker log] KSEF_ASYNC_SYNC_WORKER_DONE job_id=... saved=... received=...

[Browser] GET job status → done → odświeżenie listy faktur
```

**Fallback** (tylko HTTP **404** na POST enqueue): `POST /api/v1/ksef/sync/purchases` (timeout 600 s) + log `fallback-404`.

## Gdzie request ginie — tabela decyzyjna

| Objaw | Gdzie szukać | Interpretacja |
|-------|--------------|---------------|
| Brak `[ksef-purchase-sync] enqueue` w konsoli przeglądarki | Frontend / stary bundle | JS nie wykonuje `runPurchaseSync` — rebuild/redeploy static |
| Jest `enqueue`, brak `enqueue-ok`, błąd w UI `422/401 …` | Network → POST sync-purchase | Request doszedł do API; napraw auth/body/sesję |
| Jest `enqueue-ok`, brak `KSEF_ASYNC_SYNC_ENQUEUE` w logach API | Reverse proxy / inny host API | Frontend trafia na inny backend niż oglądane logi |
| Jest `ENQUEUE`, brak `WORKER_START` | Worker / DB jobs | Worker nie polluje jobów lub job nie zapisany |
| Jest `WORKER_START`, brak `WORKER_DONE` | Worker / KSeF sync | Błąd importu — `WORKER_ERROR` |
| Jest `WORKER_DONE`, UI błąd | Polling GET job status | Sprawdź `JOB_STATUS` i odpowiedź JSON |

## Guardian — kontrola przed/po deploy

```bash
python3 scripts/guardian.py --ksef-async-check
```

Sprawdza:
- brak `syncPurchasesNow(` w `frontend-react/src/components/**`
- `runPurchaseSync` + fallback 404 w `ksef.js`
- `runPurchaseSync` w `frontend-react/dist/assets/*.js`
- brak `syncPurchasesNow(!1` w dist
- `/api/v1/ksef-sessions/sync-purchase` w openapi.json

## Procedura deployu DS723+

```bash
# Na Mac mini — commit/push (jeśli potrzebny)
git push origin production

# Na DS723+
ssh ds723
cd /volume1/docker/ifg_v2/ifg_standalone
git pull origin production

# Backend + worker (logi KSEF_ASYNC_SYNC)
cd docker
sudo docker compose -f docker-compose.prod.yml build api
sudo docker compose -f docker-compose.prod.yml up -d api worker

# Frontend — WAŻNE: dist musi trafić do serwowanej ścieżki
cd ../frontend-react
npm ci
npm run build
# upewnij się, że nginx/proxy serwuje frontend-react/dist (nie stary katalog)

python3 ../scripts/guardian.py --ksef-async-check
python3 ../scripts/guardian.py --deploy-check
```

## Procedura testu po deployu

1. Otwórz aplikację → DevTools → Console + Network.
2. Klik **„Odśwież KSeF”**.
3. **Console:** `Uruchamiam async sync…` → `[ksef-purchase-sync] enqueue` → `enqueue-ok` z `jobId`.
4. **Network:** `POST .../ksef-sessions/sync-purchase` → **202**; potem `GET .../jobs/{id}`.
5. **API logs:**
   ```bash
   sudo docker compose -f docker/docker-compose.prod.yml logs -f api | grep KSEF_ASYNC_SYNC
   ```
6. **Worker logs:**
   ```bash
   sudo docker compose -f docker/docker-compose.prod.yml logs -f worker | grep KSEF_ASYNC_SYNC
   ```
7. Oczekiwana sekwencja: `ENQUEUE` → `WORKER_START` → `JOB_STATUS processing` → `WORKER_DONE` → `JOB_STATUS done`.
8. Przy błędzie UI: komunikat `{status} {endpoint}: {message}` (np. `401 /api/v1/ksef-sessions/sync-purchase: ...`).

## Powiązane dokumenty

- `docs/KSEF_FORCE_ASYNC_PURCHASE_SYNC.md` — wymuszenie async w kodzie źródłowym
- `docs/KSEF_SYNC_REFRESH_UX_FIX.md` — pierwotna naprawa UX timeoutu
