# KSeF purchase sync resume — retest produkcyjny DS723+

**Data analizy:** 2026-06-21 ~00:55 CEST  
**Commit produkcyjny:** `ca30742`  
**Job:** `4d6ad6ef-b187-4fd9-8504-6a63985c5ef9` (created 2026-06-21 00:51:55)

---

## STATUS: **PARTIAL**

Mechanizm **resume działa** na produkcji (offset rośnie, brak re-metadata, payload.resume zapisany). Sync **nie zakończony** (48/50 ref, `pending`). **0 nowych** faktur — wszystkie przetworzone ref już w bazie (`skipped_existing=48`).

---

## Odpowiedzi diagnostyczne

| # | Pytanie | Wynik |
|---|---------|-------|
| 1 | Job claimnięty? | **TAK** — 3× `WORKER_JOB_CLAIMED` (00:51:59, 00:54:07, 00:55:13) |
| 2 | Ścieżka incremental/resume ca30742? | **TAK** — `KSeF purchases incremental sync`, offset 0→16→32→48 |
| 3 | Metadata pobrane? | **TAK** (tylko run 1) — POST metadata 429→retry→200, refs=50; run 2–3 **bez** ponownego metadata |
| 4 | XML pobrany? | **TAK (częściowo)** — GET 200 dla części ref; 429 na granicy batchy |
| 5 | Wystąpił 429? | **TAK** — metadata (run 1), GET ref (każdy run) |
| 6 | Zapisano resume/current_offset? | **TAK** — `current_offset=48`, `downloaded_count=48`, `partial_result` w DB |
| 7 | Nowe faktury zakupowe? | **0** — `COUNT=51` (bez zmian od 2026-06-17) |
| 8 | Status joba? | **pending / deferred** — `available_at=2026-06-21 00:56:18`, nie `done`, nie `failed` |
| 9 | Błędy blokujące? | **429 KSeF** — nie blokuje postępu (defer 44s + resume); brak błędów aplikacyjnych |
| 10 | Fix resume działający? | **TAK** — potwierdzone na produkcji |

---

## Timeline joba `4d6ad6ef`

| Czas | Zdarzenie |
|------|-----------|
| 00:51:55 | `KSEF_ASYNC_SYNC_ENQUEUE` (API) |
| 00:51:59 | CLAIM + `KSEF_ASYNC_SYNC_WORKER_START` |
| 00:51:59 | Metadata POST → **429** |
| 00:52:57–00:53:00 | Metadata retry → 200, refs=50 |
| 00:53:00 | `incremental sync offset=0` |
| 00:53:22 | GET ref `8691917419-...` → **429**, `WORKER_JOB_DEFERRED` retry_after=44s |
| 00:54:07 | CLAIM (run 2), `incremental sync offset=16` — **bez metadata** |
| 00:54:11 | GET 200 (ref `5541092223-...`) |
| 00:54:27 | GET ref `7792467259-...` → **429**, DEFERRED |
| 00:55:13 | CLAIM (run 3), `incremental sync offset=32` |
| 00:55:13 | DB: `current_offset=48`, `partial_result` zaktualizowany |

---

## Stan DB (job)

```
id:                  4d6ad6ef-b187-4fd9-8504-6a63985c5ef9
status:              pending
attempts:            0
available_at:        2026-06-21 00:56:18
current_offset:      48
downloaded_count:    48
saved_accumulated:   0
partial_result:      {"saved": 0, "received": 50, "skipped_existing": 48,
                      "skipped_parse": 0, "rate_limited": true, "warning": "..."}
last_error:          KSeF ograniczył tempo pobierania faktur (HTTP 429)...
```

Stare 4 joby: `failed` z `Manual cleanup before KSeF resume retest after deploy ca30742`.

---

## Faktury zakupowe

| Metryka | Wartość |
|---------|---------|
| Łącznie | **51** |
| Nowe w tym teście | **0** |
| Ostatni zapis | 2026-06-17 19:28:47 |

`partial_result.skipped_existing=48` — przetworzone ref już istniały w bazie; resume + dedup działają poprawnie.

---

## Logi — kluczowe markery fixu

| Marker | Obecny? |
|--------|---------|
| `KSeF purchases incremental sync` | ✅ |
| `offset=N` rosnący bez re-metadata | ✅ (16, 32, 48) |
| `KSEF_RATE_LIMIT_DEFER` | ✅ |
| `WORKER_JOB_DEFERRED` | ✅ (3×) |
| `payload resume` / `current_offset` w DB | ✅ |
| `partial_result` w DB | ✅ |
| `KSEF_ASYNC_SYNC_WORKER_DONE` | ❌ (sync w toku) |
| `KSeF sync: zapisano fakturę` | ❌ (brak nowych) |

---

## Werdykt

| Pole | Wartość |
|------|---------|
| **STATUS** | **PARTIAL** |
| **Resume** | **TAK** |
| **Nowe faktury** | **0** |
| **Status joba** | **pending** (deferred, offset 48/50, retry ~00:56) |

Fix resume **potwierdzony na produkcji**. Pełny sukces sync (`done`, nowe FV) wymaga dokończenia pozostałych 2 ref po wygaśnięciu limitu KSeF — przy obecnym stanie wszystkie 50 ref wyglądają na już znane w bazie.
