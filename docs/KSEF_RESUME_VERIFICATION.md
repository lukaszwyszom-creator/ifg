# Weryfikacja audytu KSeF resume (commit / UNIQUE / per-faktura)

**Data:** 2026-06-22  
**Odniesienie:** [KSEF_RESUME_AUDIT_2026_06.md](./KSEF_RESUME_AUDIT_2026_06.md)  
**Metoda:** analiza statyczna wskazanych plików (bez zmian kodu)

---

## Werdykty weryfikacji

| # | Pytanie | Wynik |
|---|---------|--------|
| 1 | Czy analiza FAIL dla commit/flush jest poprawna? | **PASS** |
| 2 | Czy po DEFERRED worker wykonuje commit przed oddaniem joba do pending? | **PASS** |
| 3 | Czy istnieje UNIQUE INDEX / CONSTRAINT na `ksef_reference_number`? | **FAIL** |
| 4 | Gdzie dodać constraint (jeśli brak)? | — (patrz sekcja 4) |
| 5 | Czy commit per faktura jest bezpieczny dla obecnej architektury sync? | **PASS** |

---

## 1. Poprawność analizy FAIL (commit / flush)

**PASS** — audyt jest poprawny.

### Uzasadnienie

- `_sync_received_invoices_incremental` wywołuje wyłącznie `session.flush()` po każdej fakturze i przy 429 (`ksef_session_service.py:656, 695`); brak `commit` w serwisie.
- `invoice_repository.add()` robi `session.add` + `flush` (`invoice_repository.py:52–53`), nie `commit`.
- W PostgreSQL `flush` wysyła SQL w **otwartej transakcji**; trwałość (WAL commit) wymaga `commit`.
- W momencie wyjątku 429 w handlerze faktury nie są jeszcze trwale zapisane dla innych sesji — dopiero po `session.commit()` workera.

Wniosek audytu „FAIL dla flush jako zamiennika commitu” i „brak trwałości przed momentem commitu” jest **technicznie poprawny**.

---

## 2. Commit po DEFERRED a oddanie joba do pending

**PASS** — dane są commitowane w tej samej transakcji co przejście joba na `pending`.

### Kolejność w `app/worker/__main__.py`

```
218–219  handler.handle()          → flush faktur w sesji
226      JobRateLimitDeferredError
233–239  payload["resume"]
240      _release_job_to_pending() → status = "pending" (w sesji)
241–245  available_at, attempts -= 1
256–257  session.flush(); session.commit()
```

### Interpretacja

- **Kolejność w kodzie:** `_release_job_to_pending` (przypisanie `pending`) następuje **przed** `commit` — nie ma osobnego commitu „przed” zmianą statusu w pamięci sesji.
- **Widoczność w PostgreSQL:** status `pending`, `payload.resume` i wstawione faktury stają się widoczne dla innych połączeń **dopiero po** `commit` w linii 257 — **atomowo**, w jednej transakcji.
- Inny worker / API nie zobaczy joba jako `pending` bez jednoczesnego commitu faktur z tej iteracji (przy normalnym zakończeniu DEFERRED).

Audyt słusznie stwierdza, że commit jest po obsłużeniu 429; weryfikacja potwierdza, że ścieżka DEFERRED **kończy się commit'em** zawierającym faktury + resume + pending.

---

## 3. UNIQUE na `ksef_reference_number`

**FAIL** — brak UNIQUE INDEX / UNIQUE CONSTRAINT.

### Model

`app/persistence/models/invoice.py:30`:

```python
ksef_reference_number: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
```

`index=True` bez `unique=True`; brak `UniqueConstraint` w `__table_args__`.

### Migracja

`alembic/versions/0003_b2c3d4e5f6a7_invoice_fa3_fields.py:31–35`:

```python
op.create_index(
    "ix_invoices_ksef_reference_number",
    "invoices",
    ["ksef_reference_number"],
    unique=False,
)
```

