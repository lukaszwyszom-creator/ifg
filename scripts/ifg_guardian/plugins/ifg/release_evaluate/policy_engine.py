from __future__ import annotations

import json
import os
from pathlib import Path

from ifg_guardian.config import DEPLOYMENT_PROFILE, ROOT
from ifg_guardian.plugins.ifg.doctor.models import DoctorState
from ifg_guardian.plugins.ifg.release_evaluate.classification import get_rule_penalty
from ifg_guardian.plugins.ifg.release_evaluate.models import ReleaseDecisionStatus, ReleaseEvaluateState

POLICY_PATH = ROOT / "scripts" / "ifg_guardian" / "policies" / "ifg_production.yaml"

DIRTY_TREE_BLOCK_MESSAGE = (
    "Production deployment blocked. Working tree contains uncommitted changes."
)
DIRTY_TREE_OVERRIDE_WARNING = (
    "Production build from dirty working tree (--allow-dirty-build)."
)


def load_policy_config(path: Path = POLICY_PATH) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"missing policy file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid policy file format: {path}") from exc


def _max_status(a: ReleaseDecisionStatus, b: ReleaseDecisionStatus) -> ReleaseDecisionStatus:
    rank = {
        ReleaseDecisionStatus.READY_FOR_DEPLOY: 0,
        ReleaseDecisionStatus.READY_WITH_WARNINGS: 1,
        ReleaseDecisionStatus.READY_WITH_OVERRIDE: 2,
        ReleaseDecisionStatus.STAGING_ONLY: 3,
        ReleaseDecisionStatus.PRODUCTION_BLOCKED: 4,
    }
    return a if rank[a] >= rank[b] else b


def _working_tree_dirty(
    state: ReleaseEvaluateState,
    *,
    report_prefixes: tuple[str, ...] = (),
) -> bool:
    for entry in state.git_status_entries:
        path = (entry.get("path") or "").strip()
        code = (entry.get("code") or "").strip()
        if not path:
            continue
        if code == "??" and (path == "backups" or path.startswith("backups/")):
            continue
        if report_prefixes and any(path.startswith(prefix) for prefix in report_prefixes):
            continue
        return True
    return False


