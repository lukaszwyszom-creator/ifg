"""Guardian Platform PSAG profile tests."""
from __future__ import annotations

from guardian_platform.core.profiles.loader import load_platform
from guardian_platform.profiles.psag_scaffold.profile import PSAGScaffoldProfile
from tests.guardian_platform.conftest import run_main


class TestPSAGProfile:
    def test_profile_loads(self):
        rt = load_platform(["psag_scaffold"])
        assert "psag" in {p.profile_id for p in rt.profiles.list_profiles()}

    def test_ping_command_registered(self):
        rt = load_platform(["psag_scaffold"])
        spec = rt.commands.resolve_namespaced("psag", ["ping"])
        assert spec is not None

    def test_ping_cli_output(self):
        code, out = run_main(["psag", "ping"])
        assert code == 0
        assert "psag scaffold active" in out

    def test_profile_description(self):
        assert "PSAG" in PSAGScaffoldProfile().description

    def test_profile_id_is_psag(self):
        assert PSAGScaffoldProfile().id == "psag"

    def test_only_ping_command(self):
        rt = load_platform(["psag_scaffold"])
        psag_cmds = [c for c in rt.commands.list_commands() if c.profile == "psag"]
        assert len(psag_cmds) == 1
        assert psag_cmds[0].path == ("ping",)

    def test_psag_without_ifg(self):
        rt = load_platform(["psag_scaffold"])
        ids = {p.profile_id for p in rt.profiles.list_profiles()}
        assert "ifg" not in ids
