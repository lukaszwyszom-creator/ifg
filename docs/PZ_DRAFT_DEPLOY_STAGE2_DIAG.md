# PZ draft deploy — etap 2: diagnoza `ModuleNotFoundError: scripts`

**Data:** 2026-06-19  
**Kontekst:** DS723+, commit `6d00b34`, migracja `f8a9b0c1d2e3` applied, api rebuilt, worker recreated  
**Błąd:** `python -m scripts.backfill_pz_draft_layers --dry-run` → `ModuleNotFoundError: No module named 'scripts'`

---

## 1. Przyczyna błędu

Katalog **`scripts/` nie istnieje w obrazie Docker `ifg-api:latest`** i nie jest pakietem Pythona zainstalowanym przez `pip`.

### Dockerfile (`docker/Dockerfile`)

Kopiowane są wyłącznie:

```dockerfile
COPY pyproject.toml README.md ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
```

**Brak:** `COPY scripts ./scripts`

### `pyproject.toml`

```toml
[tool.setuptools.packages.find]
include = ["app*"]
```

Instalowany jest tylko pakiet `app`. Katalog `scripts/` nie wchodzi do dystrybucji.

### `docker-compose.prod.yml`

Volume dla `api`:

- `frontend-react/dist` → UI
- `.env.production` → konfiguracja

**Brak bind-mount** repo / `scripts/` do konteneru.

### Dlaczego `python -m scripts.backfill_pz_draft_layers` nie działa

1. `-m scripts....` wymaga modułu `scripts` w `sys.path` (pakiet lub katalog w `/app/scripts`).
2. W kontenerze `/app` zawiera: `app/`, `alembic/`, `alembic.ini`, zainstalowane site-packages — **nie ma `scripts/`**.
3. Brak `scripts/__init__.py` — nawet na hoście `-m scripts` działa tylko przy uruchomieniu z root repo i odpowiednim PYTHONPATH; w kontenerze pliku fizycznie nie ma.

**Wniosek:** Dokumentacja wdrożeniowa (`PZ_DRAFT_E1_E5_EXECUTION_PLAN.md`, `GUARDIAN_PZ_DRAFT_DEPLOY_DIAG.md`) zakładała `exec api python -m scripts...`, ale **obraz prod nigdy nie zawierał tego skryptu** — to luka dokumentacji vs Dockerfile, nie błąd operatora.

---

## 2. Gdzie leżą pliki operacyjne

| Plik | Na hoście (git checkout) | W obrazie `api` |
|------|--------------------------|-----------------|
| `scripts/backfill_pz_draft_layers.py` | ✅ po `git pull` | ❌ |
| `scripts/verify_pz_draft_backfill.sql` | ✅ | ❌ (niepotrzebny w api) |

Skrypt backfill importuje `app.persistence.*` — **musi działać w środowisku z zainstalowanym pakietem `app`** (kontener `api`), ale **plik `.py` może pochodzić z bind-mounta** przy jednorazowym `compose run`.

Plik SQL uruchamia się **z hosta** przez `psql` w kontenerze `db` (stdin / redirect pliku z hosta).

---

## 3. Poprawny sposób uruchomienia (DS723+)

Załóż:

```bash
export IFG_ROOT=/volume1/docker/ifg/ifg_standalone   # dostosuj ścieżkę
export COMPOSE="sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production"
cd "$IFG_ROOT"
```

### A. Weryfikacja: plik na hoście vs brak w obrazie

```bash
ls -la scripts/backfill_pz_draft_layers.py
$COMPOSE exec api ls -la /app/scripts 2>&1 || true
# Oczekiwane: ls: cannot access '/app/scripts' — potwierdza diagnozę
```

### B. Backfill — **bind-mount `scripts/` przy one-shot `run`**

Użyj `compose run` (nie `exec`), bo można dodać volume tylko przy starcie kontenera:

```bash
# dry-run
$COMPOSE run --rm --no-deps \
  -v "$IFG_ROOT/scripts:/app/scripts:ro" \
  api python /app/scripts/backfill_pz_draft_layers.py --dry-run

# execute (gdy dry-run pokaże candidates > 0)
$COMPOSE run --rm --no-deps \
  -v "$IFG_ROOT/scripts:/app/scripts:ro" \
  api python /app/scripts/backfill_pz_draft_layers.py --execute
```

**Uwaga:** `run` tworzy tymczasowy kontener — OK dla skryptu operacyjnego; używa tej samej sieci i `env_file` co `api`.

Alternatywa bez `-m`:

```bash
$COMPOSE run --rm --no-deps \
  -v "$IFG_ROOT/scripts:/app/scripts:ro" \
  api python /app/scripts/backfill_pz_draft_layers.py --dry-run
```

**Nie używać:** `$COMPOSE exec api python -m scripts...` — bez zmiany Dockerfile / volume na stałe **nie zadziała**.

### C. Weryfikacja E3 — SQL z hosta do `db`

```bash
$COMPOSE exec -T db psql -U postgres -d ksef_backend \
  < scripts/verify_pz_draft_backfill.sql
```

Plik SQL jest czytany z **filesystem hosta** (katalog repo), nie z obrazu.

Szybki gate (0 draft):

