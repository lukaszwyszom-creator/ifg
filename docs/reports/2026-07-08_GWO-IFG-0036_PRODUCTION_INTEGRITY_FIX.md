# GWO-IFG-0036 — Production Integrity Fix

**Data:** 2026-07-08  
**Branch:** `production`  
**Zakres:** naprawa regresji Monitor KSeF + polityka dirty working tree w Guardianie

---

## 1. Naprawione regresje

### A. HTTP 500 na `GET /api/v1/transmissions/`

**Przyczyna:** `TransmissionORM.invoice_id` jest nullable (wpisy journal KSeF), ale `TransmissionResponse.invoice_id` wymagał `UUID`.

**Naprawa:** `invoice_id: UUID | None = None` w `app/schemas/transmission.py`.

**Test:** `TestListTransmissions::test_list_includes_journal_entry_with_null_invoice_id` — lista zwraca 200 dla wpisu `SESSION_RENEWED` z `invoice_id=null`.

### B. Frontend — rename „Transmisje KSeF” → „Monitor KSeF”

Zweryfikowane miejsca:

| Miejsce | Status |
|---------|--------|
| Zakładka `AdvancedDashboard.jsx` | Monitor KSeF |
| Nagłówek `TransmissionTable.jsx` | Monitor KSeF |
| Tooltip `invoiceOpenMode.js` | Monitor KSeF |
| Bundle po `npm run build` | `Monitor KSeF`: 2 wystąpienia, `Transmisje KSeF`: 0 |

### C. UX — diagnostyka błędów ładowania

Nowy helper `frontend-react/src/utils/transmissionLoadError.js`:

- loguje szczegóły do `console.error` (URL, status, response, obecność auth header),
- mapuje 401 / 403 / 404 / 500 na czytelne komunikaty,
- nie pokazuje stack trace użytkownikowi.

---

## 2. Zmodyfikowane pliki

### IFG (backend + frontend)

- `app/schemas/transmission.py`
- `tests/unit/test_transmission_api.py`
- `frontend-react/src/components/dashboard/TransmissionTable.jsx`
- `frontend-react/src/components/invoice/invoiceOpenMode.js`
- `frontend-react/src/utils/transmissionLoadError.js` *(nowy)*

### Guardian / Release Engine

- `scripts/ifg_guardian/core/preflight/models.py`
- `scripts/ifg_guardian/core/preflight/checks.py`
- `scripts/ifg_guardian/core/preflight/engine.py`
- `scripts/ifg_guardian/plugins/ifg/deploy_run/preflight_stage.py`
- `scripts/ifg_guardian/plugins/ifg/deploy_run/workflow.py`
- `scripts/ifg_guardian/plugins/ifg/deploy_run/stages.py`
- `scripts/ifg_guardian/plugins/ifg/deploy_run/models.py`
- `scripts/ifg_guardian/plugins/ifg/deploy_run/report.py`
- `scripts/ifg_guardian/plugins/ifg/release_evaluate/models.py`
- `scripts/ifg_guardian/plugins/ifg/release_evaluate/policy_engine.py`
- `scripts/ifg_guardian/plugins/ifg/release_evaluate/stages.py`
- `scripts/ifg_guardian/modules/ifg_deploy_run.py`
- `scripts/ifg_guardian/modules/ifg_release_evaluate.py`
- `scripts/ifg_guardian/cli.py`
- `scripts/ifg_guardian/policies/ifg_production.yaml`

### Testy

- `tests/unit/test_guardian_preflight.py`
- `tests/unit/test_guardian_ifg_release_evaluate_workflow.py`
- `tests/unit/test_guardian_ifg_deploy_run_workflow.py`

---

## 3. Nowa polityka Guardiana (dirty working tree)

**Domyślnie (production LIVE):**

```
dirty working tree → BLOCKED
```

Komunikat operatora:

> Production deployment blocked. Working tree contains uncommitted changes.

**Warstwy egzekucji:**

1. **Release Engine** — reguła `dirty_working_tree_blocks_production` → `PRODUCTION_BLOCKED`
2. **Deploy InitStage** — fail-fast przed mutacjami (ten sam komunikat)
3. **Preflight `check_git_clean`** — `FAIL` na LIVE (Safety Gate `NO_GO`)
4. **PreflightStage** — podpięty do workflow `ifg.deploy.run` (przed build pipeline)

**Override jawny:** `--allow-dirty-build`

- logowany w raporcie deploy (`allow_dirty_build_override: true`),
- obniża Release Score o 25 pkt,
- decyzja Release Engine: `READY_WITH_OVERRIDE`,
- ostrzeżenie w Deploy Report i Release Evaluate.

