from __future__ import annotations

import hashlib
from pathlib import Path

from ifg_guardian.config import COMPOSE_FILE, REQUIRED_COMPOSE_SERVICES, ROOT
from ifg_guardian.core.git import git, short_sha
from ifg_guardian.plugins.ifg.doctor.models import DoctorState
from ifg_guardian.plugins.ifg.release_plan.models import BuildDecision, PlannedArtifact, ReleasePlanState


def _frontend_bundle_id() -> str:
    dist_assets = ROOT / "frontend-react" / "dist" / "assets"
    if not dist_assets.is_dir():
        return "missing"
    js_files = sorted(dist_assets.glob("*.js"))
    if not js_files:
        return "empty"
    digest = hashlib.sha256()
    for js_file in js_files:
        digest.update(js_file.name.encode())
        digest.update(js_file.read_bytes())
    return digest.hexdigest()[:12]


def _alembic_revision(doctor: DoctorState) -> str:
    for check in doctor.checks:
        if check.check_id == "alembic.current":
            return check.message
    return "unknown"


def build_artifacts(state: ReleasePlanState, doctor: DoctorState) -> list[PlannedArtifact]:
    head = state.repository.head_sha or _read_head()
    short = state.repository.head_short or short_sha(head) if head else "unknown"
    bundle = _frontend_bundle_id()
    alembic_rev = _alembic_revision(doctor)

    artifacts = [
        PlannedArtifact("Git SHA", head or short, "target commit for deploy"),
        PlannedArtifact("Frontend bundle", bundle, "planned dist/assets fingerprint"),
        PlannedArtifact("Docker image API", f"ifg-api:{short}", "planned tag — not built in plan mode"),
        PlannedArtifact("Docker image Worker", f"ifg-worker:{short}", "planned tag — not built in plan mode"),
        PlannedArtifact("Alembic revision", alembic_rev, "target schema revision"),
    ]

    compose_path = ROOT / COMPOSE_FILE
    if compose_path.is_file():
        artifacts.append(
            PlannedArtifact("Compose file", str(COMPOSE_FILE), "production compose definition")
        )

    for svc in REQUIRED_COMPOSE_SERVICES:
        artifacts.append(
            PlannedArtifact("Compose service", svc, f"service managed by {COMPOSE_FILE}")
        )

    return artifacts


def _read_head() -> str:
    try:
        return git("rev-parse", "HEAD")
    except RuntimeError:
        return ""