def apply_policy_engine(state: ReleaseEvaluateState, *, doctor: DoctorState, policy: dict) -> None:
    decision = ReleaseDecisionStatus.READY_FOR_DEPLOY
    rules: list[str] = []
    blockers: list[str] = []
    required_actions = list(state.required_actions)

    check_by_id = {c.check_id: c for c in doctor.checks}
    has_fail = any(c.status.value == "FAIL" for c in doctor.checks)
    has_critical = any(c.status.value == "CRITICAL" for c in doctor.checks)

    changed_lower = [p.lower() for p in state.changed_files]
    backend_changed = any(p.startswith("app/") or p.startswith("alembic/") for p in changed_lower)
    frontend_changed = any(p.startswith("frontend-react/") for p in changed_lower)
    alembic_changed = any(p.startswith("alembic/") for p in changed_lower)

    deployment_profile = os.getenv(
        "GUARDIAN_DEPLOYMENT_PROFILE",
        policy.get("default_deployment_profile", DEPLOYMENT_PROFILE),
    )
    profiles_cfg = policy.get("profiles", {})
    profile_cfg = profiles_cfg.get(deployment_profile, {})
    staging_available = bool(profile_cfg.get("staging_available", deployment_profile == "enterprise"))
    state.deployment_profile = deployment_profile

    report_prefixes = tuple(policy.get("report_paths", []))
    if _working_tree_dirty(state, report_prefixes=report_prefixes):
        if state.allow_dirty_build:
            decision = _max_status(decision, ReleaseDecisionStatus.READY_WITH_OVERRIDE)
            rules.append("dirty_tree_build_with_override")
            state.warnings.append(DIRTY_TREE_OVERRIDE_WARNING)
            required_actions.append(
                "Potwierdź świadomy deploy z flagą --allow-dirty-build (build z lokalnego dirty tree)."
            )
            state.release_score = max(
                0,
                state.release_score - get_rule_penalty(policy, "dirty_tree_build_with_override"),
            )
        else:
            decision = ReleaseDecisionStatus.PRODUCTION_BLOCKED
            state.production_blocked = True
            rules.append("dirty_working_tree_blocks_production")
            blockers.append(DIRTY_TREE_BLOCK_MESSAGE)
            required_actions.append(
                "Zacommituj zmiany lub użyj jawnego override: guardian ifg deploy run --allow-dirty-build --yes"
            )

    if alembic_changed:
        required_actions.append("Wykonaj migrację DB w kontrolowanym deploy pipeline.")
        if staging_available:
            decision = _max_status(decision, ReleaseDecisionStatus.STAGING_ONLY)
            state.staging_required = True
            rules.append("alembic_changes_require_staging")
        else:
            rules.append("migration_change_requires_controlled_deploy")

    critical_tables = set(policy.get("critical_migration_tables", []))
    critical_hits = [name for name in critical_tables if any(name in p for p in changed_lower)]
    if critical_hits:
        state.backup_required = True
        if staging_available:
            state.staging_required = True
            decision = _max_status(decision, ReleaseDecisionStatus.STAGING_ONLY)
            rules.append("critical_table_migration_requires_backup")
        else:
            rules.append("critical_db_change_requires_verified_backup")
        required_actions.append(
            "Wykonaj backup DB przed produkcją (krytyczne tabele migracji: "
            + ", ".join(sorted(critical_hits))
            + ")."
        )

    if not state.test_discovery_ok and not state.test_discovery_local_env:
        decision = ReleaseDecisionStatus.PRODUCTION_BLOCKED
        state.production_blocked = True
        rules.append("tests_must_pass")
        blockers.append("Test discovery failed.")
        penalty = get_rule_penalty(policy, "tests_must_pass")
        if penalty:
            state.release_score = max(0, state.release_score - penalty)
        required_actions.append("Napraw test discovery i uruchom ponownie evaluate.")

    frontend_build = check_by_id.get("frontend.build_required")
    if frontend_changed and frontend_build is not None and frontend_build.status.value in {"FAIL", "CRITICAL"}:
        decision = ReleaseDecisionStatus.PRODUCTION_BLOCKED
        state.production_blocked = True
        rules.append("frontend_change_requires_passing_build")
        blockers.append("Frontend changed and build check failed.")
        required_actions.append("Zbuduj frontend (`npm run build`) i odśwież artefakty dist.")

    if backend_changed:
        rules.append("backend_change_requires_api_worker_rebuild")
        required_actions.append("Wymagany rebuild obrazów api/worker przed produkcją.")

    block_patterns = [s.lower() for s in policy.get("non_report_untracked_block_patterns", [])]
    suspicious_untracked: list[str] = []
    normal_untracked: list[str] = []
    for entry in state.git_status_entries:
        if entry.get("code") != "??":
            continue
        path = (entry.get("path") or "").strip()
        if not path:
            continue
        low = path.lower()
        if report_prefixes and any(path.startswith(prefix) for prefix in report_prefixes):
            continue
        if any(pattern in low for pattern in block_patterns):
            suspicious_untracked.append(path)
        else:
            normal_untracked.append(path)

    if suspicious_untracked:
        decision = ReleaseDecisionStatus.PRODUCTION_BLOCKED
        state.production_blocked = True
        rules.append("suspicious_untracked_files_block")
        blockers.append(
            "Suspicious untracked files detected: " + ", ".join(sorted(suspicious_untracked)[:8])
        )
        required_actions.append(
            "Usuń/obsłuż podejrzane untracked pliki: " + ", ".join(sorted(suspicious_untracked)[:8])
        )
    elif normal_untracked:
        decision = _max_status(decision, ReleaseDecisionStatus.READY_WITH_WARNINGS)
        rules.append("untracked_files_warn")
        required_actions.append(
            "Zweryfikuj untracked pliki przed produkcją: " + ", ".join(sorted(normal_untracked)[:8])
        )

    if has_critical:
        decision = ReleaseDecisionStatus.PRODUCTION_BLOCKED
        state.production_blocked = True
        rules.append("doctor_critical_fail_blocks_production")
        critical_checks = [
            f"[{c.group}] {c.name}: {c.message}" for c in doctor.checks if c.status.value == "CRITICAL"
        ]
        blockers.extend(critical_checks)
    elif has_fail:
        if staging_available:
            decision = _max_status(decision, ReleaseDecisionStatus.STAGING_ONLY)
            state.staging_required = True
            rules.append("doctor_fail_requires_staging")
        else:
            rules.append("doctor_fail_warn_single_production")

    # Hard blockers from doctor checks that indicate real deploy unsafety.
    hard_block_ids = {
        "repo.deploy_blockers",
        "config.required_vars",
        "docker.compose_config",
        "docker.containers",
        "health.endpoint",
    }
    for check in doctor.checks:
        if check.check_id in hard_block_ids and check.status.value in {"FAIL", "CRITICAL"}:
            decision = ReleaseDecisionStatus.PRODUCTION_BLOCKED
            state.production_blocked = True
            rules.append("doctor_hard_block_check")
            blockers.append(f"[{check.group}] {check.name}: {check.message}")

    state.policy_rules_triggered = rules
    state.blockers = list(dict.fromkeys(blockers))
    state.required_actions = list(dict.fromkeys(required_actions))
    if decision == ReleaseDecisionStatus.READY_FOR_DEPLOY and (
        state.warnings or state.required_actions
    ):
        decision = ReleaseDecisionStatus.READY_WITH_WARNINGS
    state.status = decision
    state.production_blocked = decision == ReleaseDecisionStatus.PRODUCTION_BLOCKED
    if decision == ReleaseDecisionStatus.PRODUCTION_BLOCKED:
        state.deployment_recommendation = "Deploy zablokowany"
        state.next_step = "Usuń blockery polityk i uruchom ponownie guardian release evaluate."
    elif decision == ReleaseDecisionStatus.STAGING_ONLY:
        state.deployment_recommendation = "Wymagany staging"
        state.next_step = "Wykonaj staging + checklistę akcji wymaganych, potem ponowna ocena."
    elif decision == ReleaseDecisionStatus.READY_WITH_OVERRIDE:
        state.deployment_recommendation = "Deploy możliwy z jawnym override dirty tree"
        state.next_step = "Uruchom deploy z --allow-dirty-build --yes po świadomej akceptacji ryzyka."
    elif decision == ReleaseDecisionStatus.READY_WITH_WARNINGS:
        state.deployment_recommendation = "Deploy możliwy z ostrzeżeniami"
    else:
        state.deployment_recommendation = "Deploy możliwy"
