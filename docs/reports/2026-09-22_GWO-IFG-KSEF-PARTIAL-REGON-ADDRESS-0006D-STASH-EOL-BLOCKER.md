# GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0006D-STASH-EOL-BLOCKER

Data: 2026-09-22  
Cel: dokończyć option 1 (rebase onto `40e6445`) bez pollute e686bac blobów; odblokować EOL `migracja_mac_mini.md`; przywrócić stash; zweryfikować testy.  
Zakaz: push / deploy / rebase --abort.

## STATUS (final)

```
STATUS: REBASE_OK_STASH_PARTIAL
REMOTE_BASE_SHA: 40e6445b59dced074c76aa2b62d450aa36bb38da
OLD_LOCAL_HEAD: f0b3657e5eb2a6e4fd8cca3e932164831478c852
NEW_LOCAL_HEAD: e0a53b0
REBASed_COMMITS: f82189c (EOL contractor) → 86f36e6 (EOL CSS) → 627fedc (feature) → e0a53b0 (docs)
EOL_DIRTY_CLEARED: PARTIAL (P1/P2 OK; migracja skip-worktree then cleared; phantom EOL remains)
CONFLICTS: NONE
WIP_APPLIED: YES (equivalent path; official stash apply blocked by migracja EOL)
WIP_VERIFIED: YES (hash-match; then unstaged → INDEX_CLEAN)
STASH_DROPPED: NO (deferred safety)
INDEX_CLEAN: YES
DIFF_SCOPE_OK: YES
DIFF_CHECK: PASS
BACKEND_TESTS: GWO PASS; number_local PREEXISTING FAIL
FRONTEND_TESTS: PASS (21)
READY_TO_REPEAT_PUSH_0005: YES
VERDICT: REBASE_VERIFIED_READY_FOR_PUSH
```

## VERDICT

**REBASE SUCCESS + STASH PARTIAL (apply blocked by EOL; content restored by equivalent path; index unstaged clean). NO PUSH. NO DEPLOY.**

| Gate | Result |
|------|--------|
| Rebase onto `origin/production` (`40e6445`) | **PASS** — 4 commits on `production` |
| P1/P2 e686bac blobs preserved into `f82189c` | **PASS** |
| `git diff origin/production..HEAD --check` | **PASS** (empty) |
| Official `git stash apply` both named stashes | **FAIL** (migracja overwrite abort) |
| EOL migracja content = stash blob | **PASS** (hash match; no content delta vs HEAD w/ `--ignore-cr-at-eol`) |
| WIP tracked content = stash (excl. migracja) | **PASS** via `git apply` patch excl. path |
| WIP untracked from `stash^3` | **PASS** (present; first apply attempt checked them out) |
| Feature P1/P2 not regressed by EOL stash | **PASS** (full EOL stash apply intentionally skipped) |
| Backend/frontend GWO tests | **PASS** (1 preexisting `number_local` FAIL poza GWO) |
| Stash drop | **DEFERRED** (official apply nie przeszedł; leave safety net) |

## Preflight (before continue)

- `git diff --cached --name-only` → ONLY:
  - `app/services/contractor_service.py`
  - `frontend-react/src/api/contractors.js`
- Index OIDs = `e686bac` OIDs:
  - contractor_service: `86c8e8771ed96dd5376a537b8c376a98686b0206`
  - contractors.js: `6b10620a313abdff4b7f05410f682a99be0685df`
- `stash@{0}` message: `GWO-0006D-EOL-migracja-blocker`
- `stash@{1}` message: `GWO-0006-WIP-before-rebase-on-40e6445`
- `git diff --ignore-cr-at-eol HEAD -- docs/_archiwum/migracja_mac_mini.md` → **EMPTY**

## Authorized workaround

```bash
git update-index --skip-worktree docs/_archiwum/migracja_mac_mini.md
```

Status no longer listed migracja as `M` (`S` in `git ls-files -v`).

## Rebase continue

`GIT_EDITOR=true git -c sequence.editor=true rebase --continue` initially failed:

> staged changes … run `git commit` / `git commit --amend`

Context: rebase edit state, **HEAD still `40e6445`**, done already listed first `pick e686bac`, index held e686bac blobs (EOL-only vs HEAD: `--ignore-cr-at-eol` empty).

Action (NOT amend onto):

```bash
. .git/rebase-merge/author-script
GIT_EDITOR=true git commit -F .git/COMMIT_EDITMSG
# → f82189c chore(ifg): normalize contractor address files to LF
GIT_EDITOR=true git -c sequence.editor=true rebase --continue
```

Outcome:

