from __future__ import annotations

from ifg_guardian.config import FRONTEND_SRC_PREFIX, IGNORE_PATTERNS
from ifg_guardian.core.line_endings import (
    Confidence,
    LineEndingCategory,
    analyze_line_endings,
)
from ifg_guardian.core.repo_audit.extensions import RepoAuditExtension
from ifg_guardian.core.repo_audit.models import ClassifiedFile
from ifg_guardian.core.risk import FileCategory, RiskLevel
from ifg_guardian.core.workflow.stage import BuildReason


def should_ignore(path: str) -> bool:
    normalized = path.replace("\\", "/")
    for pattern in IGNORE_PATTERNS:
        if pattern.endswith("/"):
            if normalized.startswith(pattern) or f"/{pattern}" in f"/{normalized}/":
                return True
        elif normalized == pattern or normalized.endswith(f"/{pattern}"):
            return True
    return False


def classify_line_endings(path: str) -> tuple[ClassifiedFile | None, list[BuildReason]]:
    analysis = analyze_line_endings(path)
    reasons: list[BuildReason] = []

    if analysis.category == LineEndingCategory.NOT_LINE_ENDING:
        return None, reasons

    decision = analysis.category.value.lower()
    reasons.append(
        BuildReason(
            decision=decision,
            because=[path],
            confidence=analysis.confidence.value,
            source_stage="line_ending_analysis",
        )
    )

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
        ), reasons

    return ClassifiedFile(
        path=path,
        status="M",
        category=FileCategory.UNKNOWN_LINE_ENDINGS,
        risk=RiskLevel.MEDIUM,
        note=analysis.note,
        confidence=analysis.confidence,
        verification=analysis.verification,
        restore_recommended=False,
    ), reasons


def classify_modified_path(path: str, *, extensions: list[RepoAuditExtension] | None = None) -> ClassifiedFile:
    """Classify a modified path without line-ending analysis (separate stage)."""
    for ext in extensions or []:
        override = ext.classify_file(path, "M")
        if override is not None:
            return override

    if should_ignore(path):
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

    return classify_modified_base(path, extensions=extensions)


def classify_modified(path: str, *, extensions: list[RepoAuditExtension] | None = None) -> ClassifiedFile:
    base = classify_modified_path(path, extensions=extensions)
    if base.category in (FileCategory.IGNORE, FileCategory.DEPLOY_BLOCKER):
        return base

    line_ending, _ = classify_line_endings(path)
    if line_ending is not None:
        return line_ending

    return base


def classify_modified_base(path: str, *, extensions: list[RepoAuditExtension] | None = None) -> ClassifiedFile:
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


def classify_untracked(path: str, *, extensions: list[RepoAuditExtension] | None = None) -> ClassifiedFile:
    for ext in extensions or []:
        override = ext.classify_file(path, "??")
        if override is not None:
            return override

    if should_ignore(path):
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
