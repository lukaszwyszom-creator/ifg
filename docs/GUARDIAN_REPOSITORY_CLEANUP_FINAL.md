# Guardian Repository Cleanup — final operational hardening

**Date:** 2026-05-22  
**Profile:** IFG Repository Cleanup Advisor  
**Stage:** Guardian Development closed → Repository Cleanup ready

---

## 1. Phase 0 safety (100% git-status safe)

Phase 0 removes **only** local, untracked artifacts:

| Category | Examples |
|----------|----------|
| Python cache | `__pycache__/`, `*.pyc` (outside `__pycache__`) |
| Test cache | `.pytest_cache` |
| OS junk | `.DS_Store` |
| Local logs / tmp | `.logs`, `tmp` (when untracked) |
| Untracked cache | any discovered path not in `git ls-files` |

### Removed from Phase 0 discovery

- `frontend-react/dist` and `frontend-react/node_modules`
- `ksef_backend.egg-info`, `doc` (no longer auto-deleted at repo root)

### Git-tracked path filter

`discover_phase0_artifacts()` calls `is_git_tracked_path()` for every candidate:

- `git ls-files --error-unmatch <path>` — exact file
- `git ls-files <path>/` — any tracked file under a directory

Tracked paths are **never** included in the Phase 0 plan.

### Executor safety net

`executor._local_remove()` raises `CleanupExecutionError` if a git-tracked path reaches execution — defence in depth; Phase 0 should never plan such ops.

### Path normalization fix

`normalize_rel_path()` no longer strips the leading dot from hidden dirs (e.g. `.pytest_cache` → `pytest_cache`). This was a latent bug exposed by the tracked-path filter.

**Never:** `git rm`, deletion of git-tracked files.

---

## 2. Git status protection (Phase 1+ guard)

Before Phase 1, 2, or 3 (dry-run or live):

```
Repository contains uncommitted changes.
Commit or stash changes before repository cleanup.
```

Exit code: **1**

Implementation: `git_guard.has_uncommitted_changes()` via `git status --porcelain` (backups dir ignored per IFG infra policy).

### Exceptions

| Scenario | Behaviour |
|----------|-----------|
| `--phase 0` | Always allowed, even on dirty worktree |
| All phases (`--phase` omitted) on dirty repo | Phase 0 only; phases 1–3 skipped with notice |
| Clean worktree | All requested phases run normally |

---

## 3. Files changed

| File | Change |
|------|--------|
| `repo_cleanup/boundaries.py` | Narrow Phase 0 allowlist; git-tracked filter; `*.pyc` discovery; fix `normalize_rel_path` |
| `repo_cleanup/git_guard.py` | **New** — dirty worktree check, tracked-path detection |
| `repo_cleanup/runner.py` | Phase 1+ guard; phase-0-only fallback when dirty |
| `repo_cleanup/executor.py` | Refuse `local_remove` on tracked paths |
| `tests/guardian_platform/test_repo_cleanup_advisor.py` | 5 regression tests |

No Guardian Platform core or Repo Graph changes.

---

## 4. New tests (5)

| Test | Asserts |
|------|---------|
| `TestPhase0Safety::test_phase0_excludes_git_tracked_dist` | `frontend-react/dist` not in Phase 0 plan when tracked |
| `TestPhase0Safety::test_phase0_live_does_not_change_git_status` | Live Phase 0 leaves `git status --porcelain` unchanged; dist preserved |
| `TestCleanWorktreeGuard::test_phase1_refused_when_dirty` | Phase 1 dry-run exits 1 with guard message |
| `TestCleanWorktreeGuard::test_phase0_allowed_when_dirty` | Phase 0 dry-run exits 0 on dirty repo |
| `TestCleanWorktreeGuard::test_all_phases_dirty_runs_phase0_only` | Full dry-run on dirty repo skips phases 1–3 |

Updated: `test_phase0_only_local` — asserts `dist` / `node_modules` absent from Phase 0 ops.

---

## 5. Test results

```text
pytest tests/guardian_platform/ — 301 passed
```

Baseline before this task: 296 passed (+5 new tests).

---

## 6. Acceptance checklist

| Criterion | Status |
|-----------|--------|
| Phase 0 does not change `git status` | ✔ |
| `frontend-react/dist` not removed by Phase 0 | ✔ |
| Phase 1+ refused on dirty repo | ✔ |
| Guardian Platform needs no further architectural changes | ✔ |

---

## 7. Recommended IFG cleanup workflow

```bash
# 1. Safe local cache cleanup (always OK)
python3 -m scripts.guardian_platform ifg repo cleanup --phase 0 --yes

# 2. Commit or stash all changes
git status   # must be clean

# 3. Plan archive/review phases
python3 -m scripts.guardian_platform ifg repo cleanup --dry-run --phase 1
python3 -m scripts.guardian_platform ifg repo cleanup --yes --phase 1
```

Guardian Development stage is **closed**. IFG Repository Cleanup may proceed operationally.
