from __future__ import annotations

import subprocess
from pathlib import Path

from ifg_guardian.config import DEFAULT_REMOTE_PATH, ROOT, TARGET_BRANCH
from ifg_guardian.core.git import git, parse_porcelain_line, porcelain_is_dirty, resolve_ds723_host, short_sha
from ifg_guardian.core.repo_audit.models import ClassifiedFile, RepoAuditState
from ifg_guardian.core.risk import FileCategory
from ifg_guardian.core.ssh import remote_git
from ifg_guardian.modules.repo_audit import collect_audit, run_repo_audit

RepoAuditResult = RepoAuditState

__all__ = [
    "ClassifiedFile",
    "RepoAuditResult",
    "RepoAuditState",
    "collect_audit",
    "run_repo_audit",
    "run_repo_clean_dry_run",
    "run_repo_status",
    "run_repo_sync",
]


def run_repo_status(*, do_fetch: bool = False) -> int:
    return run_repo_sync(do_fetch=do_fetch, remote=None)


def run_repo_sync(
    *,
    do_fetch: bool = False,
    remote: str | None = None,
    remote_host: str | None = None,
    remote_path: str = DEFAULT_REMOTE_PATH,
) -> int:
    host = resolve_ds723_host(remote_host)
    print("IFG Guardian Repo Sync")
    print("=" * 40)

    has_error = False
    has_warning = False
    notes: list[str] = []

    if do_fetch:
        try:
            git("fetch", "origin", TARGET_BRANCH, "--quiet")
        except RuntimeError as exc:
            print(f"\n❌ git fetch origin {TARGET_BRANCH} failed: {exc}")
            print("\nStatus: ERROR")
            return 1
    else:
        notes.append(f"⚠️  origin/{TARGET_BRANCH} may be stale. Run: git fetch origin {TARGET_BRANCH}")

    try:
        branch = git("branch", "--show-current")
        local_head = git("rev-parse", "HEAD")
        origin_head = git("rev-parse", f"origin/{TARGET_BRANCH}")
        porcelain = git("status", "--porcelain")
        counts = git("rev-list", "--left-right", "--count", f"HEAD...origin/{TARGET_BRANCH}")
    except RuntimeError as exc:
        print(f"\n❌ Nie udało się odczytać stanu repo: {exc}")
        print("\nStatus: ERROR")
        return 1

    ahead_s, behind_s = counts.split("\t", 1)
    ahead = int(ahead_s)
    behind = int(behind_s)
    dirty = porcelain_is_dirty(porcelain)
    on_production = branch == TARGET_BRANCH
    local_ok = on_production and not dirty and ahead == 0 and behind == 0

    print(f"\nLocal branch: {branch}")
    print(f"Local HEAD: {local_head}")
    print(f"Origin {TARGET_BRANCH}: {origin_head}")
    print(f"Local ahead: {ahead}")
    print(f"Local behind: {behind}")
    print(f"Local working tree: {'dirty' if dirty else 'clean'}")
    print()

    if not on_production:
        has_error = True
        notes.append(f"❌ local not on {TARGET_BRANCH} branch")
    else:
        notes.append(f"✅ local on {TARGET_BRANCH} branch")

    if dirty:
        has_warning = True
        notes.append("⚠️  local working tree dirty")
    else:
        notes.append("✅ local working tree clean")

    if ahead > 0:
        has_warning = True
        notes.append(f"⚠️  local ahead of origin/{TARGET_BRANCH} ({ahead} commit(s))")
    elif behind > 0:
        has_warning = True
        notes.append(f"⚠️  local behind origin/{TARGET_BRANCH} ({behind} commit(s))")
    elif local_ok:
        notes.append(f"✅ local clean + synced with origin/{TARGET_BRANCH}")

    if not do_fetch:
        has_warning = True

    remote_ok = True
    if remote == "ds723":
        print(f"Remote DS723 ({host}:{remote_path})")
        print("-" * 40)
        try:
            remote_branch = remote_git(host, remote_path, "branch --show-current")
            remote_head = remote_git(host, remote_path, "rev-parse HEAD")
            remote_porcelain = remote_git(host, remote_path, "status --porcelain")
        except RuntimeError as exc:
            has_error = True
            notes.append(f"❌ SSH/git failed on DS723+: {exc}")
            remote_ok = False
        else:
            remote_dirty = porcelain_is_dirty(remote_porcelain)
            remote_on_production = remote_branch == TARGET_BRANCH

            print(f"Remote DS723 branch: {remote_branch}")
            print(f"Remote DS723 HEAD: {remote_head}")
            print(f"Remote DS723 working tree: {'dirty' if remote_dirty else 'clean'}")
            print()

            if not remote_on_production:
                has_error = True
                notes.append(f"❌ remote not on {TARGET_BRANCH} branch")
                remote_ok = False
            else:
                notes.append(f"✅ remote on {TARGET_BRANCH} branch")

            if remote_dirty:
                has_warning = True
                notes.append("⚠️  remote working tree dirty")
                remote_ok = False
            else:
                notes.append("✅ remote working tree clean")

            if remote_head == origin_head:
                notes.append("✅ remote HEAD matches origin/production")
            else:
                try:
                    rb_counts = git(
                        "rev-list",
                        "--left-right",
                        "--count",
                        f"{origin_head}...{remote_head}",
                    )
                    r_behind_s, r_ahead_s = rb_counts.split("\t", 1)
                    r_behind = int(r_behind_s)
                    r_ahead = int(r_ahead_s)
                except RuntimeError:
                    r_behind = r_ahead = -1

                if r_behind > 0:
                    has_warning = True
                    remote_ok = False
                    notes.append(f"⚠️  DS723+ behind origin/{TARGET_BRANCH} ({r_behind} commit(s))")
                if r_ahead > 0:
                    has_warning = True
                    remote_ok = False
                    notes.append(f"⚠️  DS723+ ahead of origin/{TARGET_BRANCH} ({r_ahead} commit(s))")
                if r_behind == 0 and r_ahead == 0 and remote_head != origin_head:
                    has_warning = True
                    remote_ok = False
                    notes.append("⚠️  remote HEAD differs from origin/production")

            print("Sync summary:")
            print(f"  Mac mini : {short_sha(local_head)}")
            print(f"  GitHub   : {short_sha(origin_head)}")
            print(f"  DS723+   : {short_sha(remote_head)}")
            if remote_head == origin_head:
                print("  ✅ DS723+ matches GitHub (origin/production)")
            elif remote_ok is False:
                print("  ⚠️  DS723+ out of sync with GitHub (origin/production)")
            print()

    for note in notes:
        print(note)

    print("\n" + "=" * 40)
    if has_error:
        print("Status: ERROR")
        return 1
    if has_warning:
        print("Status: WARNING")
        return 1
    if local_ok and (remote != "ds723" or remote_ok):
        print("Status: OK")
        return 0

    print("Status: WARNING")
    return 1


