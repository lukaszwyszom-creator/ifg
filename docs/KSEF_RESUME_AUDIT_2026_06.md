# Audyt implementacji KSeF purchase sync resume

**Data:** 2026-06-22  
**Zakres:** pliki ze fixu ([KSEF_PURCHASE_SYNC_RESUME_FIX.md](./KSEF_PURCHASE_SYNC_RESUME_FIX.md))  
**Metoda:** analiza statyczna kodu (bez zmian w repozytorium)

---

## Podsumowanie werdyktów

| # | Pytanie | Werdykt |
|---|---------|---------|
| 1 | Trwały zapis faktur do PostgreSQL **przed** wystąpieniem 429 | **FAIL** |
| 2 | Czy `session.flush()` wystarcza, czy wymagany commit/checkpoint | **FAIL** |
| 3 | Resume od `current_offset` po restarcie workera | **PASS** |
| 4 | Ryzyko utraty pobranych faktur przy rollbacku transakcji | **FAIL** |
| 5 | Blokada aktywnego joba per NIP (deferred/pending) | **PASS** |
| 6 | Duplikaty przy resume + równoczesnym restarcie workera | **PASS** |

---

## 1. Trwały zapis przed 429

**Werdykt: FAIL**

### Dowód w kodzie

Incremental sync (`_sync_received_invoices_incremental`):

- Po każdej fakturze: `invoice_repository.add()` → wewnętrzny `session.flush()` (`invoice_repository.py:52–53`) oraz dodatkowy `self.session.flush()` (`ksef_session_service.py:695`).
- Przy 429: `self.session.flush()` (`ksef_session_service.py:656`) i **return** — bez `commit`.

Worker (`__main__.py`):

- `handler.handle()` wykonuje się w **jednej** sesji SQLAlchemy.
- `session.commit()` następuje **dopiero po** złapaniu `JobRateLimitDeferredError` i ustawieniu joba na `pending` (`__main__.py:256–257`).

### Wniosek

W momencie wystąpienia 429 faktury są jedynie **flushowane w otwartej transakcji**. Nie są widoczne dla innych połączeń ani trwałe w PostgreSQL do momentu `commit` na końcu iteracji workera (czyli **po** 429).

Funkcjonalnie: przy normalnym DEFERRED (bez crashu) 15 faktur **będzie** w bazie przed kolejną próbą joba — ale **nie** „przed wystąpieniem 429” w sensie transakcyjnym.

---

## 2. flush vs commit/checkpoint

**Werdykt: FAIL**

| Mechanizm | Efekt |
|-----------|--------|
| `session.flush()` | Wysyła INSERT do PG w bieżącej transakcji; brak trwałości po crashu |
| `session.commit()` | Jedyny moment trwałości w obecnej architekturze |
| Per-faktura commit / SAVEPOINT | **Brak** w implementacji |

Commit jest **jeden na job** na końcu pętli `_process_batch`, nie po każdej fakturze. Dokumentacja fixu sugeruje „add + flush” jako zapis — to poprawia widoczność w tej samej sesji, ale **nie** zastępuje commitu.

**Wymagany:** commit (obecny, lecz opóźniony). **Niewystarczający:** sam flush.

---

## 3. Resume po restarcie workera

**Werdykt: PASS** (ścieżka nominalna DEFERRED)

### Łańcuch resume

1. Handler przekazuje `resume_state=payload.get("resume")` (`sync_purchase_invoices.py:70`).
2. Przy defer: `JobRateLimitDeferredError(..., resume=report["resume_state"])` (`sync_purchase_invoices.py:82–88`).
3. Worker zapisuje `payload_json["resume"]` (`__main__.py:233–234`) i commit.
4. Kolejne claim: `start_offset = resume["current_offset"]`, pętla `for idx in range(start_offset, len(refs))` (`ksef_session_service.py:612, 651`).
5. Przy resume **nie** woła `query_purchase_metadata_refs` jeśli `invoice_refs` jest w payload.

### Warunek

Resume działa, jeśli poprzednia iteracja zakończyła się **commit'em** (normalny DEFERRED). Patrz punkt 4 — crash przed commit = brak resume w payload.

---

## 4. Ryzyko utraty przy rollbacku

**Werdykt: FAIL** (ryzyko istnieje)

### Scenariusze utraty

| Scenariusz | Skutek |
|------------|--------|
| Crash / SIGKILL workera **po** flush, **przed** `commit` | Wszystkie faktury z bieżącej iteracji **utracone** (PG rollback niezatwierdzonej transakcji) |
| Wyjątek w `_process_batch` przed pętlą commit per job | `session.rollback()` (`__main__.py:261–262`) — utrata całego batcha |
| Normalny DEFERRED | Commit obejmuje faktury + `payload.resume` + status joba — **atomowo**, brak rollbacku |

