# GWO-IFG-KSEF-STATUS-API-TEST-MOCK-DRIFT-0016

**Date:** 2026-10-23  
**BASELINE_SHA:** `7ecfa95d941956171c89cc0c607c26b3bd771245`  
**Branch:** `gwo/ifg-ksef-status-api-test-mock-drift-0016`  
**Worktree:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-ksef-status-mock-0016`  
*(canonical `/Volumes/WorkspaceSSD/projects/ifg_standalone` had unrelated WIP on `gwo/ifg-invoice-template-polish-0014` — not touched)*

## Root cause (confirmed on production HEAD)

| | |
|--|--|
| OLD_MOCK_TARGET | `_get_active_db_session` |
| RUNTIME_TARGET | `_get_active_online_session` (`get_connection_status` L423) |
| Effect | Mock unused → real lookup on MagicMock session → `expires_at` MagicMock `<=` datetime → TypeError → `ui_status=ERROR` |

`ROOT_CAUSE_CONFIRMED=YES` (same as 0015O-A/Q).

## Fix (test-only)

`tests/unit/test_ksef_status_api.py`:
- patch `_get_active_online_session` instead of `_get_active_db_session`
- missing-session: also stub `purchase_auth._find_purchase_auth_record → None` (post-session fallback path)
- network-error probe: give orm a real `expires_at` so early probes don’t TypeError

**RUNTIME_CHANGED=NO · INVOICE_CHANGED=NO · DB_CHANGED=NO**

## Tests

| Suite | Result |
|-------|--------|
| Previously failing 5 (+ network) | **6 passed** |
| `test_ksef_status_api.py` | **9 passed** |
| `tests/unit/test_ksef*.py` + poll | **387 passed** |
| Full `tests/unit` (ignore openpyxl-missing export test) | **1573 passed**, 22 failed |

### Full-suite failures classification

Baseline @ `7ecfa95` **without** fix: **27 failed** (22 pre-existing + 5 ksef).  
With fix: **22 failed** — identical pre-existing set; **NEW_REGRESSIONS=NO**.

Pre-existing (out of scope): guardian GDD/handoff/plugins, invoice numbering/transitions/domain, PDF API tests needing weasy/fonts env, etc.

## Gates

```
MERGE_PERFORMED=NO
DEPLOY_PERFORMED=NO
```
