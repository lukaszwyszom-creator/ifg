"""Regression: legacy Guardian remains independent."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"


class TestLegacyGuardianRegression:
    def test_legacy_guardian_doctor_runs(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "guardian.py"), "doctor"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert "IFG Doctor" in result.stdout or "Doctor" in result.stdout
        assert result.returncode in (0, 1)

    def test_legacy_guardian_module_importable(self):
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
        import ifg_guardian  # noqa: F401

    def test_platform_does_not_replace_guardian_py(self):
        assert (SCRIPTS / "guardian.py").is_file()
        assert (SCRIPTS / "guardian_platform").is_dir()

    def test_legacy_tests_still_pass(self):
        result = subprocess.run(
            [
                str(REPO_ROOT / ".venv/bin/python"),
                "-m",
                "pytest",
                "tests/unit/",
                "-k",
                "guardian",
                "-q",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "passed" in result.stdout