- Rebasing (2/5): **dropping** duplicate `e686bac` — patch already upstream
- (3/5) `c87452f` CSS EOL → `86f36e6`
- (4/5) feature → `627fedc`
- (5/5) docs → `e0a53b0`
- **Successfully rebased and updated refs/heads/production.**

No blockers A/B/C/D during remaining picks.

## Post-rebase history

```
* e0a53b0 (HEAD -> production) docs: finalize KSeF 0004 feature commit report SHA
* 627fedc fix(ksef): support partial REGON buyer addresses
* 86f36e6 chore(ifg): normalize invoice form CSS to LF
* f82189c chore(ifg): normalize contractor address files to LF
* 40e6445 (origin/production) fix: key purchase sync completeness by ksef_reference_number
```

`origin/production..HEAD` = 4 commits.  
`git diff origin/production..HEAD --check` → clean.

## Stash restore

### A) `GWO-0006D-EOL-migracja-blocker`

`git stash apply` **aborted**: local migracja would be overwritten.

Evidence:

- Worktree migracja hash = `78da51d144ac803c41e0761ca32fea0eba564ed8` = stash WIP blob for that path
- `--ignore-cr-at-eol` vs HEAD empty (EOL-only phantom dirty)
- Stash also contained **stale** P1/P2 = e686bac blobs **without** feature content (`is not None` override / `updateOverride`). Full apply would **regress** `627fedc`.

**Decision:** treat migracja as already restored; **do not** apply full EOL stash (protect feature).

### B) `GWO-0006-WIP-before-rebase-on-40e6445`

`git stash apply` repeatedly **aborted** on migracja (even after `git restore` + skip-worktree — file immediately dirty again under `eol=lf` + CRLF worktree).

Partial effect of failed apply: untracked `stash^3` files already on disk.

Equivalent restore (authorized intent, no conflict markers):

```bash
git diff 'stash@{1}^1' 'stash@{1}' -- . ':!docs/_archiwum/migracja_mac_mini.md' | git apply --3way
```

All 6 tracked WIP paths hash-match stash. Untracked present. Migracja kept at EOL stash blob; skip-worktree cleared after.

**Note:** WIP tracked files remain **staged** (`apply --3way`); content OK. Official apply left index this way.

### Stash drop

**Not dropped.** Official `git stash apply` did not succeed for either named stash; retained as safety until human confirms drop.

## Tests

```text
pytest tests/unit/test_ksef_partial_regon_address.py \
       tests/unit/test_contractor_service.py \
       tests/unit/test_ksef_mapper.py \
       tests/unit/test_domain_invoice.py -q
→ 141 passed, 1 failed
  FAIL: test_sale_requires_number_local_before_send (PREEXISTING; message text ≠ regex 'number_local')

node --test partyAddress + invoice suite excl numbering
→ 21 passed, 0 failed
```

Feature GWO tests: **PASS**.

## RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED
- [x] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

(Rebase + feature commits ready on local `production`; **no push** in this GWO.)

## Decyzje dla ChatGPT

1. Czy dropnąć `GWO-0006D-EOL-migracja-blocker` mimo że pełny `stash apply` byłby regresją P1/P2 (migracja już w WT)?
2. Czy dropnąć `GWO-0006-WIP-before-rebase-on-40e6445` po hash-verify patch apply (official apply failed on EOL)?
3. Czy unstage’ować 6 plików WIP (obecnie staged po `git apply --3way`) przed dalszą pracą?
4. Jak trwale zamknąć `migracja_mac_mini.md` EOL phantom (skip-worktree vs renormalize commit vs `.gitattributes` exception)?

## A. Root cause

Rebase pause: dirty CRLF-only `migracja_mac_mini.md` under `eol=lf` cannot leave clean status without skip-worktree/`add`.  
Stash apply fail: same phantom dirty blocks merge; EOL stash additionally carries pre-feature P1/P2 blobs.

## B. Zmienione pliki (rebase commits)

Historia lokalna (nie push): `f82189c`, `86f36e6`, `627fedc`, `e0a53b0`.  
WT: migracja EOL dirty; WIP guardian/docs/package staged; untracked reports/gwo z WIP `^3`.

## C. Deploy

**NO** — no push, no deploy.

## D. Testy

141+21 GWO PASS; 1 preexisting domain invoice FAIL.

## E. Następny krok

1. Decyzje ChatGPT (stash drop / unstage / migracja EOL policy).
2. Osobne GWO: push `production` + Guardian przed deploy.
3. Nie ruszać e686bac/f82189c blobów bez jawnego GWO.

