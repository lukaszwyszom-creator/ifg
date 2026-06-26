# Guardian Platform — Repository Dependency Graph (Repo Dependency Audit)

**Data:** 2026-06-26  
**Status:** IMPLEMENTED  
**Scope:** Guardian Platform core (`scripts/guardian_platform/core/repository/`)  
**IFG-specific:** brak — funkcja ogólna, profile-agnostic

---

## 1. Cel

Repo cleanup nie może opierać się wyłącznie na nazwach plików (`*FIX*`, `*DIAG*`, `*DEPLOY*`).  
Guardian Platform otrzymał moduł **statycznej analizy zależności**, który przed usunięciem/archiwizacją ocenia rzeczywiste powiązania kodu, testów, dokumentacji, CLI i workflow.

---

## 2. Moduł `core/repository/`

| Plik | Odpowiedzialność |
|------|------------------|
| `models.py` | `FileStatus`, `RiskLevel`, `Recommendation`, grafy, `RepositoryAnalysis` |
| `discovery.py` | Skan plików, AST importów, referencje w docs, CommandSpec |
| `graphs.py` | Budowa 6 grafów |
| `scoring.py` | Ocena ACTIVE/REFERENCED/ORPHAN/UNKNOWN + SAFE/LOW/MEDIUM/HIGH |
| `analyzer.py` | `RepositoryAnalyzer` — orchestracja |
| `report.py` | Raporty markdown + format explain |
| `commands.py` | Handlery CLI |

### Grafy (v1 — statyczna analiza)

1. **Import Graph** — AST `import` / `from … import`, reverse edges, cykle, moduły bez importerów  
2. **Script Graph** — entry point (`__main__`), helper (importowany), unused  
3. **Test Graph** — mapowanie `tests/` → `app/` / `scripts/`, orphan tests, moduły bez testów  
4. **Documentation Graph** — referencje ścieżek `.py` w `docs/`  
5. **CLI Graph** — `CommandSpec` w `guardian_platform/**/*.py` → moduły handlerów  
6. **Guardian Graph** — workflow constants + command → handler mapping  

### Ocena pliku

| Pole | Wartości |
|------|----------|
| Status | `ACTIVE`, `REFERENCED`, `ORPHAN`, `UNKNOWN` |
| Risk | `SAFE`, `LOW`, `MEDIUM`, `HIGH` |
| Recommendation | `KEEP`, `REVIEW`, `ARCHIVE`, `DELETE` |

Metryki: `imports`, `imported_by`, `cli`, `workflow`, `tests`, `docs`.

---

## 3. Komendy CLI (core, top-level)

```bash
python3 -m scripts.guardian_platform repo graph
python3 -m scripts.guardian_platform repo dependencies
python3 -m scripts.guardian_platform repo orphan
python3 -m scripts.guardian_platform repo dead-code
python3 -m scripts.guardian_platform repo impact <path>
python3 -m scripts.guardian_platform repo explain <path>
```

Globalne flagi: `--format terminal|json|markdown`.

### Przykład `repo explain`

```
scripts/guardian.py

Imports: 2
Imported by: 0
CLI: 0
Workflow: 0
Tests: 0
Docs: 26

Risk: LOW
Recommendation: REVIEW
```

*(Wysokie `docs` bez importerów → REVIEW, nie DELETE — dokumentacja wskazuje na plik.)*

---

## 4. Raporty

Generowane automatycznie przez komendy graph / orphan / dead-code:

| Plik | Komenda |
|------|---------|
| `docs/reports/repository_graph.md` | `repo graph` |
| `docs/reports/repository_orphans.md` | `repo orphan` |
| `docs/reports/repository_dead_code.md` | `repo dead-code` |

---

## 5. Integracja

- Rejestracja w `CoreProfile.register()` (`core/profiles/builtin.py`) — 6 nowych `CommandSpec`  
- `core/cli/app.py` — przekazywanie `remainder` do handlerów (`impact`, `explain`)  
- **Nie zmieniono:** profil IFG, legacy `guardian.py`, `ifg_guardian/`, istniejące komendy core/profile  

---

## 6. Testy

Nowy plik: `tests/guardian_platform/test_repository_graph.py`

| Klasa | Zakres |
|-------|--------|
| `TestDiscovery` | import resolution, doc refs |
| `TestGraphs` | 4 grafy na mini-repo |
| `TestScoring` | orphan DELETE, core KEEP, impact chain |
| `TestAnalyzer` | pełna analiza mini-repo |
| `TestReports` | zapis 3 raportów |
| `TestRepositoryCLI` | 6 komend CLI |
| `TestRegistry` | rejestracja + regresja `repo audit` |

**Nowe testy:** 23  
**Guardian Platform łącznie:** 246 passed (223 + 23)

---

## 7. Ograniczenia v1

- Analiza statyczna (AST + regex) — brak runtime / dynamic imports  
- Skan domyślny: `app/`, `scripts/`, `tests/`, `agent/`, `alembic/`  
- CLI Graph oparty o regex `CommandSpec` — nie pełny AST  
- Importy zewnętrzne (`fastapi`, `pytest`) ignorowane  
- Rekomendacja `DELETE` wymaga ręcznej akceptacji — Guardian nie usuwa plików  

---

## 8. Wykorzystanie przy cleanup repo

1. `repo graph` — pełny obraz zależności  
2. `repo orphan` + `repo dead-code` — kandydaci z metrykami (nie tylko nazwy)  
3. `repo explain <path>` — weryfikacja pojedynczego pliku przed ARCHIVE/DELETE  
4. `repo impact <path>` — blast radius przed usunięciem  

**Gotowość:** Repo Graph jest gotowy do wsparcia Fazy 1–3 cleanup (`docs/REPO_CLEANUP_PLAN.md`) jako warstwa decyzyjna obok klasyfikacji heurystycznej.
