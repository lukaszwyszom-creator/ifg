# KSeF — trigger sync zakupów + UI listy zakupów

Data: 2026-05-22

---

## Problem

1. Po kliknięciu „Odśwież KSeF” / połączeniu z KSeF sesja powstaje poprawnie.
2. Nie było wywołania synchronizacji zakupów — brak joba w workerze.
3. W logach brak `KSEF_ASYNC_SYNC_ENQUEUE` / `KSEF_ASYNC_SYNC_WORKER_START`.
4. Lista zakupów pokazywała błędne numery (`number_local` w formacie IFG zamiast P_2 / ref KSeF).
5. Faktury majowe z bazy nie pojawiały się w UI po syncu.

---

## Przyczyny

### A. Sync nie startował

| Objaw | Przyczyna |
|-------|-----------|
| Sesja OK, brak POST sync | UI woła **`POST /api/v1/ksef-sessions/sync-purchase`**, nie `/ksef/sync/purchases`. Szukanie tylko drugiego endpointu w logach daje fałszywy negatyw. |
| Klik „Połącz” na kafelku KSeF | `KSeFConnectionTile` otwierał sesję, **bez** enqueue sync i **bez** `setSellerNip`. |
| Klik „Odśwież KSeF” w topbarze | `KSeFTopbarInfo.handleSyncPurchase` robił **ciche `return`** gdy `sellerNip` pusty (`if (!sellerNip \|\| …) return`), mimo `ui_status === 'CONNECTED'`. |

### B. Numery zakupów

`InvoiceCardList` wyświetlał surowe `number_local`. W części rekordów (historyczne dane / stary `mark_as_ready`) kolumna zawiera format IFG (`01/05/2026`, `FV/n/mm/yyyy`) zamiast numeru dostawcy z P_2.

### C. Brak majowych faktur w UI

1. **`refreshAllInvoicePools`** odświeżało tylko **już załadowane** pule z cache. Po pierwszym syncu, jeśli użytkownik nie otworzył zakładki „Faktury zakupowe”, pula `purchase` była pusta → refresh nic nie robił.
2. Filtr miesiąca w `useAppStore.filters.month` ogranicza widok do wybranego miesiąca (domyślnie bieżący). Faktury z innego miesiąca są w DB, ale poza filtrem UI.

---

## Naprawa

| Plik | Zmiana |
|------|--------|
| `KSeFTopbarInfo.jsx` | Rozwiązywanie NIP (store → settings → aktywna sesja); komunikat błędu zamiast cichego return; `KSEF_UI_TRIGGER_PURCHASE_SYNC` |
| `KSeFConnectionTile.jsx` | `setSellerNip` po connect; auto `runPurchaseSync` → `ksef:invoices-synced`; log trigger |
| `KSeFSessionBar.jsx` | Log `KSEF_UI_TRIGGER_PURCHASE_SYNC` |
| `ksef.js` | `logKsefUiTriggerPurchaseSync()` + log na początku `runPurchaseSync` |
| `useAppStore.js` | `refreshAllInvoicePools` ładuje sale/purchase z bieżącymi filtrami gdy cache pusty |
| `InvoiceCardList.jsx` | `getPurchaseDisplayNumber`: P_2 gdy nie-IFG; fallback `ksef_reference_number` |
| `ksef_session.py` | Log `KSEF_UI_TRIGGER_PURCHASE_SYNC` na enqueue async i sync synchroniczny |

---

## Oczekiwany przepływ po fixie

```
[UI] Połącz / Odśwież KSeF
  → console: KSEF_UI_TRIGGER_PURCHASE_SYNC { nip, source }
  → POST /api/v1/ksef-sessions/sync-purchase
  → API log: KSEF_UI_TRIGGER_PURCHASE_SYNC … mode=async
  → API log: KSEF_ASYNC_SYNC_ENQUEUE … job_id=…
  → Worker: KSEF_ASYNC_SYNC_WORKER_START
  → event ksef:invoices-synced → refresh puli (także purchase jeśli cache pusty)
```

Fallback synchroniczny (`POST /ksef/sync/purchases`) tylko przy HTTP **404** na enqueue.

---

## Test plan

1. **DevTools Console** — klik „Odśwież KSeF” → `KSEF_UI_TRIGGER_PURCHASE_SYNC` + `[ksef-purchase-sync] enqueue`.
2. **Network** — `POST …/ksef-sessions/sync-purchase` → **202**; polling `GET …/jobs/{id}`.
3. **API logs** — `grep KSEF_UI_TRIGGER_PURCHASE_SYNC` oraz `grep KSEF_ASYNC_SYNC`.
4. **Worker logs** — `KSEF_ASYNC_SYNC_WORKER_START` → `WORKER_DONE`.
5. **Numery** — zakładka zakupów: numer dostawcy (P_2) lub ref KSeF, nie `01/mm/yyyy`.
6. **Maj** — ustaw filtr miesiąc = maj, odśwież po syncu; nowe faktury widoczne bez ręcznego F5 całej aplikacji.

---

## Uwagi

- Mobile-expo nie ma przycisku „Odśwież KSeF” — bez zmian.
- Błędne `number_local` w DB (historyczne IFG) nie są migrowane; UI pokazuje `ksef_reference_number` gdy numer wygląda na IFG.
- Pełna diagnostyka E2E: `docs/KSEF_ASYNC_SYNC_E2E_DIAGNOSTIC.md`.
