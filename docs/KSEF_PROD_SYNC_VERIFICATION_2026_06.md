# KSeF purchase sync resume — weryfikacja produkcyjna DS723+

**Data analizy:** 2026-06-21 00:37 CEST  
**Środowisko:** DS723+ (`/volume1/docker/ifg_v2/ifg_standalone`)  
**HEAD na serwerze:** `bc14bd3` (fix resume: `ca30742` — **nie wdrożony**)

---

## STATUS: **FAIL**

Mechanizm resume **nie działa** na produkcji — wdrożony jest kod sprzed fixu. Zachowanie odpowiada diagnozie sprzed `KSEF_PURCHASE_SYNC_RESUME_FIX.md`.

---

## Źródła danych

```bash
sudo docker compose -f docker/docker-compose.prod.yml logs --tail=1000 worker
sudo docker compose -f docker/docker-compose.prod.yml logs --tail=500 api
# + zapytania SQL z polecenia użytkownika
```

Kontenery `api` / `worker`: recreate ~8 min przed analizą; git HEAD nadal `bc14bd3`.

---

## Odpowiedzi na pytania diagnostyczne

| # | Pytanie | Wynik | Dowód |
|---|---------|-------|-------|
| 1 | Czy job został uruchomiony? | **TAK** | `WORKER_JOB_CLAIMED` + `KSEF_ASYNC_SYNC_WORKER_START` dla `0e43ee5a`, `ad883446` (2026-06-21 00:30–00:31) |
| 2 | Czy pobrał metadata? | **TAK** | `POST .../invoices/query/metadata` 200, `refs=50`, `KSeF received invoices via metadata query: count=50` |
| 3 | Czy pobrał XML faktur? | **NIE** (brak sukcesu) | Jedyny `GET /invoices/ksef/5223027866-...` → **429**; brak logów `KSeF sync: zapisano fakturę` |
| 4 | Czy wystąpił 429? | **TAK** | `HTTP/1.1 429 Too Many Requests`, `KSEF_RATE_LIMIT_DEFER retry_after_seconds=1320` |
| 5 | Czy zapisano resume_state? | **NIE** | `payload_json->'resume'` → **NULL** dla wszystkich aktywnych jobów; brak logów `incremental`, `saved_accumulated`, `partial_result` |
| 6 | Czy job wrócił do pending? | **TAK** | `WORKER_JOB_DEFERRED`; DB: `status=pending`, `attempts=0`, `available_at≈2026-06-21 00:53` |
| 7 | Czy kolejna próba od current_offset? | **NIE** | Drugi job (`ad883446`) ponownie pobrał metadata (pageOffset 0+50); ten sam pierwszy ref → 429. Brak `current_offset` w payload |
| 8 | Ile nowych faktur zakupowych? | **0** | `COUNT(*)=51`; ostatni zapis `2026-06-17 19:28:47` |
| 9 | Błędy blokujące sync? | **TAK** | Ciągły 429 KSeF na pierwszym ref; 4 równoległe joby `pending` bez resume; `ksef_sync_states.status=error` |

---

## Logi worker (kluczowe zdarzenia)

```
00:30:58 WORKER_JOB_CLAIMED job_id=0e43ee5a... sync_purchase_invoices
00:30:58 KSEF_ASYNC_SYNC_WORKER_START nip=9670402857
00:30:58–59 POST metadata pageOffset=0,50 → refs=50
00:31:00 GET .../5223027866-20260330-532CD44000EF-B9 → 429
00:31:00 KSEF_RATE_LIMIT_DEFER retry_after_seconds=1320
00:31:00 WORKER_JOB_DEFERRED job_id=0e43ee5a...

00:31:06 WORKER_JOB_CLAIMED job_id=ad883446... (drugi job, ten sam NIP)
00:31:06 KSEF_ASYNC_SYNC_WORKER_START nip=9670402857
00:31:06–07 POST metadata ponownie → refs=50
00:31:08 GET ten sam ref → 429
00:31:08 WORKER_JOB_DEFERRED job_id=ad883446...
```

**Brak w logach (oczekiwane po fixie `ca30742`):**
- `KSeF purchases incremental sync`
- `query_purchase_metadata_refs` / `get_purchase_invoice_xml` jako osobna ścieżka
- `payload resume` / `current_offset`
- `KSEF_ASYNC_SYNC_WORKER_DONE`

---

## Stan `background_jobs` (TOP 4 aktywne)

| id (skrót) | status | attempts | current_offset | saved_accumulated | available_at |
|------------|--------|----------|----------------|-------------------|--------------|
| ad883446 | pending | 0 | NULL | NULL | 2026-06-21 00:53 |
| 0e43ee5a | pending | 0 | NULL | NULL | 2026-06-21 00:53 |
| aca91f39 | pending | 0 | NULL | NULL | 2026-06-21 00:53 |
| 0ffada86 | pending | 0 | NULL | NULL | 2026-06-21 00:53 |

`last_error` (wszystkie): `Błąd synchronizacji z KSeF: KSeF rate limit (429) dla 5223027866-...` — ścieżka batch + `ExternalServiceError`, bez `resume` w payload.

---

## Faktury zakupowe

| Metryka | Wartość |
|---------|---------|
| Łącznie `direction=purchase` | **51** |
| Nowe od ostatniego udanego sync (2026-06-17) | **0** |
| Duplikaty ref | nie badano (poza zakresem) |

---

## `ksef_sync_states`

```
scope=purchase_invoices | status=error
last_success_at=2026-06-17 19:31:55
last_attempt_at=2026-06-21 00:31:08
last_error=429 dla 5223027866-20260330-532CD44000EF-B9
```

---

## API

- Poll statusu jobów: `GET /sync-purchase/jobs/{id}` → `status=pending` (UI odpytuje oba joby).
- Brak logów `KSEF_ASYNC_SYNC_ENQUEUE_BLOCKED` — blokada per NIP z fixu **nieobecna** (stary kod).
- Utworzono **dwa** joby sync dla tego samego NIP w odstępie ~2 s (00:30:54 i 00:30:56).

---

## Wnioski

1. **Resume na produkcji: NIE** — brak `payload_json.resume`, brak incremental sync w logach.
2. **Przyczyna:** kod produkcyjny `bc14bd3`, fix `ca30742` nie został `git pull` + rebuild/recreate po commicie.
3. **Defer 429 (stary):** worker odrocza job (`WORKER_JOB_DEFERRED`), ale każda próba zaczyna metadata + GET od pierwszego ref → natychmiastowy 429 → **0 zapisanych faktur**.
4. **Retry po `available_at` (00:53):** w momencie analizy (00:37) jeszcze nie nastąpił; na podstawie braku resume w payload oczekiwane jest **ponowne metadata od zera**.
5. **Blokujące:** limit KSeF 429; 4 pending joby bez postępu; brak wdrożenia fixu.

---

## Werdykt końcowy

| Pole | Wartość |
|------|---------|
| **STATUS** | **FAIL** |
| **Nowe faktury** | **0** |
| **Resume działa** | **NIE** |
| **Fix wdrożony** | **NIE** (`bc14bd3` ≠ `ca30742`) |

Weryfikacja resume wymaga deployu zgodnie z `docs/KSEF_RESUME_DEPLOY_READY_2026_06.md`, a następnie powtórzenia tej samej diagnostyki po retry joba.