Indeks jest **nieunikalny**. Audyt (ryzyko #5) jest poprawny.

---

## 4. Gdzie dodać UNIQUE (rekomendacja — bez implementacji)

Ponieważ kolumna jest **nullable** (faktury sprzedaży bez numeru KSeF), w PostgreSQL potrzebny jest **partial unique index** (wiele wierszy z `NULL` dozwolone).

### A. Model ORM

Plik: `app/persistence/models/invoice.py`

- Dodać do `InvoiceORM.__table_args__` (wzorzec jak w `stock.py`, `idempotency_key.py`):

```python
Index(
    "uq_invoices_ksef_reference_number",
    "ksef_reference_number",
    unique=True,
    postgresql_where=text("ksef_reference_number IS NOT NULL"),
)
```

(wymaga importu `Index` z `sqlalchemy` i `text` z `sqlalchemy`).

### B. Migracja Alembic

Nowy plik: `alembic/versions/<revision>_unique_invoices_ksef_reference_number.py`

1. Sprawdzić brak duplikatów w prod (`SELECT ksef_reference_number, COUNT(*) … HAVING COUNT(*) > 1`).
2. `op.drop_index("ix_invoices_ksef_reference_number", table_name="invoices")` (opcjonalnie — można zostawić nieunikalny + dodać partial unique).
3. `op.create_index("uq_invoices_ksef_reference_number", "invoices", ["ksef_reference_number"], unique=True, postgresql_where=sa.text("ksef_reference_number IS NOT NULL"))`.

### C. Warstwa aplikacji (opcjonalnie)

`app/persistence/repositories/invoice_repository.py` — obsługa `IntegrityError` przy `add()` jako drugi poziom po `exists_by_ksef_number` (nie zastępuje constraintu DB).

---

## 5. Bezpieczeństwo commit per faktura

**PASS** — kompatybilne z obecną architekturą workera, przy minimalnym zakresie zmian.

### Dlaczego PASS

| Aspekt | Ocena |
|--------|--------|
| Worker używa jednej sesji SQLAlchemy na batch (`__main__.py:168`) | `commit` w serwisie zatwierdza bieżącą transakcję sesji workera |
| Claim joba | `claim_and_lock_jobs` robi `flush` (`background_job.py:181`); pierwszy `commit` w sync utrwala też `status=processing` — spójne |
| Blokada równoległego sync per NIP | Dopóki job `processing`/`pending`, enqueue zablokowany (`ksef_session.py:324`) |
| `ksef_sync_states` | `mark_running` / `mark_error` używają `flush` (`ksef_sync_state_repository.py`); pierwszy commit per faktura utrwala `running` — akceptowalne |
| Resume payload | Nadal może być zapisywany przy DEFERRED w commit workera na końcu iteracji |
| Ścieżka synchroniczna API | Incremental sync aktywuje się tylko przy `defer_purchase_rate_limit is True` lub `resume_state` — sync HTTP bez defer **nie** wymaga commit per faktura |

### Ograniczenia (nie blokują PASS)

- Faktury stają się trwałe **przed** zapisem `payload.resume` (resume nadal przy commit końcowym workera) — lepsze niż obecny stan (utrata faktur przy crash przed końcowym commit).
- Przy crash po częściowych commitach faktur: job może wrócić ze stale recovery bez `resume` — dedup przez `exists_by_ksef_number`; bez UNIQUE nadal możliwy race przy równoległych writerach.
- Commit per faktura **w `_sync_received_invoices_incremental`**, nie globalnie w `invoice_repository.add`, aby nie zmieniać transakcji innych endpointów współdzielących sesję API.

---

## Pliki użyte w weryfikacji

- `docs/KSEF_RESUME_AUDIT_2026_06.md`
- `app/worker/__main__.py`
- `app/services/ksef_session_service.py`
- `app/persistence/repositories/invoice_repository.py`
- `app/persistence/repositories/ksef_sync_state_repository.py`
- `app/persistence/models/invoice.py`
- `alembic/versions/0003_b2c3d4e5f6a7_invoice_fa3_fields.py`
