"""Guardian Platform runtime and guard tests."""
from __future__ import annotations

import pytest
from guardian_platform.core.registry.commands import CommandSpec
from guardian_platform.core.runtime.context import CommandContext
from guardian_platform.core.runtime.guards import MutatingCommandBlocked, ensure_mutating_allowed
from guardian_platform.core.runtime.mode import ExecutionMode
from guardian_platform.core.config.models import ProjectConfig
from pathlib import Path


def _noop(ctx):
    return 0


class TestRuntime:
    def test_execution_mode_live(self):
        ctx = CommandContext(root=Path("."), config=ProjectConfig(), argv=[])
        assert ctx.execution_mode == ExecutionMode.LIVE

    def test_execution_mode_dry_run(self):
        ctx = CommandContext(root=Path("."), config=ProjectConfig(), argv=[], dry_run=True)
        assert ctx.execution_mode == ExecutionMode.DRY_RUN

    def test_execution_mode_simulates_mutations(self):
        assert ExecutionMode.DRY_RUN.simulates_mutations is True
        assert ExecutionMode.LIVE.simulates_mutations is False

    def test_mutating_blocked_without_yes(self):
        spec = CommandSpec("core", ("mutate",), _noop, mutating=True)
        with pytest.raises(MutatingCommandBlocked):
            ensure_mutating_allowed(spec=spec, assume_yes=False, dry_run=False)

    def test_mutating_allowed_with_yes(self):
        spec = CommandSpec("core", ("mutate",), _noop, mutating=True)
        ensure_mutating_allowed(spec=spec, assume_yes=True, dry_run=False)

    def test_mutating_allowed_in_dry_run(self):
        spec = CommandSpec("core", ("mutate",), _noop, mutating=True)
        ensure_mutating_allowed(spec=spec, assume_yes=False, dry_run=True)

    def test_non_mutating_never_blocked(self):
        spec = CommandSpec("core", ("ping",), _noop, mutating=False)
        ensure_mutating_allowed(spec=spec, assume_yes=False, dry_run=False)

    def test_mutating_blocked_message(self):
        spec = CommandSpec("core", ("platform", "mutate-test"), _noop, mutating=True)
        with pytest.raises(MutatingCommandBlocked) as exc:
            ensure_mutating_allowed(spec=spec, assume_yes=False, dry_run=False)
        assert "requires --yes" in str(exc.value)

    def test_command_context_extra_defaults_empty(self):
        ctx = CommandContext(root=Path("."), config=ProjectConfig(), argv=[])
        assert ctx.extra == {}

    def test_project_config_defaults(self, repo_root):
        cfg = ProjectConfig.defaults(repo_root)
        assert cfg.root == repo_root.resolve()
