# Guardian Canonical Check — `repo.eol_check`

**Data:** 2026-07-06  
**Status:** CANONICAL (read-only check, v1)  
**Check ID:** `repo.eol_check`  
**CLI:** `python3 -m ifg_guardian repo eol-check`  
**Moduł:** `scripts/ifg_guardian/core/repo_audit/eol_check.py`

---

## 1. Cel

Guardian musi **niezależnie** od operatora rozstrzygnąć, czy pliki oznaczone przez Git jako zmodyfikowane (`M`) zawierają:

- wyłącznie różnice końców linii (CRLF/LF), czy
- realną zmianę logiczną treści.

Check jest **read-only**. Nie wykonuje `git restore`, renormalizacji, commitów, push, deploy ani cutover.

---

## 2. Zakres v1

| Element | Opis |
|---------|------|
| Wejście | `git status --porcelain` — tracked modified files |
| Metoda | `git diff HEAD` vs `git diff HEAD --ignore-cr-at-eol` per plik |
| Klasyfikacja | `EOL_ONLY`, `LOGICAL_CHANGE`, `UNKNOWN` |
| Werdykt | `GO`, `GO_WITH_CAUTION`, `NO_GO` |
| Raport | Markdown (domyślnie `docs/guardian/EOL_CHECK_YYYY_MM_DD.md`) |

### Relacja do `repo audit`

`core.repo.audit` zawiera stage `line_ending_analysis` (głębsza analiza blobów HEAD/index/worktree).  
**`repo.eol_check`** jest **kanonicznym gate** przed release/cutover — prostszy kontrakt oparty wyłącznie na diff git, z twardym werdyktem GO/NO-GO.

---

## 3. Algorytm klasyfikacji (per plik)

Dla każdego tracked modified file:

```bash
git diff HEAD --quiet -- <path>                    # normal_diff = exit != 0
git diff HEAD --ignore-cr-at-eol --quiet -- <path> # ignore_cr_diff = exit != 0
```

| normal_diff | ignore_cr_diff | Klasyfikacja |
|-------------|----------------|--------------|
| false | * | `UNKNOWN` — status M bez diff vs HEAD |
| true | false | `EOL_ONLY` |
| true | true | `LOGICAL_CHANGE` |

---

## 4. Werdykt release / cutover

| Warunek | Werdykt | Znaczenie |
|---------|---------|-----------|
| Brak tracked modified | `GO` | Czysty stan względem EOL |
| Wszystkie pliki `EOL_ONLY` | `GO_WITH_CAUTION` | **Nie pełne GO** — szum EOL; normalize/restore wymaga osobnej zgody operatora |
| Jakikolwiek `LOGICAL_CHANGE` | `NO_GO` | Commit lub discard przed push/release/cutover |
| Jakikolwiek `UNKNOWN` | `NO_GO` | Ręczna analiza wymagana |

**Zasada:** Guardian **nie** normalizuje plików automatycznie.

---

## 5. CLI

```bash
# Terminal (domyślnie) + raport w docs/guardian/
PYTHONPATH=scripts python3 -m ifg_guardian repo eol-check

# Markdown na stdout + raport
PYTHONPATH=scripts python3 -m ifg_guardian repo eol-check --markdown

# JSON
PYTHONPATH=scripts python3 -m ifg_guardian repo eol-check --json

# Własna ścieżka raportu
PYTHONPATH=scripts python3 -m ifg_guardian repo eol-check --report docs/reports/MY_EOL_CHECK.md
```

**Exit code:** `0` dla `GO` i `GO_WITH_CAUTION`; `1` dla `NO_GO`.

---

## 6. Struktura raportu

1. Check ID, branch, HEAD, werdykt  
2. Rekomendacja operacyjna  
3. Podsumowanie liczników  
4. Listy: EOL-only / logical / unknown  
5. Tabela per-file  
6. Legenda gate release/cutover  

---

## 7. Testy

`tests/unit/test_guardian_eol_check.py`:

- klasyfikacja `classify_from_diff_flags` (EOL vs logical vs unknown),
- werdykt `compute_verdict`,
- integracja na tymczasowym repo git (EOL-only i logical change).

---

## 8. Ograniczenia v1

- Porównanie względem `HEAD` (staged + unstaged łącznie).
- Nie klasyfikuje untracked, deleted-only, submodule.
- `UNKNOWN` przy fałszywym `M` (identyczna treść, filtry Git) — wymaga ręcznej decyzji.
- Nie zastępuje pełnego `repo audit` ani preflight cutover.

---

*Check kanoniczny v1. Rozszerzenia (integracja preflight, doctor) wymagają osobnego GWO.*
