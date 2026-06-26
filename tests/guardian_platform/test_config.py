"""Guardian Platform config loader tests."""
from __future__ import annotations

from pathlib import Path

from guardian_platform.core.config.loader import _find_config_file, _parse_profiles_active, load_project_config


class TestConfigLoader:
    def test_finds_guardian_yml_in_repo(self, repo_root):
        path = _find_config_file(repo_root)
        assert path is not None
        assert path.name in (".guardian.yml", ".guardian.yaml")

    def test_parse_profiles_active(self):
        lines = [
            "profiles:",
            "  active:",
            "    - ifg",
            "    - psag_scaffold",
        ]
        assert _parse_profiles_active(lines) == ["ifg", "psag_scaffold"]

    def test_load_project_config_active_profiles(self, repo_root):
        cfg = load_project_config(root=repo_root)
        assert "ifg" in cfg.active_profiles

    def test_load_project_config_root(self, repo_root):
        cfg = load_project_config(root=repo_root)
        assert cfg.root.resolve() == repo_root.resolve()

    def test_load_project_config_reports_dir(self, repo_root):
        cfg = load_project_config(root=repo_root)
        assert cfg.reports_dir.name == "guardian"

    def test_defaults_when_no_config(self, tmp_path):
        cfg = load_project_config(root=tmp_path)
        assert cfg.schema == "guardian_project_v1"

    def test_find_config_not_found_in_empty_dir(self, tmp_path):
        assert _find_config_file(tmp_path) is None

    def test_parse_profiles_active_stops_at_next_key(self):
        lines = ["active:", "  - ifg", "other: value"]
        assert _parse_profiles_active(lines) == ["ifg"]
