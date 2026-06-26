"""Guardian Platform command registry tests."""
from __future__ import annotations

from guardian_platform.core.registry.commands import CommandRegistry, CommandSpec


def _handler(ctx):
    return 0


class TestCommandRegistry:
    def test_register_and_list(self):
        reg = CommandRegistry()
        spec = CommandSpec("core", ("plugin", "list"), _handler, help="list plugins")
        reg.register(spec)
        assert len(reg.list_commands()) == 1

    def test_resolve_core_command(self):
        reg = CommandRegistry()
        reg.register(CommandSpec("core", ("repo", "status"), _handler))
        assert reg.resolve(["repo", "status"]) is not None

    def test_resolve_unknown_returns_none(self):
        reg = CommandRegistry()
        assert reg.resolve(["missing"]) is None

    def test_resolve_namespaced_ifg(self):
        reg = CommandRegistry()
        reg.register(CommandSpec("ifg", ("deploy", "check"), _handler))
        spec = reg.resolve_namespaced("ifg", ["deploy", "check"])
        assert spec is not None
        assert spec.path == ("deploy", "check")

    def test_resolve_namespaced_wrong_profile(self):
        reg = CommandRegistry()
        reg.register(CommandSpec("ifg", ("ping",), _handler))
        assert reg.resolve_namespaced("psag", ["ping"]) is None

    def test_profiles_with_commands_groups(self):
        reg = CommandRegistry()
        reg.register(CommandSpec("core", ("plugin", "list"), _handler))
        reg.register(CommandSpec("ifg", ("ping",), _handler))
        grouped = reg.profiles_with_commands()
        assert "core" in grouped
        assert "ifg" in grouped

    def test_command_spec_dotted(self):
        spec = CommandSpec("ifg", ("deploy", "check"), _handler)
        assert spec.dotted == "ifg deploy check"

    def test_command_spec_mutating_flag(self):
        spec = CommandSpec("core", ("mutate",), _handler, mutating=True)
        assert spec.mutating is True

    def test_multiple_commands_same_profile(self):
        reg = CommandRegistry()
        reg.register(CommandSpec("ifg", ("doctor",), _handler))
        reg.register(CommandSpec("ifg", ("ping",), _handler))
        assert len(reg.profiles_with_commands()["ifg"]) == 2

    def test_resolve_longest_core_path(self, platform_runtime):
        spec = platform_runtime.commands.resolve(["workflow", "run"])
        assert spec is not None
        assert spec.path == ("workflow", "run")

    def test_ifg_commands_registered(self, platform_runtime):
        grouped = platform_runtime.commands.profiles_with_commands()
        paths = {c.path for c in grouped["ifg"]}
        assert ("doctor",) in paths
        assert ("deploy", "check") in paths
        assert ("repo", "audit") in paths

    def test_psag_ping_registered(self, platform_runtime):
        spec = platform_runtime.commands.resolve_namespaced("psag", ["ping"])
        assert spec is not None

    def test_core_plugin_list_registered(self, platform_runtime):
        spec = platform_runtime.commands.resolve(["plugin", "list"])
        assert spec is not None

    def test_core_repo_audit_registered(self, platform_runtime):
        spec = platform_runtime.commands.resolve(["repo", "audit"])
        assert spec is not None