---

## 4. Czy deploy z dirty tree jest nadal możliwy?

**Tak — wyłącznie z jawnym override.**

---

## 5. Jak uruchomić deploy z dirty tree

```bash
# 1. Ocena z override (opcjonalnie, dla podglądu decyzji)
PYTHONPATH=scripts python3 scripts/guardian.py release evaluate --allow-dirty-build

# 2. Deploy LIVE z override
PYTHONPATH=scripts python3 scripts/guardian.py ifg deploy run --allow-dirty-build --yes
```

Bez `--allow-dirty-build` deploy LIVE kończy się blokadą na etapie evaluate / init / preflight.

---

## 6. Wyniki testów

```text
pytest tests/unit/test_transmission_api.py \
       tests/unit/test_guardian_preflight.py \
       tests/unit/test_guardian_ifg_deploy_run_workflow.py \
       tests/unit/test_guardian_ifg_release_evaluate_workflow.py

45 passed in 1.03s
```

Frontend build: `npm run build` — SUCCESS (brak „Transmisje KSeF” w `dist/assets/*.js`).

---

## 7. Guardian Doctor

```text
PYTHONPATH=scripts python3 scripts/guardian.py ifg doctor --dry-run --no-progress
Status: BLOCKED
```

*(dry-run: alembic/health/remote pominięte; lokalne repo dirty — zgodne z oczekiwaniem w trakcie prac)*

---

## 8. Release Engine

**Bez override (dirty tree):**

```text
Decision: PRODUCTION_BLOCKED
Release Score: 86/100
Blocker: Production deployment blocked. Working tree contains uncommitted changes.
Rule: dirty_working_tree_blocks_production
```

**Z `--allow-dirty-build`:**

```text
Decision: READY_WITH_OVERRIDE
Release Score: 61/100  (kara -25)
Warning: Production build from dirty working tree (--allow-dirty-build).
Rule: dirty_tree_build_with_override
```

---

## 9. Decyzja deploy

### NOT READY FOR DEPLOY

**Uzasadnienie:** working tree nadal zawiera niezacommitowane zmiany GWO-IFG-0036. Po commit na `production` i ponownej ocenie Release Engine (bez dirty tree) status powinien przejść na `READY_FOR_DEPLOY` / `READY_WITH_WARNINGS`.

---

## Podsumowanie operacyjne

### Wykonane analizy

- Root cause HTTP 500: nullable `invoice_id` w ORM vs required w Pydantic
- Audyt stringów frontend „Transmisje KSeF” / „Monitor KSeF”
- Audyt GWO-IFG-0035: deploy z LOCAL_NPM na dirty tree
- Przegląd workflow `ifg.deploy.run`, PreflightStage, Policy Engine

### Wykonane raporty

- `docs/reports/2026-07-08_GWO-IFG-0036_PRODUCTION_INTEGRITY_FIX.md` (ten dokument)
- `docs/guardian/IFG_DOCTOR_2026_07_07.md` (doctor dry-run)
- `docs/guardian/IFG_RELEASE_EVALUATE_2026_07_07.md` (release evaluate)

### Nowe reguły Policy Engine

| ID reguły | Warunek | Decyzja |
|-----------|---------|---------|
| `dirty_working_tree_blocks_production` | dirty tree, brak override | `PRODUCTION_BLOCKED` |
| `dirty_tree_build_with_override` | dirty tree + `--allow-dirty-build` | `READY_WITH_OVERRIDE` (score -25) |

---

🩷 STATUS KOŃCOWY

✅ Co działa
- `GET /api/v1/transmissions/` akceptuje wpisy journal z `invoice_id=NULL`
- Frontend: pełny rename „Monitor KSeF”, lepsza diagnostyka 401/403/404/500
- Guardian: dirty tree blokuje production deploy domyślnie
- Override `--allow-dirty-build` działa i jest audytowany

⚠️ Znane problemy
- Zmiany GWO-IFG-0036 niezacommitowane — Release Engine: `PRODUCTION_BLOCKED`
- Doctor dry-run: `BLOCKED` (repo dirty + alembic niedostępny lokalnie w dry-run)

❌ Co nie działa
- Deploy produkcyjny bez commitu / bez override (zamierzone zachowanie)

**A. Root cause** — schema mismatch + deploy z dirty LOCAL_NPM bez polityki blokującej  
**B. Zmienione pliki** — patrz sekcja 2  
**C. Deploy** — NOT READY (wymaga commit + evaluate)  
**D. Testy** — 45/45 passed (zakres GWO)  
**E. Następny krok** — commit na `production`, `release evaluate`, deploy po `READY_*`
