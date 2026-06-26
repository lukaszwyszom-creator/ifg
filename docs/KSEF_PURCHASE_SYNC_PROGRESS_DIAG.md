# KSeF purchase sync — diagnostyka postępu i 429 DEFERRED

**Data:** 2026-06-21  
**Środowisko:** DS723+ production  
**Tryb:** read-only

---

## 1. Architektura resume (kod)

### Brak cursora w jobie

`background_jobs.payload_json` zawiera tylko:

```json
{ "job_id", "nip", "date_from", "date_to", "actor_user_id" }
```

**Nie ma** pola typu `last_ref`, `downloaded_count`, `pending_refs`. Po DEFERRED job restartuje **cały** `sync_purchase_invoices()` od początku.

### Jedyny mechanizm „resume”

**Dedup po zapisie:** `invoice_repository.exists_by_ksef_number()` — przy kolejnej próbie już zapisane faktury są pomijane (`skipped_existing`).

### Przepływ przy HTTP 429 (worker, `defer_purchase_rate_limit=True`)

1. Metadata query → lista ref (np. 50).
2. Pętla `GET /invoices/ksef/{ref}` po kolei.
3. Przy **pierwszym 429** → `KSeFRateLimitDeferredError` → wyjątek **przerywa cały download**.
4. Zapis faktur (`sync_received_invoices` pętla `saved++`) wykonuje się **dopiero po** zakończeniu `query_received_invoices()`.
5. **Wniosek:** faktury pobrane w pamięci przed 429 w **tej samej próbie nie są zapisywane**.

### Worker DEFERRED

```
WORKER_JOB_DEFERRED → status=pending, available_at=now+retry_after
attempts -= 1  (przy max_attempts=1 pozwala na wielokrotne defer bez failed)
```

`mark_success` / `state_json` aktualizowane **tylko** po pełnym sukcesie bez wyjątku. Przy 429 defer → `mark_error` w `ksef_sync_states`.

---

## 2. Stan produkcji (2026-06-20/21)

### Aktywne joby sync (2× pending, DEFERRED)

| job_id | status | attempts | last_error (429 na ref) |
|--------|--------|----------|-------------------------|
| `aca91f39-…` | pending | 0 | `5223027866-20260330-532CD44000EF-B9` |
| `0ffada86-…` | pending | 0 | `8691917419-20260424-781042C00000-3D` |

Oba utworzone **2026-06-20 ~23:52–23:53**, `available_at` ~ **2026-06-21 00:53** (retry_after ~3380 s po eskalacji limitu).

### ksef_sync_states

```
scope=purchase_invoices | status=error
last_success_at=2026-06-17 19:31
last_attempt_at=2026-06-20 23:56:46
last_error=429 dla 5223027866-20260330-532CD44000EF-B9
```

### Liczba faktur zakupowych

| Metryka | Wartość |
|---------|---------|
| **Przed bieżącym sync** (ostatni zapis) | **50** (2026-06-17 19:28, job `0ad868a3`: saved=1, skipped_existing=49) |
| **Zapisane podczas bieżącego sync (20–21.06)** | **0** |
| **Teraz w bazie** | **51** purchase, wszystkie z `ksef_reference_number` |
| Najnowsza faktura | 2026-06-17 19:28:47 |

### Duplikaty `ksef_reference_number`

**0** — brak duplikatów.

### WORKER_DONE vs DEFERRED (ostatnie 6h)

| Log | Liczba |
|-----|--------|
| `KSEF_ASYNC_SYNC_WORKER_START` | wiele (2 joby naprzemiennie) |
| `WORKER_JOB_DEFERRED` | każdy START kończy się DEFERRED |
| `KSEF_ASYNC_SYNC_WORKER_DONE` | **0** |
| `KSeF sync: zapisano fakturę` | **0** |

Wzorzec logów:

```
START aca91f39 → 429 ref B9 (~3s) → DEFERRED 22–3374s
START 0ffada86 → 429 ref 3D (~23s) → DEFERRED 40–3382s
(powtarzane co ~40s, potem retry_after > 3000s)
```

**Dwa równoległe joby** konkurują o ten sam limit KSeF — pogarszają sytuację 429.

---

## 3. Odpowiedzi na pytania

### Czy sync zapisuje nowe faktury?

