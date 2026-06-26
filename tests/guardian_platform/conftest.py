"""Fixtures for Guardian Platform tests (independent from legacy ifg_guardian tests)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def platform_runtime():
    from guardian_platform.core.profiles.loader import load_platform

    return load_platform(["ifg", "psag_scaffold"])


@pytest.fixture
def core_only_runtime():
    from guardian_platform.core.profiles.loader import load_platform

    return load_platform([])


@pytest.fixture
def project_config(repo_root):
    from guardian_platform.core.config.loader import load_project_config

    return load_project_config(root=repo_root)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "gp@test"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "GP Test"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


@pytest.fixture
def production_git_repo(git_repo: Path) -> Path:
    subprocess.run(["git", "branch", "-M", "production"], cwd=git_repo, check=True, capture_output=True)
    return git_repo


def run_main(argv: list[str], *, cwd: Path | None = None) -> tuple[int, str]:
    from guardian_platform.core.cli.app import main
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()
