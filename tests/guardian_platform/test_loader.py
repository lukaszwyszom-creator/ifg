"""Guardian Platform profile loader tests."""
from __future__ import annotations

from guardian_platform.core.profiles.loader import load_platform


class TestProfileLoader:
    def test_loads_core_always(self):
        rt = load_platform([])
        assert "core" in {p.profile_id for p in rt.profiles.list_profiles()}

    def test_loads_ifg_and_psag(self):
        rt = load_platform(["ifg", "psag_scaffold"])
        ids = {p.profile_id for p in rt.profiles.list_profiles()}
        assert ids == {"core", "ifg", "psag"}

    def test_ifg_scaffold_alias_dedupes(self):
        rt = load_platform(["ifg", "ifg_scaffold", "psag_scaffold"])
        ifg_cmds = rt.commands.profiles_with_commands().get("ifg", [])
        assert len(ifg_cmds) == 10

    def test_unknown_profile_skipped(self):
        rt = load_platform(["nonexistent_profile"])
        ids = {p.profile_id for p in rt.profiles.list_profiles()}
        assert ids == {"core"}

    def test_core_commands_present(self):
        rt = load_platform(["ifg"])
        paths = {tuple(c.path) for c in rt.commands.list_commands() if c.profile == "core"}
        assert ("plugin", "list") in paths
        assert ("workflow", "list") in paths

    def test_ifg_version_m3(self):
        rt = load_platform(["ifg"])
        info = next(p for p in rt.profiles.list_profiles() if p.profile_id == "ifg")
        assert info.version.startswith("0.5")

    def test_psag_description(self):
        rt = load_platform(["psag_scaffold"])
        info = next(p for p in rt.profiles.list_profiles() if p.profile_id == "psag")
        assert "PSAG" in info.description

    def test_workflows_registered_with_core(self):
        rt = load_platform([])
        assert rt.workflows.get("core.ping") is not None

    def test_profile_instances_retrievable(self):
        rt = load_platform(["ifg"])
        assert rt.profiles.get("ifg") is not None

    def test_only_ifg_profile_commands(self):
        rt = load_platform(["ifg"])
        ifg_cmds = [c for c in rt.commands.list_commands() if c.profile == "ifg"]
        assert len(ifg_cmds) >= 9
