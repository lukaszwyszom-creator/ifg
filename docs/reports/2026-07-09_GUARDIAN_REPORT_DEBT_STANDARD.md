# GWO-GUARDIAN-STANDARD — Rozszerzenie standardu raportów o sekcję Debt

**Data:** 2026-07-09  
**Status:** DONE

---

## Cel

Ujednolicić generowanie raportów markdown Guardiana o opcjonalne sekcje **Debt** (UX / Technical / Architecture / Performance) — miejsce na świadomie odłożone obserwacje rozwojowe z realizacji GWO.

**Zakres:** wyłącznie nowe raporty. Historyczne pliki `.md` **nie** modyfikowane.

---

## Zmodyfikowane szablony

### Moduł kanoniczny

| Plik | Rola |
|------|------|
| `scripts/ifg_guardian/core/reporting/debt.py` | `DebtItem`, `ReportDebt`, `append_debt_sections()`, `finish_markdown()`, `resolve_report_debt()` |
| `scripts/ifg_guardian/core/reporting/__init__.py` | Re-export API |
| `scripts/guardian_platform/core/reporting/debt.py` | Re-export do platformy |

### ifg_guardian — `render_markdown` / precheck

| Szablon | Plik |
|---------|------|
| Deploy Run | `plugins/ifg/deploy_run/report.py` |
| Doctor | `plugins/ifg/doctor/report.py` |
| Release Plan | `plugins/ifg/release_plan/report.py` |
| Release Evaluate | `plugins/ifg/release_evaluate/report.py` |
| Container Cutover | `plugins/ifg/container_cutover/report.py` |
| Repo Audit | `core/repo_audit/report.py` |
| EOL Check | `core/repo_audit/eol_check.py` |
| Preflight Precheck | `core/preflight/report.py` |

### guardian_platform

| Szablon | Plik |
|---------|------|
| Generic writer | `core/reporting/writers.py` |
| Deploy | `profiles/ifg/deploy/report.py` |
| Doctor | `profiles/ifg/doctor/report.py` |
| Recover | `profiles/ifg/recover/report.py` |
| Repo Audit | `profiles/ifg/repo_audit/report.py` |
| Repo Cleanup Plan | `profiles/ifg/repo_cleanup/report.py` |

### Reguły i dokumentacja

| Plik | Zmiana |
|------|--------|
| `.cursor/rules/rules_09_reporting.mdc` | Sekcje Debt po E. Następny krok |
| `docs/guardian/core/GUARDIAN_REPORT_DEBT_STANDARD.md` | Standard kanoniczny |

---

## Miejsca wykorzystania

### Automatyczne (Guardian CLI)

Każdy workflow zapisujący raport przez `render_markdown` → `finish_markdown`:

```bash
python scripts/guardian.py ifg doctor --markdown
python scripts/guardian.py ifg deploy run --yes --markdown
python scripts/guardian.py ifg release plan --markdown
# …
```

Debt pojawi się w raporcie **tylko** gdy przekazane:

- argument `debt=` do `render_markdown`, lub
- `state.debt`, lub
- `transaction.audit["debt"]` / `profile_data["debt"]`.

Bez danych — raport bez zmian wizualnych (brak pustych sekcji).

### Ręczne (GWO / Cursor)

Agent kończy raport sekcją E, potem opcjonalnie Debt wg `rules_09_reporting.mdc`.

---

## Przykładowy raport po zmianach

Fragment raportu GWO z `example_gwo_0053_debt()`:

```markdown
# GWO-IFG-0053 — Monitor KSeF UX v2

…

## E. NASTĘPNY KROK

Deploy przez Guardian.

## UX Debt

#### HIGH

Pokazywać "Dzisiaj", "Wczoraj" zamiast wyłącznie daty.

Ułatwia operatorowi szybką orientację czasową.

Szybsze rozpoznanie świeżości procesu bez czytania kalendarza.

Nie wykonano w tym GWO, ponieważ wykracza poza ustalony zakres.

#### MEDIUM

Dodać ikonę typu procesu (zakupy, sprzedaż, sesja).

Poprawia szybkość skanowania listy.

Mniej błędów interpretacji przy wielu równoległych procesach.

Nie wykonano w tym GWO, ponieważ wykracza poza ustalony zakres.

## Technical Debt

#### HIGH

Agregować process_status po stronie backendu.

Frontend nie powinien wyliczać końcowego statusu procesu.

Jedna semantyka statusu dla UI, API i przyszłych klientów.

Nie wykonano w tym GWO, ponieważ wykracza poza ustalony zakres.

## Performance Debt

#### LOW

Grupowanie server-side zamiast frontendowego.

Przydatne dopiero przy bardzo dużej liczbie rekordów.

Mniejszy transfer danych i prostszy UI przy skali.

Nie wykonano w tym GWO, ponieważ wykracza poza ustalony zakres.
```

---

## Wpływ na zgodność wsteczną

| Obszar | Wpływ |
|--------|-------|
| Istniejące raporty `.md` | **Brak** — nie edytowane |
| API `render_markdown` | **Additive** — opcjonalny parametr `debt=None` |
| Raporty bez Debt | **Identyczny wygląd** — `finish_markdown` nie dodaje sekcji |
| JSON schema raportów | **Bez zmian** — Debt tylko w markdown |
| Testy workflow | **Kompatybilne** — domyślnie `debt=None` |

---

## Wyniki testów

```bash
.venv/bin/python -m pytest tests/unit/test_guardian_report_debt.py -q
# 5 passed

.venv/bin/python -m pytest tests/unit/test_guardian_ifg_deploy_run_workflow.py::TestDeployRunReport -q
# PASS (istniejące testy markdown)
```

---

## 🩷 STATUS KOŃCOWY

### ✅ CO DZIAŁA

- Centralny moduł Debt w `ifg_guardian.core.reporting.debt`
- 14 szablonów markdown zaktualizowanych
- Reguła Cursor + dokument kanoniczny
- 5 testów jednostkowych PASS

### ⚠️ ZNANE PROBLEMY

- Raporty GWO pisane ręcznie wymagają dyscypliny operatora/agenta (nie wymuszane automatycznie poza regułą Cursor)

### ❌ CO NIE DZIAŁA

- Brak

## A. ROOT CAUSE (kontekst zadania)

Brak ustandaryzowanego miejsca na obserwacje rozwojowe — wartościowe pomysły ginęły po zakończeniu GWO.

## B. ZMIENIONE PLIKI

Patrz sekcja „Zmodyfikowane szablony”.

## C. DEPLOY

Nie dotyczy — zmiana narzędziowa Guardiana i reguł raportowania.

## D. TESTY

`tests/unit/test_guardian_report_debt.py` — 5/5 PASS.

## E. NASTĘPNY KROK

Przy kolejnych GWO uzupełniać sekcje Debt tylko gdy pojawią się realne obserwacje.

---

## Lista wygenerowanych raportów `.md`

1. `docs/reports/2026-07-09_GUARDIAN_REPORT_DEBT_STANDARD.md`
2. `docs/guardian/core/GUARDIAN_REPORT_DEBT_STANDARD.md`
