from __future__ import annotations

from pathlib import Path

from guardian_platform.profiles.ifg.repo_cleanup.models import AdvisorDecision, HistoryKind
from guardian_platform.profiles.ifg.repo_cleanup.policy import KEEP_CANONICAL_DOCS


def classify_history(path: str) -> tuple[HistoryKind, str]:
    normalized = path.replace("\\", "/")
    name = Path(path).name

    if normalized.startswith(("__pycache__", ".pytest_cache")) or name == ".DS_Store":
        return HistoryKind.LOCAL_ARTIFACT, "local cache or OS artifact"
    if normalized in {".logs", "tmp", "frontend-react/dist", "frontend-react/node_modules"}:
        return HistoryKind.LOCAL_ARTIFACT, "local build or temp directory"
    if "/__pycache__/" in normalized or normalized.endswith("/__pycache__"):
        return HistoryKind.LOCAL_ARTIFACT, "python bytecode cache"
    if name.endswith(".pyc"):
        return HistoryKind.LOCAL_ARTIFACT, "compiled python"

    if not normalized.startswith("docs/") and not name.startswith(("README", "CHANGELOG", "LICENSE", "CONTRIBUTING")):
        if normalized.startswith(("app/", "scripts/", "tests/", "alembic/")):
            return HistoryKind.UNKNOWN, "production code path"

    if name in KEEP_CANONICAL_DOCS:
        return HistoryKind.CANONICAL, "canonical IFG / Guardian documentation"

    if "SPRINT" in name and "GUARDIAN" in name:
        return HistoryKind.SPRINT_REPORT, "Guardian sprint implementation report"

    if any(x in name for x in ("_DIAG", "_FIX", "ROOT_CAUSE", "_PATCH", "PROGRESS", "_REPAIR")):
        return HistoryKind.CLOSED_INCIDENT, "closed incident / fix documentation"

    if normalized.startswith("docs/guardian/") or normalized.startswith("docs/reports/"):
        return HistoryKind.RUNTIME_REPORT, "Guardian runtime report"

    if name in {"GUARDIAN2_DEPLOY.md", "GUARDIAN2_RECOVERY_DS723.md", "DS723_SUDO_DOCKER_SETUP.md", "migracja_mac_mini.md"}:
        return HistoryKind.OPERATIONS, "operations runbook"

    if normalized.startswith("docs/"):
        return HistoryKind.UNKNOWN, "documentation without explicit incident marker"

    return HistoryKind.UNKNOWN, "unspecified"
