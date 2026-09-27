# GWO-IFG-REPO-MIGRATION-WORKSPACESSD-0010C

**Data:** 2026-09-27  
**Metoda:** FRESH CLONE + CUTOVER (LaunchAgent cutover **rolled back**)

## RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED
- [x] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

`READY_FOR_DEPLOY` tu = raport/branch gotowe; **nie** oznacza cutover LaunchAgents na SSD. DS723+ nietknięty.

---

## STATUS / VERDICT

```
STATUS: COMPLETE_WITH_RUNTIME_BLOCK
VERDICT: SSD_REPO_OK_RUNTIME_PATH_BLOCKED
```

---

## OUTPUT CONTRACT

```
OLD_REPO: /Users/lukasz/projekty/ifg_standalone
OLD_HEAD: d3571ec068f2d83b451ed3cd4cf3c9ae003beaaa
OLD_STATUS: CLEAN (ROLLBACK_CHECKOUT; LaunchAgents restored here)

NEW_REPO: /Volumes/WorkspaceSSD/projects/ifg_standalone
NEW_HEAD: 082992826b60556177ec1a1a7667d1ee6e53011d (branch gwo/ifg-repo-path-migration-0010c)
NEW_ORIGIN_PRODUCTION: d3571ec068f2d83b451ed3cd4cf3c9ae003beaaa
NEW_STATUS: CLEAN (local `.git/info/attributes` `* -text` — see risks)
NEW_ORIGIN: git@github.com:lukaszwyszom-creator/ifg.git

SSD_MOUNT: /Volumes/WorkspaceSSD (apfs, noowners, RW, ~1.8Ti free)

ENV_RECREATED:
  Python: python3.13 venv + pip install -e ".[dev,guardian]"
  Node: npm ci (package-lock.json, no lockfile edits)

LAUNCHAGENTS_BEFORE:
  com.ifg.guardian.prod-monitor: loaded, not running (interval), cwd OLD, last exit 0
  pl.ifg.dev-bootstrap: loaded, running (pid 1498), cwd OLD

LAUNCHAGENTS_AFTER_ATTEMPT:
  Both pointed at NEW → launchd last exit **78 EX_CONFIG**
  Manual Terminal run of monitor from NEW: PASS (PRODUCTION_RUNNING)
  → TCC / removable-volume access for launchd (volume has noowners)

LAUNCHAGENTS_FINAL:
  ROLLED BACK to OLD paths; monitor last exit 0; bootstrap running

TCC_RESULT: BLOCKED (launchd); NOT_APPLICABLE for interactive Terminal/git

DEV_BOOTSTRAP: FAIL on SSD via launchd; PASS after rollback on OLD (running)
GUARDIAN_PROD_MONITOR: FAIL on SSD via launchd; PASS manual on SSD; PASS after rollback on OLD
PYTHON_SMOKE: PASS (import app + ifg_guardian via PYTHONPATH=scripts)
FRONTEND_BUILD: PASS (vite build, tracked tree clean)

GUARDIAN_PROFILE: UPDATED (branch gwo/ifg-profile-path-0010c)
IFG_MIGRATION_BRANCH: gwo/ifg-repo-path-migration-0010c
IFG_MIGRATION_COMMIT: 082992826b60556177ec1a1a7667d1ee6e53011d
IFG_PR: https://github.com/lukaszwyszom-creator/ifg/pull/1
GUARDIAN_CHANGE: Profiles/IFG.md path + TCC note; branch pushed gwo/ifg-profile-path-0010c

ROLLBACK_CHECKOUT: PRESERVED (/Users/lukasz/projekty/ifg_standalone)
DS723_TOUCHED: NO
KSEF_TOUCHED: NO
DB_TOUCHED: NO
OLD_REPO_DELETED: NO

CANONICAL_REPO_AFTER:
  Git clone on SSD: YES (usable for Cursor/dev)
  LaunchAgent runtime canonical: STILL OLD (until TCC resolved)
```

---

## Evidence — TCC / EX_CONFIG

1. After plist rewrite to WorkspaceSSD, both agents: `last exit code = 78: EX_CONFIG`.
2. Same python one-liner/`-m ifg_guardian.cli prod monitor check` from Terminal in NEW cwd: **exit 0**, `PRODUCTION_RUNNING`.
3. Mount options: `noowners` on `/Volumes/WorkspaceSSD`.
4. Rollback from backups in  
   `~/Library/Application Support/Guardian/ifg-migration-0010c-rollback/`  
   restored OLD paths; agents healthy again.

---

## EOL note (fresh clone dirty)

Fresh clone initially showed ~99 “modified” files: CRLF blobs + `.gitattributes eol=lf`.  
OLD checkout hid this via index stat cache (`size` populated).  
NEW got `size: 0` in index → always rehash → false dirty.

**Mitigation (local only, not committed):**  
`$NEW/.git/info/attributes` contains `* -text` so status is CLEAN without changing `origin/production`.  
Future GWO should renormalize EOL on a dedicated branch.

No skip-worktree / old exclude copied.

---

## Mutations performed

1. Unloaded IFG LaunchAgents; backed up plists.
2. `git clone` → `/Volumes/WorkspaceSSD/projects/ifg_standalone` @ `d3571ec`.
3. Recreated `.venv` + `npm ci`.
4. Branch `gwo/ifg-repo-path-migration-0010c` + commit plist path rewrite; **pushed**; PR #1.
5. Attempted LaunchAgent cutover → EX_CONFIG → **rollback**.
6. Guardian `Profiles/IFG.md` on `gwo/ifg-profile-path-0010c` (path + status note); pushed.

## Not performed

- Delete/rename OLD checkout
- Merge PRs
- Deploy / DS723 / KSeF / DB
- Port WIP snapshot / STOCK branches

---

## RISKS

1. **Split brain:** git/Cursor on SSD vs LaunchAgents on internal until TCC fixed.
2. Local `* -text` attributes mask EOL debt.
3. Do not develop on ROLLBACK_CHECKOUT; keep it only for agents/rollback.
4. Merging IFG PR #1 updates tracked plist to SSD paths while live agents still use OLD — OK for template; coordinate before merge.

## NEXT_ACTION

1. Resolve launchd/TCC for WorkspaceSSD (FDA for launchd wrapper / avoid noowners agent cwd) — then retry LaunchAgent cutover.  
2. Until then: open Cursor on SSD repo; leave agents on OLD.  
3. Hold merge of IFG PR #1 / Guardian profile PR until cutover policy decided.  
4. Optional follow-up GWO: EOL renormalize on production line.

## Decyzje dla ChatGPT

1. Czy do czasu TCC trzymać **split brain** (SSD git + OLD agents), czy rollback SSD jako non-canonical i pracować tylko na OLD?  
2. Czy merge PR #1 (plist SSD paths) teraz, czy dopiero po udanym LaunchAgent cutover?

## GENERATED REPORTS

Ten plik (na SSD checkout).
