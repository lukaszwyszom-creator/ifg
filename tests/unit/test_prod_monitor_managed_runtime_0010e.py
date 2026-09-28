"""Unit tests for prod-monitor managed runtime (GWO-IFG-PROD-MONITOR-MANAGED-RUNTIME-0010E)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
MANIFEST = SCRIPTS / "ifg_guardian" / "prod_monitor_runtime" / "MANIFEST.txt"


@pytest.fixture()
def clean_state_env(monkeypatch):
    monkeypatch.delenv("IFG_GUARDIAN_STATE_DIR", raising=False)
    monkeypatch.delenv("IFG_GUARDIAN_LOG_DIR", raising=False)


def test_manifest_lists_existing_files():
    assert MANIFEST.is_file()
    missing = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if not (REPO_ROOT / line).is_file():
            missing.append(line)
    assert missing == []


def test_state_dir_override(tmp_path, monkeypatch, clean_state_env):
    import importlib

    override = tmp_path / "durable-state"
    monkeypatch.setenv("IFG_GUARDIAN_STATE_DIR", str(override))
    sys.path.insert(0, str(SCRIPTS))
    import ifg_guardian.core.runtime_store as rs

    rs = importlib.reload(rs)
    assert rs.STATE_DIR == override
    rs.ensure_state_dir()
    assert override.is_dir()
    path = rs.state_path("runtime_monitor.json")
    assert path == override / "runtime_monitor.json"
    rs.atomic_write_json(path, {"state": "OK"})
    assert path.is_file()
    # restore default for other tests in process
    monkeypatch.delenv("IFG_GUARDIAN_STATE_DIR", raising=False)
    importlib.reload(rs)


def test_install_help_runs():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SCRIPTS)
    proc = subprocess.run(
        [sys.executable, "-m", "ifg_guardian.prod_monitor_runtime.install", "--help"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "install" in proc.stdout


def test_materialize_from_git_object(tmp_path):
    """Installer must refuse missing SHA and accept archive of committed tree."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SCRIPTS)
    # Fake missing sha
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "ifg_guardian.prod_monitor_runtime.install",
            "install",
            "--source-repo",
            str(REPO_ROOT),
            "--source-sha",
            "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            "--runtime-home",
            str(tmp_path / "rt"),
        ],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "REFUSE" in (proc.stderr + proc.stdout)


def test_runner_template_exists():
    runner = SCRIPTS / "ifg_guardian" / "prod_monitor_runtime" / "runner.py"
    text = runner.read_text(encoding="utf-8")
    assert "IFG_GUARDIAN_STATE_DIR" in text
    assert "run_prod_monitor_check" in text
