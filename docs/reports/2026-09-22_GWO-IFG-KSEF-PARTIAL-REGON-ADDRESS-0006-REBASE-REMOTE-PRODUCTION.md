# GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0006-REBASE-REMOTE-PRODUCTION

Data: 2026-09-22  
Cel: rebase 4 lokalnych commitów KSeF/EOL na `origin/production` (`40e6445`) — **bez push / bez deploy**.

## STATUS

```
STATUS: STOP_CONFLICT
REMOTE_BASE_SHA: 40e6445b59dced074c76aa2b62d450aa36bb38da
OLD_LOCAL_HEAD: f0b3657e5eb2a6e4fd8cca3e932164831478c852
NEW_LOCAL_HEAD: (rebase paused; HEAD=40e6445 onto only)
REBASed_COMMITS: (none applied)
CONFLICTS: NOT UU — blocked pick e686bac by "local changes would be overwritten" (EOL)
WIP_STASHED: YES
WIP_RESTORED: NO
UNRELATED_WIP_PRESERVED: YES (in stash)
INDEX_CLEAN: N/A (rebase in progress)
DIFF_SCOPE_OK: N/A
DIFF_CHECK: N/A
BACKEND_TESTS: N/A
FRONTEND_TESTS: N/A
READY_TO_REPEAT_PUSH_0005: NO
VERDICT: STOP_REBASE_EOL_DIRTY_BLOCKER
```

## ETAP 1 — PREFLIGHT (PASS)

- `origin/production` = `40e6445…` (potwierdzone po fetch)
- Lokalny HEAD przed: `f0b3657…`
- Index pusty
- ahead 4, behind 1

## ETAP 2 — WIP

Lista WIP zapisana; stash:

```
stash@{0}: On production: GWO-0006-WIP-before-rebase-on-40e6445
```

Unrelated WIP **nie** przywrócony (rebase w toku).

## ETAP 3 — REBASE STOP

```
interactive rebase in progress; onto 40e6445
REBASE_HEAD / pick: e686bac — chore(ifg): normalize contractor address files to LF
HEAD: 40e6445
```

**Brak markerów `UU` / unmerged.**  
Git: *local changes would be overwritten* dla:

| Plik | Wariant „obecny” (HEAD/`40e6445` + WT) | Wariant „incoming” (`e686bac`) |
|---|---|---|
| `app/services/contractor_service.py` | treść logiczna bez LF-norm; blob **CRLF** (`0ba674a…`, 11907 B, 288 CRLF) | ta sama treść logiki; blob **LF** (`86c8e877…`, 11619 B) |
| `frontend-react/src/api/contractors.js` | treść logiczna; blob **CRLF** (`523da5da…`, 342 B, 12 CRLF) | ta sama treść; blob **LF** (`6b10620a…`, 330 B) |

`git diff --ignore-cr-at-eol HEAD -- <path>` = **EMPTY** (tylko EOL).  
Atrybuty: `text` + `eol=lf`.

**Znaczenie:** pierwszy rebased commit to czysta renormalizacja EOL na bazie, która na `40e6445` nadal ma CRLF w tych plikach. Worktree wygląda na „dirty” przez filtr CRLF↔LF, więc checkout/pick LF blobów jest blokowany — **to nie jest konflikt treści biznesowej**.

Nie rozwiązano. Nie `--continue`. Nie `--abort` (stan celowo paused per GWO).

Todo pozostałe: `e686bac` (ponownie), `c87452f`, `23c72b2`, `f0b3657`.

## Odzyskanie (dla decyzji — nie wykonane)

Opcje po decyzji ChatGPT/użytkownika:

1. Wyczyścić dirty EOL na 2 plikach (`git checkout --` / restore do HEAD) → `git rebase --continue`  
2. `git rebase --abort` → `git stash pop` (stash@{0}) → ponów strategię  
3. Nie zgadywać ours/theirs — tu nie ma UU.

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

1. Abort rebase + restore stash, czy continue po oczyszczeniu dirty EOL na 2 plikach?
2. Czy przy continue dozwolone jest `git checkout HEAD --` tych 2 ścieżek (EOL-only dirty), bez zmiany logiki?
