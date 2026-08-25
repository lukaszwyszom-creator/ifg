"""Tests for snapshot frontend npm ci + build and circular-blocker demotion."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.plugins.bootstrap import create_runtime  # noqa: E402

_runtime = create_runtime()
_runtime.shutdown()

from ifg_guardian.core.build_snapshot import (  # noqa: E402
    BuildSnapshot,
    cleanup_snapshot,
    snapshot_contains_env_production,
)
from ifg_guardian.core.workflow.executors import DeployExecutorContext, IntentExecutor  # noqa: E402
from ifg_guardian.core.workflow.executors.router import (  # noqa: E402
    DeployCommandKind,
    classify_deploy_command,
)
from ifg_guardian.core.workflow.intents import LocalExecIntent  # noqa: E402
from ifg_guardian.core.workflow.mode import ExecutionMode  # noqa: E402
from ifg_guardian.core.workflow.results import IntentResult  # noqa: E402
from ifg_guardian.plugins.ifg.doctor.aggregation import (  # noqa: E402
    aggregate_overall_status,
    effective_check_status,
)
from ifg_guardian.plugins.ifg.doctor.models import (  # noqa: E402
    CheckResult,
    CheckStatus,
    DoctorState,
    OverallStatus,
)
from ifg_guardian.plugins.ifg.release_evaluate.classification import classify_doctor_check  # noqa: E402
from ifg_guardian.plugins.ifg.release_evaluate.models import (  # noqa: E402
    FindingCategory,
    ReleaseDecisionStatus,
    ReleaseEvaluateState,
)
from ifg_guardian.plugins.ifg.release_evaluate.policy_engine import apply_policy_engine  # noqa: E402


NPM_PIPELINE_CMD = (
    "cd frontend-react && npm ci --prefer-offline --no-audit --no-fund && npm run build"
)


class TestNpmCiClassification:
    def test_pipeline_command_is_local_npm(self):
        assert classify_deploy_command(NPM_PIPELINE_CMD) == DeployCommandKind.LOCAL_NPM


class TestFrontendNpmExecutor:
    def test_npm_ci_runs_before_build(self, tmp_path: Path):
        frontend = tmp_path / "frontend-react"
        frontend.mkdir()
        (frontend / "package-lock.json").write_text("{}", encoding="utf-8")
        dist = frontend / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<html></html>", encoding="utf-8")
        assets = dist / "assets"
        assets.mkdir()
        (assets / "app.js").write_text("console.log(1)", encoding="utf-8")

        ctx = DeployExecutorContext(build_root=tmp_path, build_source="git_archive")
        executor = IntentExecutor(root=tmp_path, deploy_context=ctx)
        calls: list[list[str]] = []

        def fake_execute(intent: LocalExecIntent) -> IntentResult:
            calls.append(list(intent.command))
            return IntentResult(intent=intent, ok=True, output="ok", data={"exit_code": 0})

        with patch.object(executor._local, "execute", side_effect=fake_execute):
            intent = LocalExecIntent(command=["/bin/sh", "-c", NPM_PIPELINE_CMD], mutating=True)
            result = executor.execute(intent, ExecutionMode.LIVE)

        assert result.ok
        assert calls[0][:2] == ["npm", "ci"]
        assert "--prefer-offline" in calls[0]
        assert calls[1] == ["npm", "run", "build"]
        assert any("npm ci" in c for c in ctx.executed_commands)
        assert any("npm run build" in c for c in ctx.executed_commands)

    def test_missing_lockfile_blocks(self, tmp_path: Path):
        frontend = tmp_path / "frontend-react"
        frontend.mkdir()
        ctx = DeployExecutorContext(build_root=tmp_path, build_source="git_archive")
        executor = IntentExecutor(root=tmp_path, deploy_context=ctx)
        intent = LocalExecIntent(command=["/bin/sh", "-c", NPM_PIPELINE_CMD], mutating=True)
        result = executor.execute(intent, ExecutionMode.LIVE)
        assert not result.ok
        assert "package-lock.json" in (result.error or "")

    def test_npm_ci_failure_blocks(self, tmp_path: Path):
        frontend = tmp_path / "frontend-react"
        frontend.mkdir()
        (frontend / "package-lock.json").write_text("{}", encoding="utf-8")
        ctx = DeployExecutorContext(build_root=tmp_path, build_source="git_archive")
        executor = IntentExecutor(root=tmp_path, deploy_context=ctx)

        def fake_execute(intent: LocalExecIntent) -> IntentResult:
            if intent.command[:2] == ["npm", "ci"]:
                return IntentResult(intent=intent, ok=False, error="npm ci failed", data={})
            raise AssertionError("npm run build must not run after npm ci failure")

        with patch.object(executor._local, "execute", side_effect=fake_execute):
            intent = LocalExecIntent(command=["/bin/sh", "-c", NPM_PIPELINE_CMD], mutating=True)
            result = executor.execute(intent, ExecutionMode.LIVE)
        assert not result.ok
        assert "npm ci" in (result.error or "") or result.error

    def test_build_failure_blocks(self, tmp_path: Path):
        frontend = tmp_path / "frontend-react"
        frontend.mkdir()
        (frontend / "package-lock.json").write_text("{}", encoding="utf-8")
        ctx = DeployExecutorContext(build_root=tmp_path, build_source="git_archive")
        executor = IntentExecutor(root=tmp_path, deploy_context=ctx)

        def fake_execute(intent: LocalExecIntent) -> IntentResult:
            if intent.command[:2] == ["npm", "ci"]:
                return IntentResult(intent=intent, ok=True, output="ok", data={})
            return IntentResult(intent=intent, ok=False, error="build failed", data={})

        with patch.object(executor._local, "execute", side_effect=fake_execute):
            intent = LocalExecIntent(command=["/bin/sh", "-c", NPM_PIPELINE_CMD], mutating=True)
            result = executor.execute(intent, ExecutionMode.LIVE)
        assert not result.ok
        assert "build failed" in (result.error or "")

    def test_missing_dist_after_build_blocks(self, tmp_path: Path):
        frontend = tmp_path / "frontend-react"
        frontend.mkdir()
        (frontend / "package-lock.json").write_text("{}", encoding="utf-8")
        ctx = DeployExecutorContext(build_root=tmp_path, build_source="git_archive")
        executor = IntentExecutor(root=tmp_path, deploy_context=ctx)

        def fake_execute(intent: LocalExecIntent) -> IntentResult:
            return IntentResult(intent=intent, ok=True, output="ok", data={})

        with patch.object(executor._local, "execute", side_effect=fake_execute):
            intent = LocalExecIntent(command=["/bin/sh", "-c", NPM_PIPELINE_CMD], mutating=True)
            result = executor.execute(intent, ExecutionMode.LIVE)
        assert not result.ok
        assert "Artifact Verification Gate" in (result.error or "")


class TestCircularBlockerDemotion:
    def test_stale_dist_is_build_required_not_doctor_blocked(self):
        state = DoctorState(
            checks=[
                CheckResult(
                    "frontend.dist_freshness",
                    "frontend",
                    "dist freshness",
                    CheckStatus.WARN,
                    "BUILD_REQUIRED: missing dist",
                ),
                CheckResult(
                    "frontend.build_required",
                    "frontend",
                    "npm run build",
                    CheckStatus.WARN,
                    "BUILD_REQUIRED: needs build",
                ),
            ]
        )
        assert aggregate_overall_status(state) == OverallStatus.READY_WITH_WARNINGS
        assert effective_check_status(state.checks[0]) == CheckStatus.WARN
        finding = classify_doctor_check(state.checks[0])
        assert finding.category == FindingCategory.WARNING

    def test_policy_does_not_hard_block_on_prebuild_dist(self):
        doctor = DoctorState(
            checks=[
                CheckResult(
                    "frontend.build_required",
                    "frontend",
                    "npm run build",
                    CheckStatus.WARN,
                    "BUILD_REQUIRED: stale",
                ),
                CheckResult(
                    "frontend.dist_freshness",
                    "frontend",
                    "dist freshness",
                    CheckStatus.WARN,
                    "BUILD_REQUIRED: stale",
                ),
            ]
        )
        state = ReleaseEvaluateState(
            changed_files=["frontend-react/src/App.jsx"],
            allow_dirty_build=False,
            test_discovery_ok=True,
        )
        policy = {
            "profiles": {"smb": {"staging_available": False}},
            "default_deployment_profile": "smb",
            "rules": {},
        }
        apply_policy_engine(state, doctor=doctor, policy=policy)
        assert state.status != ReleaseDecisionStatus.PRODUCTION_BLOCKED
        assert "frontend_change_requires_pipeline_build" in state.policy_rules_triggered


class TestSnapshotEnvGuard:
    def test_env_production_not_in_helper(self, tmp_path: Path):
        tree = tmp_path / "tree"
        tree.mkdir()
        assert snapshot_contains_env_production(tree) is False
        (tree / ".env.production").write_text("SECRET=1\n", encoding="utf-8")
        assert snapshot_contains_env_production(tree) is True

    def test_cleanup_removes_node_modules(self, tmp_path: Path):
        # Minimal fake snapshot layout
        snap_root = tmp_path / "snap"
        tree = snap_root / "tree" / "frontend-react"
        nm = tree / "node_modules" / "x"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("1", encoding="utf-8")
        dist = tree / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("x", encoding="utf-8")
        snap = BuildSnapshot(
            commit_sha="abc",
            snapshot_root=snap_root,
            tree_dir=snap_root / "tree",
            meta_dir=snap_root / ".ifg_guardian_snapshot",
            manifest_path=snap_root / ".ifg_guardian_snapshot" / "manifest.json",
            manifest_sha256="0" * 64,
            source_root=tmp_path,
            source_wip_detected=False,
        )
        snap.meta_dir.mkdir(parents=True, exist_ok=True)
        cleanup_snapshot(snap)
        assert not snap_root.exists()
