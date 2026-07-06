"""Canonical read-only EOL check for tracked modified files (repo.eol_check)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from ifg_guardian.config import ROOT
from ifg_guardian.core.git import parse_porcelain_line
from ifg_guardian.core.repo_audit.service import parse_changed_paths


class EolClassification(str, Enum):
    EOL_ONLY = "EOL_ONLY"
    LOGICAL_CHANGE = "LOGICAL_CHANGE"
    UNKNOWN = "UNKNOWN"


class EolVerdict(str, Enum):
    GO = "GO"
    GO_WITH_CAUTION = "GO_WITH_CAUTION"
    NO_GO = "NO_GO"


@dataclass
class EolFileResult:
    path: str
    status: str
    classification: EolClassification
    note: str = ""
    normal_diff: bool = False
    ignore_cr_diff: bool = False

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "status": self.status,
            "classification": self.classification.value,
            "note": self.note,
            "normal_diff": self.normal_diff,
            "ignore_cr_diff": self.ignore_cr_diff,
        }


@dataclass
class EolCheckResult:
    check_id: str = "repo.eol_check"
    branch: str = ""
    head: str = ""
    files: list[EolFileResult] = field(default_factory=list)
    verdict: EolVerdict = EolVerdict.GO
    recommendation: str = ""

    @property
    def eol_only_files(self) -> list[EolFileResult]:
        return [f for f in self.files if f.classification == EolClassification.EOL_ONLY]

    @property
    def logical_change_files(self) -> list[EolFileResult]:
        return [f for f in self.files if f.classification == EolClassification.LOGICAL_CHANGE]

    @property
    def unknown_files(self) -> list[EolFileResult]:
        return [f for f in self.files if f.classification == EolClassification.UNKNOWN]

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "branch": self.branch,
            "head": self.head,
            "verdict": self.verdict.value,
            "recommendation": self.recommendation,
            "files": [f.to_dict() for f in self.files],
            "eol_only_count": len(self.eol_only_files),
            "logical_change_count": len(self.logical_change_files),
            "unknown_count": len(self.unknown_files),
        }


def is_tracked_modified_status(status: str) -> bool:
    """True when porcelain XY indicates a tracked content modification."""
    if not status or status == "??":
        return False
    if status.strip() in ("D", "D "):
        return False
    if "D" in status and "M" not in status:
        return False
    return "M" in status


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_git_bytes(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        check=False,
    )


def _normalize_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _normalized_content_matches_head(path: str, repo_root: Path) -> bool:
    """Fallback when git diff reports dirty but bytes match HEAD after LF normalization."""
    head = _run_git_bytes(repo_root, "show", f"HEAD:{path}")
    if head.returncode != 0:
        return False
    file_path = repo_root / path
    if not file_path.is_file():
        return False
    worktree = file_path.read_bytes()
    return _normalize_bytes(head.stdout) == _normalize_bytes(worktree)


def classify_from_diff_flags(normal_diff: bool, ignore_cr_diff: bool) -> tuple[EolClassification, str]:
    """Pure classification from git diff exit codes (testable without subprocess)."""
    if not normal_diff:
        return (
            EolClassification.UNKNOWN,
            "Porcelain shows modified but git diff HEAD is clean",
        )
    if not ignore_cr_diff:
        return EolClassification.EOL_ONLY, "Diff disappears with --ignore-cr-at-eol"
    return EolClassification.LOGICAL_CHANGE, "Diff remains with --ignore-cr-at-eol"


def classify_file_eol(path: str, *, root: Path | None = None) -> EolFileResult:
    """Classify a single tracked file using git diff vs git diff --ignore-cr-at-eol."""
    repo_root = root or ROOT

    normal = _run_git(repo_root, "diff", "HEAD", "--quiet", "--", path)
    ignore_cr = _run_git(repo_root, "diff", "HEAD", "--ignore-cr-at-eol", "--quiet", "--", path)

    normal_diff = normal.returncode != 0
    ignore_cr_diff = ignore_cr.returncode != 0
    classification, note = classify_from_diff_flags(normal_diff, ignore_cr_diff)

    if classification == EolClassification.LOGICAL_CHANGE and _normalized_content_matches_head(
        path, repo_root
    ):
        classification = EolClassification.EOL_ONLY
        note = "Normalized bytes match HEAD (git eol filter false positive)"

    return EolFileResult(
        path=path,
        status="",
        classification=classification,
        note=note,
        normal_diff=normal_diff,
        ignore_cr_diff=ignore_cr_diff,
    )


def compute_verdict(files: list[EolFileResult]) -> tuple[EolVerdict, str]:
    if not files:
        return (
            EolVerdict.GO,
            "No tracked modified files — safe for release/cutover from EOL perspective.",
        )

    if any(f.classification == EolClassification.LOGICAL_CHANGE for f in files):
        n = sum(1 for f in files if f.classification == EolClassification.LOGICAL_CHANGE)
        return (
            EolVerdict.NO_GO,
            f"{n} file(s) with logical diff — commit or discard before release/cutover.",
        )

    if any(f.classification == EolClassification.UNKNOWN for f in files):
        n = sum(1 for f in files if f.classification == EolClassification.UNKNOWN)
        return (
            EolVerdict.NO_GO,
            f"{n} file(s) could not be classified — manual review required before release/cutover.",
        )

    if all(f.classification == EolClassification.EOL_ONLY for f in files):
        return (
            EolVerdict.GO_WITH_CAUTION,
            "All tracked modifications are EOL-only — not full GO; normalize or restore before push "
            "(manual approval required; Guardian will not auto-normalize).",
        )

    return EolVerdict.NO_GO, "Mixed or unclassified state — manual review required."


def collect_tracked_modified_paths(porcelain: str) -> list[tuple[str, str]]:
    paths: list[tuple[str, str]] = []
    seen: set[str] = set()
    for status, path in parse_changed_paths(porcelain):
        if not is_tracked_modified_status(status):
            continue
        if path in seen:
            continue
        seen.add(path)
        paths.append((status, path))
    return paths


def run_eol_check(*, root: Path | None = None) -> EolCheckResult:
    repo_root = root or ROOT
    branch = _run_git(repo_root, "branch", "--show-current").stdout.strip()
    head = _run_git(repo_root, "rev-parse", "HEAD").stdout.strip()
    porcelain = _run_git(repo_root, "status", "--porcelain").stdout

    files: list[EolFileResult] = []
    for status, path in collect_tracked_modified_paths(porcelain):
        result = classify_file_eol(path, root=repo_root)
        result.status = status
        files.append(result)

    files.sort(key=lambda f: f.path)
    verdict, recommendation = compute_verdict(files)

    return EolCheckResult(
        branch=branch,
        head=head,
        files=files,
        verdict=verdict,
        recommendation=recommendation,
    )


def render_markdown(result: EolCheckResult) -> str:
    lines = [
        "# Guardian EOL Check (`repo.eol_check`)",
        "",
        f"**Check ID:** `{result.check_id}`",
        f"**Branch:** `{result.branch}`",
        f"**HEAD:** `{result.head}`",
        f"**Verdict:** **{result.verdict.value}**",
        "",
        "## Recommendation",
        "",
        result.recommendation,
        "",
        "## Summary",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Tracked modified files | {len(result.files)} |",
        f"| EOL-only | {len(result.eol_only_files)} |",
        f"| Logical change | {len(result.logical_change_files)} |",
        f"| Unknown | {len(result.unknown_files)} |",
        "",
    ]

    if result.eol_only_files:
        lines.extend(["## EOL-only files", ""])
        for f in result.eol_only_files:
            lines.append(f"- `{f.path}` ({f.status.strip()}) — {f.note}")
        lines.append("")

    if result.logical_change_files:
        lines.extend(["## Logical change files", ""])
        for f in result.logical_change_files:
            lines.append(f"- `{f.path}` ({f.status.strip()}) — {f.note}")
        lines.append("")

    if result.unknown_files:
        lines.extend(["## Unknown classification", ""])
        for f in result.unknown_files:
            lines.append(f"- `{f.path}` ({f.status.strip()}) — {f.note}")
        lines.append("")

    if result.files:
        lines.extend(
            [
                "## Per-file classification",
                "",
                "| Path | Status | Classification | Normal diff | Ignore-CR diff | Note |",
                "|------|--------|----------------|-------------|----------------|------|",
            ]
        )
        for f in result.files:
            lines.append(
                f"| `{f.path}` | `{f.status}` | {f.classification.value} | "
                f"{'yes' if f.normal_diff else 'no'} | {'yes' if f.ignore_cr_diff else 'no'} | {f.note} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Release / cutover gate",
            "",
            "| Verdict | Meaning |",
            "|---------|---------|",
            "| GO | No tracked modifications |",
            "| GO_WITH_CAUTION | EOL-only noise — not full GO; manual normalize/restore before push |",
            "| NO_GO | Logical diff and/or unknown files present |",
            "",
        ]
    )
    return "\n".join(lines)


def exit_code_for_verdict(verdict: EolVerdict) -> int:
    if verdict == EolVerdict.NO_GO:
        return 1
    return 0