```bash
$COMPOSE exec -T db psql -U postgres -d ksef_backend -c \
  "SELECT COUNT(*) AS draft_pz FROM warehouse_documents WHERE doc_type='PZ' AND status='draft';"
```

Oczekiwane: `0`.

Gate orphan lines:

```bash
$COMPOSE exec -T db psql -U postgres -d ksef_backend -c "
SELECT COUNT(*) AS orphan_lines
FROM warehouse_documents d
JOIN warehouse_document_items di ON di.document_id = d.id
LEFT JOIN inventory_layers il ON il.source_document_item_id = di.id
WHERE d.doc_type='PZ' AND d.status='draft' AND il.id IS NULL;"
```

Oczekiwane: `0`.

---

## 4. Gdzie *powinien* być uruchamiany skrypt (decyzja architektoniczna)

| Wariant | Ocena | Uzasadnienie |
|---------|-------|--------------|
| **Na hoście** (`python3 scripts/...`) | ⚠️ słaby | DS723+ zwykle bez venv z zależnościami; brak `app` w PYTHONPATH |
| **W kontenerze `api` + plik z bind-mount** | ✅ **zalecany teraz** | `app` zainstalowany; skrypt z git checkout; bez zmiany obrazu |
| **Skopiowany do obrazu (COPY scripts)** | ✅ na przyszłość | Wymaga zmiany Dockerfile + rebuild — **poza scope tej diagnozy** |

Skrypt **nie powinien** być uruchamiany w `worker` — dotyczy migracji danych magazynu, one-shot w `api`.

---

## 5. Czy backfill jest wymagany przy PZ draft = 0, PZ posted = 1?

| Aspekt | Ocena |
|--------|-------|
| **Funkcjonalnie** | **NIE** — brak kandydatów; `fetch_candidates()` zwróci `[]`; execute = no-op |
| **Logicznie / audyt** | **Opcjonalnie** — dry-run potwierdza `candidates: 0` |
| **Gate E3 (SQL)** | **TAK (zalecany)** — potwierdza spójność bez uruchamiania backfillu |

Przy **0 PZ draft** bezpieczne jest:

1. Pominąć `--execute` backfillu po potwierdzeniu SQL `draft_pz = 0` i `orphan_lines = 0`.
2. Uruchomić `verify_pz_draft_backfill.sql` (E3) — wystarczy jako gate.

Istniejący **1 PZ posted** ma warstwę utworzoną starym flow (przy post) — backfill go **nie dotyka** (tylko `status='draft'`).

---

## 6. Czy wdrożenie można uznać za zakończone?

**Tak — warunkowo**, jeśli spełnione:

| Krok | Status (wg opisu) |
|------|-------------------|
| Backup DB | ✅ |
| `alembic upgrade head` → `f8a9b0c1d2e3` | ✅ |
| Rebuild + recreate api/worker | ✅ |
| Backfill execute | ⏭️ **pominięty OK** przy 0 draft + SQL gate |
| E3 SQL verify | ⬜ do wykonania (komendy §3C) |
| `npm run build` frontend (E5 UI) | ⬜ zweryfikować |
| Smoke: nowy PZ draft, Stany, post PZ | ⬜ zweryfikować |

Brak backfillu **nie blokuje** zakończenia wdrożenia przy **0 draft PZ**.

Błąd `ModuleNotFoundError` **nie oznacza** problemu z migracją ani z kodem magazynu — tylko **niedopasowanie instrukcji uruchomienia do Dockerfile**.

---

## 7. Poprawka dokumentacji (bez implementacji w repo)

Zaktualizować w przyszłości:

- `docs/PZ_DRAFT_IMPLEMENTATION_REPORT.md`
- `docs/GUARDIAN_PZ_DRAFT_DEPLOY_DIAG.md`
- `docs/PZ_DRAFT_E1_E5_EXECUTION_PLAN.md`

Zamienić:

```bash
exec api python -m scripts.backfill_pz_draft_layers ...
```

Na:

```bash
compose run --rm --no-deps -v "$PWD/scripts:/app/scripts:ro" \
  api python /app/scripts/backfill_pz_draft_layers.py ...
```

Opcjonalnie długoterminowo: `COPY scripts ./scripts` w Dockerfile (wymaga rebuild).

---

## 8. Podsumowanie

| Pytanie | Odpowiedź |
|---------|-----------|
| Przyczyna `ModuleNotFoundError` | `scripts/` nie w obrazie Docker; `-m scripts` w `exec api` niemożliwe |
| Poprawny backfill | `compose run` + bind-mount `scripts/` + `python /app/scripts/backfill_pz_draft_layers.py` |
| Poprawny verify SQL | `exec -T db psql ... < scripts/verify_pz_draft_backfill.sql` z hosta |
| Backfill wymagany? | **Nie** przy 0 PZ draft; SQL gate wystarczy |
| Wdrożenie zakończone? | **Tak**, po E3 SQL + frontend build + smoke (backfill opcjonalny no-op) |

---

## Powiązane

- [`docs/GUARDIAN_PZ_DRAFT_DEPLOY_DIAG.md`](GUARDIAN_PZ_DRAFT_DEPLOY_DIAG.md) — rebuild obrazu
- [`docs/PZ_DRAFT_IMPLEMENTATION_REPORT.md`](PZ_DRAFT_IMPLEMENTATION_REPORT.md) — E2/E3
