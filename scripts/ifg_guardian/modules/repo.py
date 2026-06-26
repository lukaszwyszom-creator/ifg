from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ifg_guardian.config import DEFAULT_REMOTE_PATH, FRONTEND_SRC_PREFIX, IGNORE_PATTERNS, ROOT, TARGET_BRANCH
from ifg_guardian.core.git import git, parse_porcelain_line, porcelain_is_dirty, resolve_ds723_host, short_sha
from ifg_guardian.core.line_endings import Confidence, LineEndingCategory, analyze_line_endings
from ifg_guardian.core.risk import FileCategory, RiskLevel, max_risk
from ifg_guardian.core.ssh import remote_git
from ifg_guardian.modules.frontend import check_frontend_worktree_requires_build
from ifg_guardian.reporting import default_report_path, write_report


@dataclass
class ClassifiedFile:
    path: str
    status: str
    category: FileCategory
    risk: RiskLevel
    note: str = ""
    confidence: Confidence | None = None
    verification: list[str] = field(default_factory=list)
    restore_recommended: bool = False


@dataclass
class RepoAuditResult:
    branch: str = ""
    head: str = ""
    dirty: bool = False
    ahead: int = 0
    behind: int = 0
    files: list[ClassifiedFile] = field(default_factory=list)
    overall_risk: RiskLevel = RiskLevel.LOW
    recommended_actions: list[str] = field(default_factory=list)
    gitattributes_exists: bool = False
    gitignore_exists: bool = False


def _should_ignore(path: str) -> bool:
    normalized = path.replace("\\", "/")
    for pattern in IGNORE_PATTERNS:
        if pattern.endswith("/"):
            if normalized.startswith(pattern) or f"/{pattern}" in f"/{normalized}/":
                return True
        elif normalized == pattern or normalized.endswith(f"/{pattern}"):
            return True
    return False


def _classify_line_endings(path: str) -> ClassifiedFile | None:
    """Return classification when line-ending analysis applies; else None."""
    analysis = analyze_line_endings(path)

    if analysis.category == LineEndingCategory.NOT_LINE_ENDING:
        return None

    if analysis.category == LineEndingCategory.CRLF_ONLY:
        return ClassifiedFile(
            path=path,
            status="M",
            category=FileCategory.CRLF_ONLY,
            risk=RiskLevel.MEDIUM,
            note=analysis.note,
            confidence=analysis.confidence,
            verification=analysis.verification,
            restore_recommended=analysis.restore_would_help,
        )

    return ClassifiedFile(
        path=path,
        status="M",
        category=FileCategory.UNKNOWN_LINE_ENDINGS,
        risk=RiskLevel.MEDIUM,
        note=analysis.note,
        confidence=analysis.confidence,
        verification=analysis.verification,
        restore_recommended=False,
    )


def _classify_modified(path: str) -> ClassifiedFile:
    if _should_ignore(path):
        return ClassifiedFile(
            path=path,
            status="M",
            category=FileCategory.IGNORE,
            risk=RiskLevel.MEDIUM,
            note="Śledzony plik z .gitignore — rozważ git restore lub popraw .gitignore",
        )
    if path.startswith(".env"):
        return ClassifiedFile(
            path=path,
            status="M",
            category=FileCategory.DEPLOY_BLOCKER,
            risk=RiskLevel.CRITICAL,
            note="Plik sekretów — nie commitować",
        )

    line_ending = _classify_line_endings(path)
    if line_ending is not None:
        return line_ending

    if path.startswith(f"{FRONTEND_SRC_PREFIX}/") or path.startswith("frontend-react/"):
        return ClassifiedFile(
            path=path,
            status="M",
            category=FileCategory.SUBSTANTIVE,
            risk=RiskLevel.HIGH,
            note="Zmiana frontend — wymaga npm run build przed deployem DS723+",
        )
    if path.startswith("app/") or path.startswith("alembic/"):
        return ClassifiedFile(
            path=path,
            status="M",
            category=FileCategory.SUBSTANTIVE,
            risk=RiskLevel.HIGH,
            note="Zmiana backend — wymaga rebuild api/worker",
        )
    if path.startswith("docs/"):
        return ClassifiedFile(
            path=path,
            status="M",
            category=FileCategory.COMMIT,
            risk=RiskLevel.LOW,
            note="Dokumentacja — bezpieczne do commita",
        )
    return ClassifiedFile(
        path=path,
        status="M",
        category=FileCategory.SUBSTANTIVE,
        risk=RiskLevel.MEDIUM,
        note="Zmiana merytoryczna",
    )


def _classify_untracked(path: str) -> ClassifiedFile:
    if _should_ignore(path):
        return ClassifiedFile(
            path=path,
            status="??",
            category=FileCategory.IGNORE,
            risk=RiskLevel.LOW,
            note="Powinien być ignorowany — dodaj do .gitignore jeśli brak",
        )
    if path.startswith("docs/"):
        return ClassifiedFile(
            path=path,
            status="??",
            category=FileCategory.COMMIT,
            risk=RiskLevel.LOW,
            note="Raport/diag — rozważ commit lub archiwum",
        )
    if path.endswith(".test.js") or path.endswith(".test.mjs") or path.startswith("tests/"):
        return ClassifiedFile(
            path=path,
            status="??",
            category=FileCategory.COMMIT,
            risk=RiskLevel.MEDIUM,
            note="Test — commit razem z feature",
        )
    return ClassifiedFile(
        path=path,
        status="??",
        category=FileCategory.DELETE_REVIEW,
        risk=RiskLevel.MEDIUM,
        note="Nieśledzony — decyzja człowieka: commit / ignore / usuń",
    )


def collect_audit(*, do_fetch: bool = False) -> RepoAuditResult:
    result = RepoAuditResult()
    result.gitattributes_exists = (ROOT / ".gitattributes").is_file()
    result.gitignore_exists = (ROOT / ".gitignore").is_file()

    if do_fetch:
        git("fetch", "origin", TARGET_BRANCH, "--quiet")

    result.branch = git("branch", "--show-current")
    result.head = git("rev-parse", "HEAD")
    porcelain = git("status", "--porcelain")
    result.dirty = porcelain_is_dirty(porcelain)

    try:
        counts = git("rev-list", "--left-right", "--count", f"HEAD...origin/{TARGET_BRANCH}")
        ahead_s, behind_s = counts.split("\t", 1)
        result.ahead = int(ahead_s)
        result.behind = int(behind_s)
    except RuntimeError:
        pass

    for line in porcelain.splitlines():
        if not line.strip():
            continue
        status, path = parse_porcelain_line(line)
        if status.strip() == "??":
            result.files.append(_classify_untracked(path))
        elif "M" in status or "A" in status or "D" in status:
            result.files.append(_classify_modified(path))

    risks = [f.risk for f in result.files]
    if result.branch != TARGET_BRANCH:
        risks.append(RiskLevel.HIGH)
    if result.behind > 0:
        risks.append(RiskLevel.MEDIUM)
    if result.ahead > 0:
        risks.append(RiskLevel.MEDIUM)

    worktree_ok, _ = check_frontend_worktree_requires_build()
    if not worktree_ok:
        risks.append(RiskLevel.HIGH)

    result.overall_risk = max_risk(RiskLevel.LOW, *risks) if risks else RiskLevel.LOW
    result.recommended_actions = _build_recommended_actions(result)
    return result


def _build_recommended_actions(audit: RepoAuditResult) -> list[str]:
    actions: list[str] = []

    crlf_files = [
        f.path for f in audit.files
        if f.category == FileCategory.CRLF_ONLY and f.restore_recommended
    ]
    if crlf_files:
        actions.append(
            f"Oczyść szum CRLF ({len(crlf_files)} plików, restore zweryfikowany): "
            f"ręcznie `git restore -- {' '.join(crlf_files[:3])}"
            f"{'...' if len(crlf_files) > 3 else ''}` "
            f"— tylko po Twojej zgodzie (Guardian NIE wykonuje tego automatycznie)."
        )

    unknown_eol = [f.path for f in audit.files if f.category == FileCategory.UNKNOWN_LINE_ENDINGS]
    if unknown_eol:
        actions.append(
            f"Pliki z niejednoznacznymi końcami linii ({len(unknown_eol)}): "
            f"{unknown_eol[0]}{'…' if len(unknown_eol) > 1 else ''} — "
            f"nie używaj git restore bez analizy Verification w raporcie."
        )

    ignore_tracked = [f.path for f in audit.files if f.category == FileCategory.IGNORE and f.status == "M"]
    if ignore_tracked:
        actions.append(
            f"Usuń ze śledzenia pliki dist/env: {', '.join(ignore_tracked)} — "
            f"`git restore -- {' '.join(ignore_tracked[:2])}` lub popraw .gitignore."
        )

    commit_docs = [f.path for f in audit.files if f.category == FileCategory.COMMIT and f.status == "??"]
    if commit_docs:
        actions.append(
            f"Rozważ commit {len(commit_docs)} raportów docs/ (np. po review): "
            f"{commit_docs[0]}" + (f" … +{len(commit_docs)-1}" if len(commit_docs) > 1 else "")
        )

    substantive = [f for f in audit.files if f.category == FileCategory.SUBSTANTIVE]
    if substantive:
        frontend = [f.path for f in substantive if f.path.startswith(FRONTEND_SRC_PREFIX)]
        backend = [f.path for f in substantive if f.path.startswith("app/")]
        if backend:
            actions.append("Backend zmieniony — przed deployem: rebuild api/worker na DS723+.")
        if frontend:
            actions.append("Frontend src zmieniony — przed deployem: `cd frontend-react && npm run build`.")

    if audit.behind > 0:
        actions.append(f"Repo behind origin/{TARGET_BRANCH} ({audit.behind}) — `git pull origin {TARGET_BRANCH}`.")
    if audit.ahead > 0:
        actions.append(f"Repo ahead ({audit.ahead}) — `git push origin {TARGET_BRANCH}` po review.")

    if audit.branch != TARGET_BRANCH:
        actions.append(f"Przełącz na branch `{TARGET_BRANCH}` przed deployem.")

    if not audit.dirty and audit.ahead == 0 and audit.behind == 0 and audit.branch == TARGET_BRANCH:
        actions.append("Worktree czysty i zsynchronizowany — brak wymaganych działań repo.")

    if not actions:
        actions.append("Brak szczegółowych rekomendacji — uruchom `guardian deploy check`.")

    return actions


def _format_audit_report(audit: RepoAuditResult) -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# IFG Guardian — Repo Audit",
        "",
        f"**Generated:** {ts}  ",
        f"**Branch:** `{audit.branch}`  ",
        f"**HEAD:** `{short_sha(audit.head)}`  ",
        f"**Overall risk:** `{audit.overall_risk.value}`  ",
        "",
        "## Repo status",
        "",
        f"- Working tree: {'dirty' if audit.dirty else 'clean'}",
        f"- Ahead of origin/{TARGET_BRANCH}: {audit.ahead}",
        f"- Behind origin/{TARGET_BRANCH}: {audit.behind}",
        f"- `.gitignore`: {'present' if audit.gitignore_exists else 'MISSING'}",
        f"- `.gitattributes`: {'present' if audit.gitattributes_exists else 'MISSING'}",
        "",
        "## File classification",
        "",
        "| Path | Status | Category | Risk | Confidence | Note |",
        "|------|--------|----------|------|------------|------|",
    ]
    for f in sorted(audit.files, key=lambda x: (x.risk.value, x.path)):
        conf = f.confidence.value if f.confidence else "—"
        lines.append(f"| `{f.path}` | {f.status} | {f.category.value} | {f.risk.value} | {conf} | {f.note} |")

    if not audit.files:
        lines.append("| _(clean)_ | | | | | |")

    eol_files = [
        f for f in audit.files
        if f.category in (FileCategory.CRLF_ONLY, FileCategory.UNKNOWN_LINE_ENDINGS)
        and f.verification
    ]
    if eol_files:
        lines.extend(["", "## Verification", ""])
        for f in eol_files:
            lines.append(f"### `{f.path}` — {f.category.value} (Confidence: {f.confidence.value if f.confidence else '—'})")
            if f.restore_recommended:
                lines.append("- Restore recommended: **yes** (simulation: index ≠ worktree)")
            else:
                lines.append("- Restore recommended: **no**")
            for step in f.verification:
                lines.append(f"- {step}")
            lines.append("")

    lines.extend(["", "## RECOMMENDED ACTION", ""])
    for i, action in enumerate(audit.recommended_actions, 1):
        lines.append(f"{i}. {action}")
    lines.append("")
    return "\n".join(lines)


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


def run_repo_audit(*, do_fetch: bool = False, report_path: Path | None = None) -> int:
    print("IFG Guardian — Repo Audit")
    print("=" * 40)

    try:
        audit = collect_audit(do_fetch=do_fetch)
    except RuntimeError as exc:
        print(f"\n❌ Audit failed: {exc}")
        return 1

    report_md = _format_audit_report(audit)
    out_path = report_path or default_report_path("REPO_AUDIT")
    write_report(out_path, report_md)

    print(f"\nBranch: {audit.branch}")
    print(f"HEAD: {short_sha(audit.head)}")
    print(f"Overall risk: {audit.overall_risk.value}")
    print(f"Classified files: {len(audit.files)}")
    print(f"\nReport: {out_path.relative_to(ROOT)}")

    print("\n## RECOMMENDED ACTION\n")
    for i, action in enumerate(audit.recommended_actions, 1):
        print(f"{i}. {action}")

    print("\n" + "=" * 40)
    if audit.overall_risk in (RiskLevel.CRITICAL, RiskLevel.HIGH):
        print("Status: ERROR")
        return 1
    if audit.overall_risk == RiskLevel.MEDIUM or audit.dirty:
        print("Status: WARNING")
        return 1
    print("Status: OK")
    return 0


def run_repo_clean_dry_run() -> int:
    """Read-only preview of housekeeping actions — never mutates repo."""
    print("IFG Guardian — Repo Clean (dry-run ONLY)")
    print("=" * 40)
    print("Guardian NIE wykonuje git restore / clean / reset / commit / push / rm.\n")

    audit = collect_audit(do_fetch=False)

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
