# GWO-IFG-DEV-BOOTSTRAP-DEMOTION-0010F

**Date:** 2026-09-28  
**Branch:** `gwo/ifg-dev-bootstrap-demotion-0010f`

## OUTPUT

```
STATUS: DEV_BOOTSTRAP_DEMOTED_PR_PENDING
VERDICT: DEV_BOOTSTRAP_DEMOTED_PR_PENDING
CANONICAL_REPO: /Volumes/WorkspaceSSD/projects/ifg_standalone
CANONICAL_HEAD: (branch tip after commit)
DEV_BOOTSTRAP_PURPOSE: Developer convenience — LaunchAgent KeepAlive running node+Vite (port 3000) from checkout; optional background docker compose up for local db/api/worker if /health fails. Not required by prod-monitor, Guardian supervisor, or DS723 production.
DEPENDENTS: NONE (no IFG/Guardian LaunchAgent or prod service depends on pl.ifg.dev-bootstrap)
DECISION: DEMOTE
LAUNCHAGENT_BEFORE: loaded KeepAlive; Program=node …/projekty/ifg_standalone/…/dev-bootstrap.mjs; WD=OLD frontend-react; logs under OLD .logs; pid running Vite
LAUNCHAGENT_AFTER: not loaded; plist removed from ~/Library/LaunchAgents (recoverable copy under Application Support/Guardian/ifg-dev-bootstrap-0010f-rollback/)
MANUAL_DEV_WORKFLOW: cd canonical/frontend-react && npm run dev | npm run dev:bootstrap (see docs/guardian/DEV_BOOTSTRAP_MANUAL.md)
MANUAL_DEV_SMOKE: PASS (Vite from SSD cwd, /ui/login HTTP 200, stop freed :3000)
PROD_MONITOR_OLD_DEPENDENCY: NONE
DEV_BOOTSTRAP_OLD_DEPENDENCY: NONE
ACTIVE_OLD_CHECKOUT_DEPENDENCY: NONE (IFG runtime/LaunchAgents); note: Cursor agent-worker may still list OLD as worker-dir (IDE, not IFG)
OLD_CHECKOUT: /Users/lukasz/projekty/ifg_standalone branch=production HEAD=d3571ec (behind origin/production)
OLD_CHECKOUT_DISPOSITION: READY_FOR_ARCHIVE_OR_REMOVAL
TRACKED_CHANGES: demoted plist template, DEV_BOOTSTRAP_MANUAL.md, package.json dev:bootstrap, GDD-0021..0023, this report
BRANCH: gwo/ifg-dev-bootstrap-demotion-0010f
COMMIT: (filled after commit)
PR: (filled after open)
DS723_TOUCHED: NO
KSEF_TOUCHED: NO
DB_TOUCHED: NO
NEXT_GWO: GWO-IFG-OLD-CHECKOUT-CLEANUP-0010G
```

## Audit summary

| Question | Answer |
|----------|--------|
| What does it run? | `node …/dev-bootstrap.mjs` → Vite; optional local docker compose |
| KeepAlive why? | Auto-restart Vite after reboot / crash — developer convenience |
| Prod-monitor depend? | No |
| Needed after reboot? | No (manual npm is enough) |

## LAMUS / GDD (not implemented)

- GDD-0021 rollback runner edge case  
- GDD-0022 atomic materialize  
- GDD-0023 SOURCE_SHA / deployed_sha audit semantics  

## RELEASE STATE

- [x] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

(Docs + local LaunchAgent demotion only — no DS723 app deploy.)
