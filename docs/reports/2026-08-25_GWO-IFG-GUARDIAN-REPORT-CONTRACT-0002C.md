# GWO-IFG-GUARDIAN-REPORT-CONTRACT-0002C

**Data:** 2026-08-25  
**Base:** `831c7327540bbf96a434b378601b5def0fcca2c8`  
**Commit:** `42b77faf5b5ba37d250bb76fba1d5ae193dd8235`

---

## ROOT CAUSE: **A — stale test assertion**

Markdown doctor report przeszedł na wspólny kontrakt raportowania w `ed8760b` (`feat: standardize IFG Guardian reporting`).

| Źródło | Kontrakt workflow w markdown |
|--------|------------------------------|
| `scripts/ifg_guardian/core/reporting/renderer.py` | `\| **Workflow** \| \`{summary.workflow}\` \|` |
| `tests/unit/test_guardian_report_standardization.py` | `assert "\| **Workflow** \|" in md` |
| `tests/unit/test_guardian_ifg_doctor_workflow.py` (831c732) | `assert "Workflow ID" in md` ← **przestarzałe** |

**Workflow ID nie zniknęło z raportu** — wartość `transaction.workflow_id` jest w Executive Summary jako komórka tabeli `| **Workflow** | \`2026-05-22T120000Z_ifg_doctor\` |`.

Format terminal (`render_terminal`) nadal używa `Workflow ID: {id}` — to osobny kanał, poza zakresem markdown contract test.

---

## DIFF (jedyny hunk)

```diff
-        assert "Workflow ID" in md
+        assert "| **Workflow** |" in md
```

Plik: `tests/unit/test_guardian_ifg_doctor_workflow.py` (linia 212)

---

## WERYFIKACJA (831c732 + isolated patch)

| Test | Wynik |
|------|-------|
| `TestReportRendering::test_markdown_report` | **1 passed** |
| `test_guardian_ifg_doctor_workflow.py` (cały plik) | **14 passed** |
| Pełny tracked zestaw (7 plików, bez deploy_decision_engine) | **95 passed** |

---

## COMMIT

```
42b77fa test: align doctor markdown contract with standard report table
 tests/unit/test_guardian_ifg_doctor_workflow.py | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)
```

---

## WIP PO COMMICIE (nietknięty)

```
 M docs/GUARDIAN2_RECOVERY_DS723.md
 M docs/_archiwum/migracja_mac_mini.md
 M scripts/ifg_guardian/plugins/ifg/doctor/aggregation.py
 M scripts/ifg_guardian/plugins/ifg/release_plan/stages.py
 M tests/unit/test_guardian_ifg_handoff.py
 M tests/unit/test_guardian_preflight.py
?? docs/gwo/
?? docs/reports/...
?? frontend-react/src/components/invoice/invoiceCardListNumbering.test.js
?? tests/unit/test_guardian_deploy_decision_engine.py
```

---

## Bezpieczeństwo operacyjne

| Akcja | Wynik |
|-------|-------|
| PUSH | **NIE WYKONANY** |
| DEPLOY | **NIE WYKONANY** |
| DS723+ | **NIETKNIĘTY** |

---

## Decyzje dla ChatGPT

Brak.

## GENERATED REPORTS

/Users/lukasz/projekty/ifg_standalone/docs/reports/2026-08-25_GWO-IFG-GUARDIAN-REPORT-CONTRACT-0002C.md
