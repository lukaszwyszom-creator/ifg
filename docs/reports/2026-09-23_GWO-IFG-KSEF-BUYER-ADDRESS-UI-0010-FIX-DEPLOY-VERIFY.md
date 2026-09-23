# GWO-IFG-KSEF-BUYER-ADDRESS-UI-0010 — FIX / DEPLOY / VERIFY

**Date:** 2026-09-23
**GWO:** GWO-0010 ETAP 6 (selective commit + push; NO deploy yet)
**Branch:** `production`
**STATUS:** in progress (code pushed; deploy not started)

## SHAs

| Field | Value |
|-------|-------|
| BASE_HEAD (pre-commit) | `e0a53b0bf673f2243fca90d522edf999622224ae` |
| COMMIT_SHA (feature) | `8259a5491098ad0942c9da82e22e1fd0175323f0` |
| REMOTE_SHA | TBD after `git push origin production` |
| DOCS_COMMIT_SHA | TBD (this report commit) |

## ROOT_CAUSE

- Address editor existed but gated on `buyerInfo` only (hidden until lookup)
- Subtle CSS made section easy to miss
- KSeF message lacked path to Adres nabywcy
- Stale nginx `ifg-frontend:32768` lacks feature (API /ui has it)

## Scope of this ETAP

Selective commit + push of buyer address UI fix only. **No deploy** in this step.

### Feature commit files

- `frontend-react/src/components/invoice/partyAddress.js`
- `frontend-react/src/components/invoice/partyAddress.test.js`
- `frontend-react/src/components/invoice/InvoiceForm.jsx`
- `frontend-react/src/components/invoice/InvoiceForm.module.css`
- `frontend-react/src/components/invoice/InvoiceActions.jsx`

### Explicitly excluded

- `frontend-react/package.json`
- Guardian scripts / unit tests
- `docs/_archiwum/migracja_mac_mini.md`
- Other unrelated dirty/untracked docs

## Pre-push gates

- Local HEAD before commit: `e0a53b0` on `production`
- `git fetch origin --prune`: `origin/production` still `e0a53b0` (ahead 0)
- `git diff --cached --check`: PASS
- Staged set verified: only the five feature files above

## Next (not this ETAP)

- Deploy to DS723 / nginx frontend refresh
- Production verify Adres nabywcy visible before REGON lookup
- Mark RELEASE STATE after deploy + health

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

Brak.
