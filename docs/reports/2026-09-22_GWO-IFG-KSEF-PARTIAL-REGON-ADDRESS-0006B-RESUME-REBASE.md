# GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0006B-RESUME-REBASE

Data: 2026-09-22  
Cel: odblokować rebase paused przy `e686bac` — **bez abort / bez push / bez deploy**.

## STATUS (final tego przebiegu)

```
STATUS: STOP_CONTINUE_BLOCKED_BY_UNAUTHORIZED_EOL_MIGRANJA
REMOTE_BASE_SHA: 40e6445b59dced074c76aa2b62d450aa36bb38da
OLD_LOCAL_HEAD: f0b3657e5eb2a6e4fd8cca3e932164831478c852
NEW_LOCAL_HEAD: 40e6445b59dced074c76aa2b62d450aa36bb38da (rebase still paused)
REBASed_COMMITS: (none — continue not completed)
EOL_DIRTY_CLEARED: PARTIAL (P1+P2 staged LF=e686bac; migracja still WT dirty)
CONFLICTS: none UU / no conflict markers
WIP_APPLIED: NO
WIP_VERIFIED: NO
STASH_DROPPED: NO
INDEX_CLEAN: NO (rebase in progress; P1+P2 staged)
DIFF_SCOPE_OK: N/A
DIFF_CHECK: N/A
BACKEND_TESTS: N/A (ETAP 7 not reached)
FRONTEND_TESTS: N/A (ETAP 7 not reached)
READY_TO_REPEAT_PUSH_0005: NO
VERDICT: STOP — OPTION A add P1/P2 PASS; rebase --continue blocked by unstaged EOL on unauthorized path docs/_archiwum/migracja_mac_mini.md
```

## STASH LIST (recorded)

```
stash@{0}: On production: GWO-0006-WIP-before-rebase-on-40e6445
stash@{1}: On production: gwo-0064-temp-gate-check
stash@{2}: On production: wip guardian async docs before ksef numbering deploy
```

## ETAP PRECHECK — PASS

- Rebase in progress onto `40e6445`
- HEAD = `40e6445…`
- `stash@{0}` message contains `GWO-0006-WIP-before-rebase-on-40e6445`
- `git diff --ignore-cr-at-eol --` P1 P2 = **EMPTY**

## OPTION A — ADD — PASS

```bash
git add -- app/services/contractor_service.py frontend-react/src/api/contractors.js
```

| Check | Wynik |
|---|---|
| `git diff --cached --ignore-cr-at-eol --` P1 P2 | **EMPTY** (EOL-only vs HEAD) |
| `git diff --cached --stat --` P1 P2 | full-file EOL rewrite shown |
| staged blob `contractor_service.py` | `86c8e8771ed96dd5376a537b8c376a98686b0206` = e686bac |
| staged blob `contractors.js` | `6b10620a313abdff4b7f05410f682a99be0685df` = e686bac |
| BLOB_MATCH | **YES** |

## OPTION A — CONTINUE — STOP

```bash
GIT_EDITOR=true git -c core.editor=true rebase --continue
```

Git printed:

```
You must edit all merge conflicts and then
mark them as resolved using git add
```

**Root cause (techniczny):** to **nie** jest konflikt merge. W Git 2.54 `builtin/rebase.c` (`ACTION_CONTINUE`) wychodzi z tym komunikatem gdy `has_unstaged_changes()` jest prawdziwe — czyli przy **jakichkolwiek** unstaged zmianach WT vs index.

Jedyny plik unstaged:

- `docs/_archiwum/migracja_mac_mini.md` — mechanizm EOL (CRLF blob vs `eol=lf`); `git diff --ignore-cr-at-eol` pusty; `git diff --stat` pokazuje pełny rewrite 609/609.

Zgodnie z bramką GWO-0006B:

- auto-add dozwolone **tylko** dla P1/P2
- jeśli EOL dirty na migracja / CSS / innym → **STOP**, nie auto-add

Dlatego **nie** dodano `migracja_mac_mini.md`. Rebase pozostaje paused. Brak abort / push / deploy / stash pop / reset --hard / checkout.

## Stan pozostawiony

- Rebase **paused** / editing; onto `40e6445`
- **Staged (gotowe do continue po odblokowaniu WT):** P1 + P2 (LF = e686bac blobs)
- **Unstaged EOL dirty (blokuje continue):** `docs/_archiwum/migracja_mac_mini.md`
- Untracked reports: `0006-REBASE-…md`, `0006B-RESUME-…md`
- Todo (nadal): e686bac, c87452f, 23c72b2, f0b3657
- `stash@{0}` nietknięty
- ETAP 5–8 **nie** uruchomione

## Decyzje potrzebne do odblokowania (poza zakresem auto)

Aby `rebase --continue` przeszedł, WT musi być bez unstaged changes. Opcje wymagają jawnej autoryzacji użytkownika:

1. **`git add -- docs/_archiwum/migracja_mac_mini.md`** (EOL-only, ten sam mechanizm co P1/P2) — potem `GIT_EDITOR=true git rebase --continue` (może trzeba powtórzyć dla kolejnych picków / CSS)
2. Inna jawna procedura na migrację (nie `reset --hard` / nie unauthorized checkout bez decyzji)

Po udanym rebase: ETAP 5–8 (log/diff, stash apply, pytest + node tests, stash drop).

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

