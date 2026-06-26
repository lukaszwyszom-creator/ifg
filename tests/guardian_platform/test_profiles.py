"""Guardian Platform profile registry tests."""
from __future__ import annotations

from guardian_platform.core.registry.profiles import ProfileInfo, ProfileRegistry
from guardian_platform.profiles.ifg.profile import IFGProfile
from guardian_platform.profiles.psag_scaffold.profile import PSAGScaffoldProfile
from guardian_platform.core.profiles.builtin import CoreProfile
from guardian_platform.core.registry.commands import CommandRegistry
from guardian_platform.core.registry.profiles import ProfileRegistrationContext
from guardian_platform.core.registry.workflows import WorkflowRegistry


class TestProfiles:
    def test_core_profile_id(self):
        assert CoreProfile().id == "core"

    def test_ifg_profile_id(self):
        assert IFGProfile().id == "ifg"

    def test_psag_profile_id(self):
        assert PSAGScaffoldProfile().id == "psag"

    def test_core_registers_workflow(self):
        ctx = ProfileRegistrationContext(
            profile_id="core",
            commands=CommandRegistry(),
            workflows=WorkflowRegistry(),
        )
        CoreProfile().register(ctx)
        assert ctx.workflows.get("core.ping") is not None

    def test_ifg_registers_seven_commands(self):
        ctx = ProfileRegistrationContext(
            profile_id="ifg",
            commands=CommandRegistry(),
            workflows=WorkflowRegistry(),
        )
        IFGProfile().register(ctx)
        ifg_cmds = [c for c in ctx.commands.list_commands() if c.profile == "ifg"]
        assert len(ifg_cmds) == 10

    def test_psag_registers_ping(self):
        ctx = ProfileRegistrationContext(
            profile_id="psag",
            commands=CommandRegistry(),
            workflows=WorkflowRegistry(),
        )
        PSAGScaffoldProfile().register(ctx)
        spec = ctx.commands.resolve_namespaced("psag", ["ping"])
        assert spec is not None

    def test_profile_registry_list(self):
        reg = ProfileRegistry()
        reg.register_info(ProfileInfo("ifg", "0.3.0", "IFG"), IFGProfile())
        assert len(reg.list_profiles()) == 1

    def test_profile_registry_get_instance(self):
        reg = ProfileRegistry()
        profile = IFGProfile()
        reg.register_info(ProfileInfo("ifg", "0.3.0", ""), profile)
        assert reg.get("ifg") is profile

    def test_ifg_commands_all_read_only_except_mutating(self):
        ctx = ProfileRegistrationContext(
            profile_id="ifg",
            commands=CommandRegistry(),
            workflows=WorkflowRegistry(),
        )
        IFGProfile().register(ctx)
        mutating_paths = {c.path for c in ctx.commands.list_commands() if c.profile == "ifg" and c.mutating}
        assert mutating_paths == {("deploy", "run"), ("prod", "recover"), ("repo", "cleanup")}
        for spec in ctx.commands.list_commands():
            if spec.profile == "ifg" and spec.path not in mutating_paths:
                assert spec.mutating is False

    def test_core_mutate_test_is_mutating(self, platform_runtime):
        cmds = platform_runtime.commands.list_commands()
        mutate = next(c for c in cmds if c.path == ("platform", "mutate-test"))
        assert mutate.mutating is True