def run_repo_clean_dry_run() -> int:
    """Read-only preview of housekeeping actions — never mutates repo."""
    print("IFG Guardian — Repo Clean (dry-run ONLY)")
    print("=" * 40)
    print("Guardian NIE wykonuje git restore / clean / reset / commit / push / rm.\n")

    try:
        audit = collect_audit(do_fetch=False)
    except RuntimeError as exc:
        print(f"\n❌ Audit failed: {exc}")
        return 1

    crlf = [f for f in audit.files if f.category == FileCategory.CRLF_ONLY and f.restore_recommended]
    unknown = [f for f in audit.files if f.category == FileCategory.UNKNOWN_LINE_ENDINGS]
    ignore = [f for f in audit.files if f.category == FileCategory.IGNORE]
    delete_review = [f for f in audit.files if f.category == FileCategory.DELETE_REVIEW]

    if crlf:
        print(f"CRLF-only ({len(crlf)}) — restore zweryfikowany (ręcznie):")
        for f in crlf:
            print(f"  git restore -- {f.path}  # Confidence: {f.confidence.value if f.confidence else '?'}")
        print()

    if unknown:
        print(f"Unknown line endings ({len(unknown)}) — NIE restore bez review:")
        for f in unknown:
            print(f"  {f.path} — {f.note}")
        print()

    if ignore:
        print(f"Ignore candidates ({len(ignore)}):")
        for f in ignore:
            print(f"  [{f.status}] {f.path} — {f.note}")
        print()

    if delete_review:
        print(f"Human review ({len(delete_review)}):")
        for f in delete_review:
            print(f"  ?? {f.path} — {f.note}")
        print()

    if not crlf and not unknown and not ignore and not delete_review:
        print("Brak plików wymagających housekeeping.")

    print("\n" + "=" * 40)
    print("Status: DRY-RUN (no changes made)")
    return 0
