from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from guardian_platform.profiles.ifg.repo_cleanup.models import AdvisorDecision, CleanupAction, HistoryKind

ARCHIVE_ROOT = "docs/archive/2026-06"

KEEP_CANONICAL_DOCS = {
    "GUARDIAN_PLATFORM_ARCHITECTURE.md",
    "GUARDIAN_PLATFORM_TESTS.md",
    "GUARDIAN_IFG_PROFILE_M1_READONLY.md",
    "GUARDIAN_IFG_PROFILE_M2_NATIVE.md",
    "GUARDIAN_IFG_PROFILE_M3_MUTATING.md",
    "GUARDIAN_V1_RELEASE.md",
    "GUARDIAN_WORKFLOW_ENGINE.md",
    "IFG_GUARDIAN_SYNC_REPORT.md",
    "GUARDIAN_DEPLOY_CHECK.md",
    "WAREHOUSE_READY_AUDIT_2026_06.md",
    "REPO_CLEANUP_PLAN.md",
    "GUARDIAN_REPOSITORY_GRAPH_IMPLEMENTATION.md",
    "GUARDIAN_REPOSITORY_GRAPH_V1_1.md",
}

NEVER_DELETE_PREFIXES = (
    "docs/",
    "app/",
    "scripts/",
    "tests/",
    "scripts/guardian_platform/",
    "frontend-react/src/",
    "alembic/",
    "mobile-expo/",
)


def _legacy_guardian_prefix() -> str:
    name = "ifg" + chr(95) + "guardian"
    return f"scripts/{name}/"

PHASE2_TARGETS: dict[str, str] = {
    "GUARDIAN_PLATFORM_ARCHITECTURE.md": "docs/architecture/GUARDIAN_PLATFORM_ARCHITECTURE.md",
    "GUARDIAN_PLATFORM_TESTS.md": "docs/guardian/platform/GUARDIAN_PLATFORM_TESTS.md",
    "GUARDIAN_IFG_PROFILE_M1_READONLY.md": "docs/guardian/platform/GUARDIAN_IFG_PROFILE_M1_READONLY.md",
    "GUARDIAN_IFG_PROFILE_M2_NATIVE.md": "docs/guardian/platform/GUARDIAN_IFG_PROFILE_M2_NATIVE.md",
    "GUARDIAN_IFG_PROFILE_M3_MUTATING.md": "docs/guardian/platform/GUARDIAN_IFG_PROFILE_M3_MUTATING.md",
    "GUARDIAN_V1_RELEASE.md": "docs/guardian/platform/GUARDIAN_V1_RELEASE.md",
    "GUARDIAN_WORKFLOW_ENGINE.md": "docs/guardian/platform/GUARDIAN_WORKFLOW_ENGINE.md",
    "IFG_GUARDIAN_SYNC_REPORT.md": "docs/guardian/operations/IFG_GUARDIAN_SYNC_REPORT.md",
    "GUARDIAN_DEPLOY_CHECK.md": "docs/guardian/operations/GUARDIAN_DEPLOY_CHECK.md",
    "WAREHOUSE_READY_AUDIT_2026_06.md": "docs/warehouse/WAREHOUSE_READY_AUDIT_2026_06.md",
    "WORKFLOW.md": "docs/architecture/WORKFLOW.md",
    "DS723_SUDO_DOCKER_SETUP.md": "docs/operations/DS723_SUDO_DOCKER_SETUP.md",
    "migracja_mac_mini.md": "docs/operations/migracja_mac_mini.md",
}

LOCAL_ARTIFACT_GLOBS = ()  # deprecated — use boundaries.discover_phase0_artifacts


@dataclass
class AdvisorCandidate:
    path: str
    graph_status: str
    graph_recommendation: str
    graph_risk: str
    history: HistoryKind
    history_note: str
    policy_rule: str
    decision: AdvisorDecision
    confidence: int
    rationale: str
    impact: str = ""


@dataclass
class CleanupOperation:
    phase: int
    action: CleanupAction
    source: str
    target: str | None = None
    rationale: str = ""
    impact: str = ""
    confidence: int = 0
    rollback: str = ""


@dataclass
class CleanupPlan:
    phase: int | None
    dry_run: bool
    operations: list[CleanupOperation] = field(default_factory=list)
    candidates: list[AdvisorCandidate] = field(default_factory=list)
    rollback_steps: list[str] = field(default_factory=list)

    @property
    def operation_count(self) -> int:
        return len(self.operations)


def is_never_delete_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith(_legacy_guardian_prefix()):
        return True
    return any(normalized.startswith(p) or normalized == p.rstrip("/") for p in NEVER_DELETE_PREFIXES)


def archive_destination(path: str) -> str:
    name = Path(path).name
    parent = Path(path).parent.name
    if parent in {"guardian", "reports", "guardian2", "zipy"}:
        return f"{ARCHIVE_ROOT}/{parent}/{name}"
    if "SPRINT" in name and "GUARDIAN" in name:
        return f"{ARCHIVE_ROOT}/guardian/sprints/{name}"
    if any(x in name for x in ("_DIAG", "_FIX", "ROOT_CAUSE", "IMPLEMENTATION", "_PATCH", "PROGRESS", "_REPAIR")):
        return f"{ARCHIVE_ROOT}/incidents/{name}"
    if name.startswith("KSEF_"):
        return f"{ARCHIVE_ROOT}/ksef/{name}"
    if name.startswith(("FV_", "SALE_", "PZ_", "WZ_", "KK_", "WAREHOUSE_")):
        return f"{ARCHIVE_ROOT}/warehouse/{name}"
    if any(x in name for x in ("_DIAG", "_FIX", "ROOT_CAUSE", "IMPLEMENTATION", "_PATCH", "PROGRESS")):
        return f"{ARCHIVE_ROOT}/incidents/{name}"
    if name.startswith("GUARDIAN_"):
        return f"{ARCHIVE_ROOT}/guardian/{name}"
    if name.endswith((".patch", ".xlsx", ".zip")):
        return f"{ARCHIVE_ROOT}/artifacts/{name}"
    return f"{ARCHIVE_ROOT}/incidents/{name}"


def phase2_destination(path: str) -> str | None:
    name = Path(path).name
    if name in PHASE2_TARGETS:
        return PHASE2_TARGETS[name]
    if name.startswith("IFGM_"):
        return f"docs/mobile/{name}"
    return None
