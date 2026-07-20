"""Regression tests for GWO-GUARDIAN-0083 image rebuild hard gate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.plugins.bootstrap import create_runtime  # noqa: E402

_runtime = create_runtime()
_runtime.shutdown()

from ifg_guardian.plugins.ifg.deploy_decision.image_inspect import (  # noqa: E402
    parse_image_inspect_payload,
)
from ifg_guardian.plugins.ifg.deploy_decision.image_rebuild_gate import (  # noqa: E402
    ImageRebuildDecision,
    evaluate_image_rebuild_gate,
    verify_deployed_image_matches_expected,
)
from ifg_guardian.plugins.ifg.deploy_decision.paths import is_image_context_path  # noqa: E402
from ifg_guardian.plugins.ifg.deploy_run.pipeline import build_deploy_pipeline  # noqa: E402
from ifg_guardian.plugins.ifg.release_plan.models import ReleasePlanState  # noqa: E402


class TestImageContextPaths:
    def test_app_is_image_context(self):
        assert is_image_context_path("app/services/foo.py")
        assert is_image_context_path("alembic/versions/x.py")
        assert is_image_context_path("pyproject.toml")
        assert is_image_context_path("docker/Dockerfile")

    def test_docs_not_image_context(self):
        assert not is_image_context_path("docs/reports/foo.md")
        assert not is_image_context_path("frontend-react/src/App.jsx")


class TestImageRebuildGate:
    def test_clean_repo_matching_label_allows_skip(self):
        result = evaluate_image_rebuild_gate(
            image_context_changes=[],
            dirty_image_context_files=[],
            expected_revision="abc123def456",
            deployed_revision="abc123def456",
            deployed_inspect_ok=True,
        )
        assert result.decision == ImageRebuildDecision.ALLOW_SKIP

    def test_app_change_requires_rebuild(self):
        result = evaluate_image_rebuild_gate(
            image_context_changes=["app/services/foo.py"],
            dirty_image_context_files=[],
            expected_revision="abc123",
            deployed_revision="old999",
            deployed_inspect_ok=True,
            committed_image_context_changes=["app/services/foo.py"],
        )
        assert result.decision == ImageRebuildDecision.REQUIRE_REBUILD
        assert "app/services/foo.py" in result.trigger_files

    def test_app_change_with_dirty_tree_never_skip_require_or_fail(self):
        # Dirty covers committed path → REQUIRE_REBUILD (never SKIP)
        overlapping = evaluate_image_rebuild_gate(
            image_context_changes=["app/main.py"],
            dirty_image_context_files=["app/main.py"],
            expected_revision="abc123",
            deployed_revision="abc123",
            deployed_inspect_ok=True,
            committed_image_context_changes=["app/main.py"],
        )
        assert overlapping.decision == ImageRebuildDecision.REQUIRE_REBUILD
        assert overlapping.decision != ImageRebuildDecision.ALLOW_SKIP

        # Dirty-only (not in commits) → FAIL (never SKIP)
        dirty_only = evaluate_image_rebuild_gate(
            image_context_changes=["app/main.py"],
            dirty_image_context_files=["app/main.py"],
            expected_revision="abc123",
            deployed_revision="abc123",
            deployed_inspect_ok=True,
            committed_image_context_changes=[],
        )
        assert dirty_only.decision == ImageRebuildDecision.FAIL
        assert dirty_only.decision != ImageRebuildDecision.ALLOW_SKIP

    def test_label_mismatch_requires_rebuild(self):
        result = evaluate_image_rebuild_gate(
            image_context_changes=[],
            dirty_image_context_files=[],
            expected_revision="newcommit01",
            deployed_revision="oldcommit99",
            deployed_inspect_ok=True,
        )
        assert result.decision == ImageRebuildDecision.REQUIRE_REBUILD

    def test_inspect_failed_without_local_changes_is_fail(self):
        result = evaluate_image_rebuild_gate(
            image_context_changes=[],
            dirty_image_context_files=[],
            expected_revision="abc123",
            deployed_revision=None,
            deployed_inspect_ok=False,
            defer_remote_verify=False,
        )
        assert result.decision == ImageRebuildDecision.FAIL

    def test_deferred_verify_allows_skip_when_clean(self):
        result = evaluate_image_rebuild_gate(
            image_context_changes=[],
            dirty_image_context_files=[],
            expected_revision="abc123",
            deployed_revision=None,
            deployed_inspect_ok=False,
            defer_remote_verify=True,
        )
        assert result.decision == ImageRebuildDecision.ALLOW_SKIP
        assert result.ambiguity == "deferred_remote_image_verify"

    def test_missing_label_requires_rebuild(self):
        result = evaluate_image_rebuild_gate(
            image_context_changes=[],
            dirty_image_context_files=[],
            expected_revision="abc123",
            deployed_revision=None,
            deployed_inspect_ok=True,
        )
        assert result.decision == ImageRebuildDecision.REQUIRE_REBUILD


class TestPostDeployImageVerify:
    def test_matching_label_ok(self):
        ok, msg = verify_deployed_image_matches_expected(
            expected_revision="abc123def",
            deployed_revision="abc123def",
            rebuild_was_required=True,
            image_id="sha256:deadbeef",
        )
        assert ok is True
        assert "abc123def"[:12] in msg

    def test_mismatch_makes_deploy_unsuccessful(self):
        ok, msg = verify_deployed_image_matches_expected(
            expected_revision="expected01",
            deployed_revision="wronglabel",
            rebuild_was_required=True,
            image_id="sha256:deadbeef",
        )
        assert ok is False
        assert "Niezgodność" in msg


class TestImageInspectParse:
    def test_parse_labels(self):
        payload = json.dumps(
            {
                "Id": "sha256:abc",
                "Config": {
                    "Labels": {
                        "ifg.git.commit": "deadbeefcafebabe",
                        "org.opencontainers.image.revision": "deadbeefcafebabe",
                    }
                },
            }
        )
        info = parse_image_inspect_payload(payload)
        assert info.inspect_ok
        assert info.image_id == "sha256:abc"
        assert info.git_commit == "deadbeefcafebabe"


class TestPipelineImageGate:
    def test_force_rebuild_prevents_skip(self):
        plan = ReleasePlanState()
        steps = build_deploy_pipeline(
            plan,
            force_docker_rebuild=True,
            docker_rebuild_reason="REQUIRE_REBUILD: app/ changed",
        )
        docker = next(s for s in steps if s.action == "docker build")
        assert docker.required is True
        assert docker.skipped is False
        assert "REQUIRE_REBUILD" in docker.reason

    def test_image_verify_step_always_present(self):
        plan = ReleasePlanState()
        steps = build_deploy_pipeline(plan, force_docker_rebuild=False)
        verify = next(s for s in steps if s.action == "image verify")
        assert verify.required is True
        assert verify.skipped is False
        assert verify.command == "ifg_guardian_image_verify"

    def test_clean_allows_docker_skip_but_verify_remains(self):
        plan = ReleasePlanState()
        steps = build_deploy_pipeline(plan, force_docker_rebuild=False)
        docker = next(s for s in steps if s.action == "docker build")
        assert docker.skipped is True
        verify = next(s for s in steps if s.action == "image verify")
        assert verify.required is True
