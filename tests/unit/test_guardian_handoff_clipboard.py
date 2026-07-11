from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.clipboard import copy_text_to_clipboard  # noqa: E402
from ifg_guardian.modules.ifg_handoff import run_ifg_handoff_latest  # noqa: E402


def _init_journal(root: Path) -> None:
    handoff_dir = root / "docs" / "handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    (handoff_dir / "index.json").write_text(
        '{"schema_version": 1, "next_handoff_id": 1, "latest_handoff_id": null, "count": 0}\n',
        encoding="utf-8",
    )
    (handoff_dir / "latest.md").write_text("", encoding="utf-8")


def test_copy_text_to_clipboard_verifies_round_trip(monkeypatch):
    state = {"value": ""}

    def fake_run(cmd, **kwargs):
        if cmd == ["pbcopy"]:
            state["value"] = kwargs.get("input", "")
            return MagicMock(returncode=0, stderr="")
        if cmd == ["pbpaste"]:
            return MagicMock(returncode=0, stdout=state["value"], stderr="")
        raise AssertionError(f"unexpected cmd: {cmd}")

    monkeypatch.setattr("ifg_guardian.core.clipboard.shutil.which", lambda _: "/usr/bin/pb")
    monkeypatch.setattr("ifg_guardian.core.clipboard.platform.system", lambda: "Darwin")
    monkeypatch.setattr("ifg_guardian.core.clipboard.subprocess.run", fake_run)

    ok, reason = copy_text_to_clipboard("# HANDOFF\n\ntreść")
    assert ok is True
    assert reason == ""


def test_copy_text_to_clipboard_reports_mismatch(monkeypatch):
    def fake_run(cmd, **kwargs):
        if cmd == ["pbcopy"]:
            return MagicMock(returncode=0, stderr="")
        if cmd == ["pbpaste"]:
            return MagicMock(returncode=0, stdout="inna zawartość", stderr="")
        raise AssertionError(f"unexpected cmd: {cmd}")

    monkeypatch.setattr("ifg_guardian.core.clipboard.shutil.which", lambda _: "/usr/bin/pb")
    monkeypatch.setattr("ifg_guardian.core.clipboard.platform.system", lambda: "Darwin")
    monkeypatch.setattr("ifg_guardian.core.clipboard.subprocess.run", fake_run)

    ok, reason = copy_text_to_clipboard("oczekiwana treść")
    assert ok is False
    assert "schowka" in reason


def test_handoff_prints_clipboard_success_message(tmp_path: Path, capsys, monkeypatch):
    _init_journal(tmp_path)
    reports = tmp_path / "docs" / "reports"
    reports.mkdir(parents=True)
    (reports / "2026-07-11_GWO-IFG-9001_A.md").write_text(
        "# GWO-IFG-9001\n\n## Decyzje dla ChatGPT\n\nBrak.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "ifg_guardian.modules.ifg_handoff.copy_text_to_clipboard",
        lambda content: (True, ""),
    )

    code = run_ifg_handoff_latest(root=tmp_path, copy_to_clipboard=True)
    output = capsys.readouterr().out

    assert code == 0
    assert "✓ Handoff wygenerowany" in output
    assert "✓ Skopiowano do schowka" in output
    assert "✓ Gotowy do wklejenia do ChatGPT" in output


def test_handoff_prints_clipboard_failure_message(tmp_path: Path, capsys, monkeypatch):
    _init_journal(tmp_path)
    reports = tmp_path / "docs" / "reports"
    reports.mkdir(parents=True)
    (reports / "2026-07-11_GWO-IFG-9002_A.md").write_text(
        "# GWO-IFG-9002\n\n## Decyzje dla ChatGPT\n\nBrak.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "ifg_guardian.core.clipboard.copy_text_to_clipboard",
        lambda _content: (False, "pbcopy exit 1"),
    )

    code = run_ifg_handoff_latest(root=tmp_path, copy_to_clipboard=True)
    captured = capsys.readouterr()

    assert code == 1
    assert "✗ Handoff workflow FAILED" in captured.err
