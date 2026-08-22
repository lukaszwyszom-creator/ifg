# Guardian Platform — Repository Graph v1.1 (False Positive Elimination)

**Data:** 2026-06-26  
**Status:** IMPLEMENTED  
**Zakres:** wyłącznie jakość klasyfikacji — bez nowych komend CLI

---

## 1. Problem (v1)

Pierwsze uruchomienie Repo Graph poprawnie budowało grafy, ale klasyfikacja opierała się głównie na importerach/testach/CLI, ignorując artefakty specjalne:

| Plik | v1 (błędnie) | v1.1 (poprawnie) |
|------|--------------|------------------|
| `alembic/env.py` | ORPHAN → DELETE | PROTECTED → KEEP |
| `alembic/versions/*.py` | ORPHAN → DELETE | PROTECTED → KEEP |
| `**/__init__.py` | ORPHAN → DELETE | PROTECTED → KEEP |
| `docs/**` | ORPHAN → DELETE | PROTECTED → KEEP |
| `README.md`, `pyproject.toml` | nieśledzone / DELETE | PROTECTED → KEEP |
| `scripts/*.py` z `__main__` | ORPHAN → DELETE | ENTRYPOINT → KEEP |
| `tests/**/test_*.py` | ORPHAN → DELETE | FRAMEWORK → KEEP |

---

## 2. Wyeliminowane false positive

Pomiar na repo IFG (`RepositoryAnalyzer` + symulacja reguł v1):

| Metryka | Wartość |
|---------|---------|
| **False positive przed v1.1** | **321** |
| **False positive po v1.1** | **0** |
| Chronione artefakty (summary) | **377** |

### False positives prevented (raport `repo graph`)

| Kategoria | Liczba |
|-----------|--------|
| Protected (`__init__.py`) | 38 |
| Entrypoints | 9 |
| Alembic | 26 |
| Docs | 155 |
| Config | 14 |
| Framework | 135 |
| **Total** | **377** |

*(Framework obejmuje m.in. pliki testów pytest, FastAPI routers, moduły wykryte heurystycznie.)*

---

## 3. Nowe reguły

### Moduł `core/repository/protected.py`

Mechanizm **Protected Artefacts** z kategoriami:

| Kategoria | Wzorzec | Status | Rekomendacja |
|-----------|---------|--------|--------------|
| `PACKAGE_INIT` | `**/__init__.py` | PROTECTED | KEEP |
| `ALEMBIC` | `alembic/**` | PROTECTED | KEEP |
| `DOCUMENTATION` | `docs/**`, `README*`, `CHANGELOG*`, `LICENSE*`, `CONTRIBUTING*` | PROTECTED | KEEP |
| `CONFIGURATION` | `pyproject.toml`, `Dockerfile*`, `.guardian.yml`, `.github/**`, … | PROTECTED | KEEP |
| `ENTRYPOINT` | `__main__`, `main.py`, `console_scripts` | ENTRYPOINT | KEEP |
| `FRAMEWORK` | FastAPI, Alembic runtime, Celery, Typer, Click, pytest/unittest | FRAMEWORK | KEEP |

### Nowe statusy

`ACTIVE`, `REFERENCED`, `ORPHAN`, `ENTRYPOINT`, `PROTECTED`, `FRAMEWORK`, `UNKNOWN`

### Scoring (v1.1)

- `DELETE` / `ARCHIVE` **zablokowane** dla: PROTECTED, ENTRYPOINT, FRAMEWORK oraz kategorii DOCUMENTATION / CONFIGURATION / ALEMBIC
- Dokumentacja wyłączona z dead-code analysis (osobny przyszły moduł Documentation Audit)
- Raport `repository_graph.md` zawiera sekcję **False positives prevented**

---

## 4. Pliki zmienione

| Plik | Zmiana |
|------|--------|
| `core/repository/protected.py` | **NOWY** — reguły chronionych artefaktów |
| `core/repository/scoring.py` | Integracja protected przed orphan scoring |
| `core/repository/models.py` | Nowe statusy, `FalsePositivesSummary` |
| `core/repository/analyzer.py` | Root config paths, summary |
| `core/repository/report.py` | Sekcja false positives, filtry orphan/dead-code |
| `core/repository/commands.py` | Payload z `false_positives_prevented` |

**Bez zmian:** komendy CLI, core Platform, profil IFG, legacy Guardian.

---

## 5. Testy

Nowy plik: `tests/guardian_platform/test_repository_protected.py`

| Klasa | Testy |
|-------|-------|
| `TestProtectedRules` | 13 — reguły pojedynczych artefaktów |
| `TestProtectedRepoAnalysis` | 3 — mini-repo integracyjne |
| `TestRegressionIFGRepo` | 6 — regresja na repo IFG |

**Nowe testy v1.1:** 22  
**Guardian Platform łącznie:** 268 passed (246 + 22)

### Regression (wymagane AC)

- `alembic/env.py` → **nie DELETE**
- `docs/GUARDIAN_PLATFORM_ARCHITECTURE.md` → **nie DELETE**
- `app/__init__.py` → **nie DELETE**
- `repo orphan` → brak migracji Alembic, `__init__.py`, docs, entrypointów jako ORPHAN/DELETE

### Martwy kod nadal wykrywany

Mini-repo: `scripts/dead_helper.py` → ORPHAN → DELETE (test `test_dead_helper_still_delete`).

---

## 6. Przykłady przed / po

### `scripts/ksef_metadata_probe.py`

| | v1 | v1.1 |
|---|-----|------|
| Status | ORPHAN | ENTRYPOINT |
| Risk | SAFE | MEDIUM |
| Recommendation | DELETE | KEEP |
| Powód | 0 importerów | `__main__` + dokumentacja ops |

### `docs/GUARDIAN_PLATFORM_ARCHITECTURE.md`

| | v1 | v1.1 |
|---|-----|------|
| Status | ORPHAN | PROTECTED |
| Recommendation | DELETE | KEEP |
| Powód | brak importerów Python | documentation artefact |

### `scripts/dead_helper.py` (izolowany helper, mini-repo)

| | v1 | v1.1 |
|---|-----|------|
| Status | ORPHAN | ORPHAN |
| Recommendation | DELETE | DELETE |
| Powód | brak wszystkich refs | bez zmian — prawdziwy kandydat |

---

## 7. Gotowość do cleanup repo

**TAK** — Repo Graph v1.1 jest gotowy do wykorzystania przy cleanup repo:

1. `repo graph` — metryki + false positives prevented  
2. `repo orphan` — tylko prawdziwe osierocone moduły (bez Alembic/docs/init)  
3. `repo dead-code` — kandydaci bez chronionych artefaktów  
4. `repo explain <path>` — weryfikacja przed ARCHIVE/DELETE  

Łączyć z heurystyką nazw z `docs/REPO_CLEANUP_PLAN.md` — Repo Graph decyduje o ryzyku zależności, plan cleanup o wartości historycznej dokumentów.
