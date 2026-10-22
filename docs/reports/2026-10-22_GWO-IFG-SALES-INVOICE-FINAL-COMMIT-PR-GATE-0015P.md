# GWO-IFG-SALES-INVOICE-FINAL-COMMIT-PR-GATE-0015P

**Date:** 2026-10-22  
**Worktree:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015`  
**Branch:** `gwo/ifg-sales-invoice-elegant-0015`  
**PRE_COMMIT_HEAD:** `b6e82da866cee7f920a58d7b2bb943f7f17fa42d`

## PREFLIGHT

```
pwd=/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015
branch=gwo/ifg-sales-invoice-elegant-0015
WORKTREE_MATCH=YES
```

## Scope policy (commit)

**INCLUDED (production locked binder + audit):**
- `sale_invoice_locked_*`, paginator/row_measure
- `app/assets/invoice/sale_locked/**` (runtime underlay/fields/profile/glass)
- `app/assets/invoice/stained_glass.png` + README (existing elegant asset contract)
- `pdf_service.py` sale → locked bind
- `pdf_sale_elegant.py` (helpers still used; prior PR #6 surface)
- unit tests: locked / paginator / production bind / prebmerge / pdf_service
- GWO reports 0015F…0015P
- scripts: `render_sale_invoice_production_bind_0015o.py`, `render_sale_invoice_prebmerge_0015o_a.py`

**EXCLUDED (left untracked WIP — not deleted):**
- `layout_shell/`, `sale_template/`, `frozen_sales_invoice.py`
- `docs/design_refs/**`
- intermediate POC scripts (`render_*0015l*`, `0015m*`, `0015n*`, frozen)
- `/temp` PNG/PDF artefacts

## Test gate

| Suite | Result |
|-------|--------|
| sale targeted + pdf + paginator | **116 passed** |
| prebmerge 0015O-A | **4 passed** (in suite) |
| purchase regression | **PASS** (+ 6 pdf purchase-filtered) |
| ksef_status 5 FAIL | **KNOWN_BASELINE_FAILURE** — fingerprint match 0015O-A |

### KSeF fingerprint (unchanged)

```
TypeError: '<=' not supported between instances of 'MagicMock' and 'datetime.datetime'
mock: _get_active_db_session
runtime: _get_active_online_session
tests:
  test_connected_for_active_non_expired_session
  test_disconnected_for_expired_session
  test_disconnected_for_missing_session
  test_probe_failure_below_threshold_keeps_connected_status
  test_probe_counter_resets_after_success
```

## Follow-up debt (do NOT fix in PR #6)

**GWO candidate:** `GWO-IFG-KSEF-STATUS-API-TEST-MOCK-DRIFT`  
Fix unit tests to mock `_get_active_online_session` (or align wrapper usage). Baseline-identical; unrelated to sales invoice binder.

## Constraints preserved

```
LAYOUT_CHANGED=NO
BACKGROUND_ASSET_MUTATED=NO
FIELDS_JSON_MUTATED=NO
PAGINATOR_CHANGED=NO
MERGE_PERFORMED=NO
DEPLOY_PERFORMED=NO
```

## RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED
- [x] READY_FOR_DEPLOY  → interpreted as **READY_FOR_MERGE** (no DS723 deploy in this GWO)
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED
