from __future__ import annotations

from ifg_guardian.config import TARGET_BRANCH
from ifg_guardian.core.git import git, parse_porcelain_line, porcelain_is_dirty
from ifg_guardian.core.repo_audit.extensions import RepoAuditExtension
from ifg_guardian.core.repo_audit.models import RepoAuditState
from ifg_guardian.core.risk import RiskLevel, max_risk
from ifg_guardian.modules.frontend import check_frontend_worktree_requires_build


def get_audit_state(ctx) -> RepoAuditState:
    audit = ctx.data.get("audit")
    if not isinstance(audit, RepoAuditState):
        raise RuntimeError("repo audit state not initialized")
    return audit


def get_extensions(ctx) -> list[RepoAuditExtension]:
    return list(ctx.data.get("repo_extensions", []))


def collect_git_status(audit: RepoAuditState) -> None:
    audit.branch = git("branch", "--show-current")
    audit.head = git("rev-parse", "HEAD")
    audit.porcelain = git("status", "--porcelain")
    audit.dirty = porcelain_is_dirty(audit.porcelain)

    try:
        counts = git("rev-list", "--left-right", "--count", f"HEAD...origin/{TARGET_BRANCH}")
        ahead_s, behind_s = counts.split("\t", 1)
        audit.ahead = int(ahead_s)
        audit.behind = int(behind_s)
    except RuntimeError:
        audit.ahead = 0
        audit.behind = 0


def parse_changed_paths(porcelain: str) -> list[tuple[str, str]]:
    paths: list[tuple[str, str]] = []
    for line in porcelain.splitlines():
        if not line.strip():
            continue
        status, path = parse_porcelain_line(line)
        paths.append((status.strip(), path))
    return paths


def aggregate_risk(audit: RepoAuditState, *, extensions: list[RepoAuditExtension] | None = None) -> None:
    risks = [f.risk for f in audit.files]
    if audit.branch != TARGET_BRANCH:
        risks.append(RiskLevel.HIGH)
    if audit.behind > 0:
        risks.append(RiskLevel.MEDIUM)
    if audit.ahead > 0:
        risks.append(RiskLevel.MEDIUM)

    worktree_ok, _ = check_frontend_worktree_requires_build()
    if not worktree_ok:
        risks.append(RiskLevel.HIGH)

    for ext in extensions or []:
        risks.extend(ext.extra_risks(audit.files))

    audit.overall_risk = max_risk(RiskLevel.LOW, *risks) if risks else RiskLevel.LOW