**Historycznie tak** (ostatnio 1 faktura 17.06).  
**Podczas bieżącej sesji (429 loop): NIE** — 0 nowych od 20.06 23:00.

### Czy po 429 kontynuuje czy zaczyna od początku?

**Zaczyna od początku** każdej próby joba:

- ponowne metadata query (50 ref),
- ponowne pobieranie XML od pierwszego ref,
- dedup tylko dla już **zapisanych** w DB (51 szt.).

Pobrania w pamięci przed 429 **nie są utrwalane** między retry.

### Czy job osiąga WORKER_DONE?

**Nie** w bieżącej sesji. Ostatni `WORKER_DONE`: **2026-06-17** (`saved=1`).

### Czy krąży START → DEFERRED → START?

**Tak** — potwierdzone na prod (2 joby, brak DONE od godzin).

### Ryzyko nieskończonej pętli?

**Tak — wysokie:**

- `max_attempts=1`, ale defer robi `attempts -= 1` → job nigdy nie przechodzi w `failed`.
- Brak postępu zapisu przy abort-before-save.
- Dwa joby równolegle = podwójne obciążenie KSeF.
- Po wielu 429 KSeF zwraca `retry_after_seconds≈3380` (~56 min) — pętla trwa, ale bez efektu.

---

## 4. SQL diagnostyczne (DS723+)

```bash
export PATH="/var/packages/ContainerManager/target/usr/bin:$PATH"
cd /volume1/docker/ifg_v2/ifg_standalone
PSQL="docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec -T db psql -U postgres -d ksef_backend"
```

### Ostatnie joby sync

```sql
SELECT id, status, attempts, max_attempts, available_at, updated_at,
       left(last_error, 100) AS last_error,
       payload_json->'result' AS result
FROM background_jobs
WHERE job_type = 'sync_purchase_invoices'
ORDER BY updated_at DESC
LIMIT 10;
```

### Stan sync

```sql
SELECT scope, status, last_success_at, last_attempt_at, last_error, state_json
FROM ksef_sync_states;
```

### Ostatnie 100 importowanych faktur zakupowych

```sql
SELECT id,
       number_local,
       ksef_reference_number,
       created_at AT TIME ZONE 'Europe/Warsaw' AS imported_at_pl,
       total_gross,
       currency
FROM invoices
WHERE direction = 'purchase'
ORDER BY created_at DESC
LIMIT 100;
```

### Duplikaty KSeF ref

```sql
SELECT ksef_reference_number, COUNT(*) AS cnt
FROM invoices
WHERE direction = 'purchase' AND ksef_reference_number IS NOT NULL
GROUP BY ksef_reference_number
HAVING COUNT(*) > 1;
```

### Liczniki przed/po sync

```sql
-- Teraz
SELECT COUNT(*) AS total_now FROM invoices WHERE direction = 'purchase';

-- Utworzone po starcie bieżących jobów (2026-06-20 23:52)
SELECT COUNT(*) AS saved_during_current_sync
FROM invoices
WHERE direction = 'purchase'
  AND created_at >= '2026-06-20 23:52:00+02';
```

### Logi worker

```bash
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  logs --since 6h worker | grep -E 'KSEF_ASYNC_SYNC|WORKER_JOB_DEFERRED|KSEF_RATE_LIMIT_DEFER|zapisano faktur'
```

---

## 5. Wnioski operacyjne (bez wdrożenia)

| Problem | Opis |
|---------|------|
| Abort-before-save | 429 kończy próbę przed zapisem → brak postępu mimo pobranych XML |
| Brak cursora | Każde retry = pełne metadata + pełny download |
| 2 równoległe joby | Podwójne trafienie w rate limit |
| Defer = nieskończony retry | Job nie przechodzi w `failed` |

**Operacyjnie (poza kodem):** anulować/zatrzymać jeden z dwóch pending jobów, odczekać retry_after (~1h), uruchomić **jeden** sync po ustabilizowaniu limitu KSeF.

---

## 6. Podsumowanie

| Pytanie | Odpowiedź |
|---------|-----------|
| Sync zapisuje nowe? | Tak historycznie; **nie w bieżącej pętli 429** |
| Po 429 kontynuuje? | **Nie** — restart od metadata; dedup tylko DB |
| Ryzyko nieskończonej pętli? | **Tak** |
| Duplikaty? | **Nie** |
