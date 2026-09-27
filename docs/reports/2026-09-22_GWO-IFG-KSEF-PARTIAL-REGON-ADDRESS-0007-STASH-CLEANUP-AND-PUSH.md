# GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0007 — STASH CLEANUP AND PUSH

Date: 2026-09-22  
Scope: Stash redundancy cleanup + fast-forward push `production` → `origin/production`  
NO deploy. NO force push.

## STATUS

```
STATUS: PASS
HEAD: e0a53b0bf673f2243fca90d522edf999622224ae
origin/production: e0a53b0bf673f2243fca90d522edf999622224ae
ls-remote production: e0a53b0bf673f2243fca90d522edf999622224ae
PUSH: OK (40e6445..e0a53b0, no --force)
STASH_DROPPED:
  - GWO-0006D-EOL-migracja-blocker (was 4a3d261 / stash@{0})
  - GWO-0006-WIP-before-rebase-on-40e6445 (was e3b56b9 / became stash@{0} after first drop)
STASH_REMAINING:
  - stash@{0}: gwo-0064-temp-gate-check
  - stash@{1}: wip guardian async docs before ksef numbering deploy
SKIP_WORKTREE_CLEARED: YES (Git 2.54: H=normal tracked; S/h nie ustawione)
WIP: STILL_PRESENT (tracked M + untracked reports/gwo/tests)
DEPLOY: NOT_DONE
VERDICT: PUSH_VERIFIED
READY_FOR_DEPLOY_PREFLIGHT: YES
```

---

🩷 STATUS KOŃCOWY

✅ Co działa
- ETAP 1 preflight: ALL PASS (`HEAD` e0a53b0…, `origin/production` was 40e6445…, ahead 4 behind 0, INDEX_CLEAN, `--check` exit 0, WIP present).
- Both target stashes verified redundant before drop; dropped only those two.
- Fast-forward push `production` → `origin/production` succeeded without force.
- Post-verify: `HEAD` = `origin/production` = `ls-remote` = `e0a53b0bf673f2243fca90d522edf999622224ae`.
- WIP dirtiness preserved in working tree (not committed).

⚠️ Znane problemy
- `docs/_archiwum/migracja_mac_mini.md` remains dirty (EOL); intentional; not committed/normalized.
- File flagged `H` (assume-unchanged) in `git ls-files -v`; skip-worktree was not set so `--no-skip-worktree` not required.
- Unrelated stashes kept for later work.

❌ Co nie działa
- Brak (w zakresie GWO-0007).

## A. Root cause

Rebase/push path left two safety stashes that duplicated working-tree / already-committed feature content. Applying them would have been harmful (P1/P2 regression) or a no-op (WIP already restored). Cleanup + FF push unblocks remote alignment without deploy.

## B. Zmienione pliki

- **Git only:** dropped 2 stashes; pushed 4 commits already on local `production`.
- **Report:** this file (`docs/reports/2026-09-22_GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0007-STASH-CLEANUP-AND-PUSH.md`).
- **No app code changes** in this GWO.

## C. Deploy

NOT DONE (explicitly out of scope).

## D. Testy / dowody

### ETAP 1 PREFLIGHT

| Check | Result |
|-------|--------|
| `git fetch origin --prune` | OK |
| HEAD starts with `e0a53b0` | PASS `e0a53b0bf673f2243fca90d522edf999622224ae` |
| `origin/production` == `40e6445b59dced074c76aa2b62d450aa36bb38da` | PASS (pre-push) |
| `status -sb` ahead 4, behind 0 | PASS |
| `git diff --cached --stat` empty | PASS INDEX_CLEAN |
| `git diff origin/production..HEAD --check` | exit 0 |
| WIP present | PASS (package.json, guardian scripts/tests, migracja, reports, …) |

### ETAP 2 STASH ANALYSIS

**stash GWO-0006D-EOL-migracja-blocker** (`4a3d261`):

Files: `app/services/contractor_service.py`, `docs/_archiwum/migracja_mac_mini.md`, `frontend-react/src/api/contractors.js`

| Path | Verdict |
|------|---------|
| `contractor_service.py` | Stash older than HEAD: would change `if override_value is not None` → `if override_value` (REGRESS). HEAD has feature. Not unique needed. |
| `contractors.js` | Stash older: would remove `updateOverride`. HEAD has feature. Not unique needed. |
| `migracja_mac_mini.md` | Normalized LF equal WT↔stash (`norm_eq=True`); raw differs by EOL only. Intentional skip / EOL OK. |

**stash GWO-0006-WIP-before-rebase-on-40e6445** (`e3b56b9`):

Tracked: all 7 paths `norm_eq=True` with WT (migracja raw EOL-only diff).  
Untracked (`^3`): 16 paths all present in WT with identical content (`OK`).  
No P1/P2 contractor feature paths in this stash; applying would not add unique needed content.

**Drop:** both redundant → dropped. Remaining: `gwo-0064-temp-gate-check`, `wip guardian async docs before ksef numbering deploy`.

### ETAP 3 EOL POLICY

- `git ls-files -v | grep migracja` → `H docs/_archiwum/migracja_mac_mini.md` (assume-unchanged).
- skip-worktree **not** set → no `--no-skip-worktree`.
- File left dirty EOL; no commit/normalize/gitignore.

### ETAP 4 PUSH GATE

Exactly 4 commits `origin/production..HEAD` (bottom→top):

1. `f82189c` chore(ifg): normalize contractor address files to LF  
2. `86f36e6` chore(ifg): normalize invoice form CSS to LF  
3. `627fedc` fix(ksef): support partial REGON buyer addresses  
4. `e0a53b0` docs: finalize KSeF 0004 feature commit report SHA  

`--check` exit 0.

### ETAP 5 PUSH

```
git push origin production
# 40e6445..e0a53b0  production -> production
```

No `--force` / `--force-with-lease`.

### ETAP 6 VERIFY

| Ref | SHA |
|-----|-----|
| HEAD | `e0a53b0bf673f2243fca90d522edf999622224ae` |
| origin/production | `e0a53b0bf673f2243fca90d522edf999622224ae` |
| ls-remote refs/heads/production | `e0a53b0bf673f2243fca90d522edf999622224ae` |

`git status -sb`: `production...origin/production` (synced) + WIP still dirty.

## E. Następny krok

- Optional: separate GWO for deploy/verify on DS723 if product wants production rollout.
- Keep WIP local until intentional commit(s).
- Do not apply remaining stashes without re-diff vs WT.

## RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED
- [x] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

Note: code already on `origin/production` via FF push; runtime deploy/verify not performed in this GWO → marked READY_FOR_DEPLOY (git remote aligned), not DEPLOYED_TO_DS723.

## Decyzje dla ChatGPT

Brak.