### Architektura transakcyjna

Cały sync (faktury, `ksef_sync_states`, aktualizacja joba) działa w **jednej transakcji** sesji workera. Brak savepointów per faktura.

Stale recovery (`release_stale_processing_jobs`, 30 min): job wraca na `pending` **bez** zapisania `resume` — przy crashu przed commit sync startuje od metadata od początku (dedup po zapisanych ref ratuje duplikaty, ale postęp w payload ginie).

---

## 5. Blokada joba per NIP (deferred/pending)

**Werdykt: PASS**

`POST /sync-purchase` (`ksef_session.py:320–336`):

```python
BackgroundJob.status.in_(["pending", "processing"])
BackgroundJob.payload_json["nip"].astext == body.nip
```

Po DEFERRED worker ustawia `status="pending"` (`_release_job_to_pending`, `__main__.py:160–164`). Job deferred **jest** pending — kolejny enqueue dla tego NIP zwróci istniejący `job_id`.

**Nie blokuje:** job ze statusem `done` / `failed` — wtedy można utworzyć nowy job (zamierzone).

---

## 6. Duplikaty przy resume + restart workera

**Werdykt: PASS** (nominalnie; resztkowe ryzyka niskie)

### Mechanizmy ochronne

| Mechanizm | Działanie |
|-----------|-----------|
| `FOR UPDATE SKIP LOCKED` przy claim | Jeden worker na job (`background_job.py:50`) |
| `exists_by_ksef_number` przed insert | Pomija już zapisane ref (`ksef_session_service.py:717`) |
| Resume od `current_offset` | Nie pobiera ponownie ref 0..offset-1 w tej samej liście |

### Po restarcie (happy path)

1. Iteracja N: 15 faktur + resume → commit.
2. Restart workera, job `pending` z `resume.current_offset=15`.
3. Pobranie od ref[15]; ref 0–14 w bazie → skip lub brak ponownego zapisu.

### Resztkowe ryzyka (nie PASS→FAIL, ale do monitorowania)

- **Brak UNIQUE** na `invoices.ksef_reference_number` w audytowanym kodzie — dedup tylko aplikacyjny; race dwóch procesów poza workerem mógłby duplikować.
- **TOCTOU enqueue:** dwa równoczesne `POST /sync-purchase` mogą oba nie zobaczyć pending i utworzyć dwa joby (brak blokady DB w enqueue).
- **Crash przed commit:** brak resume, re-metadata — duplikat mało prawdopodobny (nic nie commitowano), ale marnowane pobrania.

---

## Ryzyka krytyczne

1. **Brak commit per faktura** — crash workera między flush a commit kasuje cały postęp bieżącej iteracji (w tym wiele już „zapisanych” faktur). Fix nie spełnia literalnie wymogu trwałości „przed 429”; spełnia go dopiero po zakończeniu iteracji workera.

2. **Pojedyncza transakcja na cały job** — faktury, stan sync i payload joba commitowane razem; brak checkpointów. Rollback / crash = utrata wszystkiego z iteracji.

3. **Stale recovery bez resume** — zawieszony job (`processing` > 30 min) wraca na `pending` bez `payload.resume`; sync od początku metadata (dedup ratuje duplikaty, nie ratuje limitów KSeF).

4. **TOCTOU przy enqueue** — równoległe requesty API mogą utworzyć dwa joby dla tego samego NIP (blokada działa sekwencyjnie, nie atomowo).

5. **Brak constraint UNIQUE na `ksef_reference_number`** — ochrona przed duplikatem wyłącznie w warstwie aplikacji (`exists_by_ksef_number`).

---

## Pliki audytowane

- `app/services/ksef_session_service.py`
- `app/integrations/ksef/client.py`
- `app/worker/job_handlers/sync_purchase_invoices.py`
- `app/worker/__main__.py`
- `app/api/routers/ksef_session.py`
- `app/persistence/repositories/invoice_repository.py` (używany przez fix: `add`, `exists_by_ksef_number`)
- `app/persistence/models/background_job.py` (claim / stale — kontekst punktów 3, 4, 6)

---

## Rekomendacje (informacyjne — poza zakresem tego audytu)

Audyt **nie wprowadza zmian**. Potencjalne usprawnienia na przyszłość:

- `commit()` (lub SAVEPOINT + commit) po każdej zapisanej fakturze w incremental sync.
- UNIQUE INDEX na `ksef_reference_number` WHERE NOT NULL.
- Atomowy enqueue (SELECT … FOR UPDATE / advisory lock na NIP).
