from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian import cli  # noqa: E402
from ifg_guardian.modules.ifg_handoff import (  # noqa: E402
    extract_decision_points,
    run_ifg_handoff_latest,
    select_latest_reports,
)


def _init_journal(root: Path) -> None:
    handoff_dir = root / "docs" / "handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    (handoff_dir / "index.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "next_handoff_id": 1,
                "latest_handoff_id": None,
                "count": 0,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (handoff_dir / "latest.md").write_text("", encoding="utf-8")


def _latest_handoff_text(root: Path) -> str:
    return (root / "docs" / "handoff" / "latest.md").read_text(encoding="utf-8")


def _write_report(path: Path, content: str, *, mtime_offset_s: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if mtime_offset_s:
        ts = path.stat().st_mtime + mtime_offset_s
        os.utime(path, (ts, ts))


def test_select_latest_reports_prefers_newest_gwo_by_mtime(tmp_path: Path):
    reports = tmp_path / "docs" / "reports"
    _write_report(reports / "2026-07-08_GWO-IFG-0054_OLD.md", "# old")
    _write_report(
        reports / "2026-07-09_GWO-IFG-0055_NEW.md",
        "# new",
        mtime_offset_s=1,
    )

    selection = select_latest_reports(root=tmp_path, today=dt.date(2026, 7, 9), limit=1)
    assert selection.preferred_today is True
    assert len(selection.reports) == 1
    assert selection.reports[0].name == "2026-07-09_GWO-IFG-0055_NEW.md"


def test_run_ifg_handoff_latest_writes_journal_handoff(tmp_path: Path):
    _init_journal(tmp_path)
    reports = tmp_path / "docs" / "reports"
    _write_report(
        reports / "2026-07-09_GWO-IFG-0062_A.md",
        "# GWO-IFG-0062\n\n## Decyzje dla ChatGPT\n\n- Czy wdrożyć zmianę na produkcję?\n\nTreść A",
    )
    _write_report(
        reports / "2026-07-09_GWO-IFG-0055_B.md",
        "# GWO-IFG-0055\n\n## Decyzje dla ChatGPT\n\nBrak.\n\nTreść B",
        mtime_offset_s=1,
    )

    code = run_ifg_handoff_latest(
        root=tmp_path,
        today=dt.date(2026, 7, 9),
        copy_to_clipboard=False,
        limit=2,
    )
    assert code == 0
    handoff_file = tmp_path / "docs" / "handoff" / "HANDOFF-0001.md"
    assert handoff_file.exists()
    text = handoff_file.read_text(encoding="utf-8")
    assert text == _latest_handoff_text(tmp_path)
    assert "artifact_format_version: 1" in text
    assert "project_id: IFG" in text
    assert "generated_artifacts:" in text
    assert "## Wynik workflow" in text
    assert "IMPLEMENTED" in text
    assert "## Źródła" in text
    assert "## Następny oczekiwany krok" in text
    assert "## Raport 1:" not in text
    assert "GWO-IFG-0062" in text
    assert "GWO-IFG-0055" in text
    assert "Czy wdrożyć zmianę na produkcję?" in text
    assert "Brak." in text
    assert "Treść A" in text
    assert "Liczba znalezionych raportów: 2" in text
    assert "handoff_id: HANDOFF-0001" in text
    assert "# HANDOFF-0001" in text
    assert "# CHATGPT HANDOFF" not in text
    assert "## Co wymaga decyzji ChatGPT" in text
    assert "docs/handoff/HANDOFF-0001.md" in text
    assert "docs/handoff/latest.md" in text
    assert "END OF HANDOFF" in text
    assert text.rstrip().endswith("HANDOFF-0001")
    assert text.index("## Streszczenie") < text.index("## Co wymaga decyzji ChatGPT")
    assert text.index("## Co wymaga decyzji ChatGPT") < text.index("## Źródła")
    assert not list((tmp_path / "reports").glob("CHATGPT_HANDOFF_*")) if (tmp_path / "reports").exists() else True


def test_cli_ifg_handoff_latest_dispatch(monkeypatch):
    captured: dict[str, object] = {}

    def _fake_run_ifg_handoff_latest(*, limit: int, copy_to_clipboard: bool, include_all: bool, reset_state: bool):
        captured["limit"] = limit
        captured["copy_to_clipboard"] = copy_to_clipboard
        captured["include_all"] = include_all
        captured["reset_state"] = reset_state
        return 0

    monkeypatch.setattr(cli, "run_ifg_handoff_latest", _fake_run_ifg_handoff_latest)
    code = cli.main(["ifg", "handoff", "latest", "--limit", "3", "--no-clipboard", "--all", "--reset"])
    assert code == 0
    assert captured == {
        "limit": 3,
        "copy_to_clipboard": False,
        "include_all": True,
        "reset_state": True,
    }


def test_extract_decision_points_from_decision_section():
    content = """# Report

## Decyzje dla ChatGPT

- Opcjonalnie: dodać testy smoke
- Czy wdrożyć zmianę na produkcję?
"""
    points = extract_decision_points(content, "docs/reports/example.md")
    texts = [p.text for p in points]
    assert any("Opcjonalnie: dodać testy smoke" in t for t in texts)
    assert any("Czy wdrożyć zmianę na produkcję?" in t for t in texts)


def test_extract_decision_points_brak():
    content = """# Report

## Decyzje dla ChatGPT

Brak.
"""
    points = extract_decision_points(content, "docs/reports/example.md")
    assert [p.text for p in points] == ["Brak."]


def test_extract_decision_points_brak_stops_before_following_sections():
    content = """# Report

## Decyzje dla ChatGPT

Brak.

A. ROOT CAUSE
Nie powinno trafić do decyzji.

B. ZMIENIONE PLIKI
- app/example.py
"""
    points = extract_decision_points(content, "docs/reports/example.md")
    assert [p.text for p in points] == ["Brak."]


def test_extract_decision_points_without_section():
    content = """# Report

## Co działa

Wszystko działa poprawnie.
"""
    points = extract_decision_points(content, "docs/reports/example.md")
    assert [p.text for p in points] == ['(Raport nie zawiera sekcji "Decyzje dla ChatGPT".)']


def test_handoff_aggregate_preserves_report_order(tmp_path: Path):
    _init_journal(tmp_path)
    reports = tmp_path / "docs" / "reports"
    _write_report(
        reports / "2026-07-09_GWO-IFG-0001_A.md",
        "# GWO-IFG-0001\n\n## Decyzje dla ChatGPT\n\n- A1",
    )
    _write_report(
        reports / "2026-07-09_GWO-IFG-0002_B.md",
        "# GWO-IFG-0002\n\n## Decyzje dla ChatGPT\n\n- B1",
        mtime_offset_s=1,
    )
    run_ifg_handoff_latest(
        root=tmp_path,
        today=dt.date(2026, 7, 9),
        copy_to_clipboard=False,
        limit=2,
    )
    text = _latest_handoff_text(tmp_path)
    assert text.index("### GWO-IFG-0002") < text.index("### GWO-IFG-0001")


def test_handoff_pending_first_then_empty_then_new(tmp_path: Path):
    _init_journal(tmp_path)
    reports = tmp_path / "docs" / "reports"
    _write_report(reports / "2026-07-09_GWO-IFG-1001_A.md", "# GWO-IFG-1001\n\n## Decyzje dla ChatGPT\n\nBrak.\n")
    _write_report(
        reports / "2026-07-09_GWO-IFG-1002_B.md",
        "# GWO-IFG-1002\n\n## Decyzje dla ChatGPT\n\n- Czy wdrożyć?\n",
        mtime_offset_s=1,
    )

    code1 = run_ifg_handoff_latest(root=tmp_path, today=dt.date(2026, 7, 9), copy_to_clipboard=False)
    assert code1 == 0
    text1 = _latest_handoff_text(tmp_path)
    assert "Liczba znalezionych raportów: 1" in text1
    assert "GWO-IFG-1002" in text1
    assert "HANDOFF-0001" in text1

    code2 = run_ifg_handoff_latest(root=tmp_path, today=dt.date(2026, 7, 9), copy_to_clipboard=False)
    assert code2 == 0
    text2 = _latest_handoff_text(tmp_path)
    assert "Liczba znalezionych raportów: 1" in text2
    assert "GWO-IFG-1001" in text2
    assert "HANDOFF-0002" in text2

    code3 = run_ifg_handoff_latest(root=tmp_path, today=dt.date(2026, 7, 9), copy_to_clipboard=False)
    assert code3 == 0
    assert "HANDOFF-0002" in _latest_handoff_text(tmp_path)

    _write_report(
        reports / "2026-07-09_GWO-IFG-1003_C.md",
        "# GWO-IFG-1003\n\n## Decyzje dla ChatGPT\n\n- Czy zrobić krok C?\n",
        mtime_offset_s=1,
    )
    code4 = run_ifg_handoff_latest(root=tmp_path, today=dt.date(2026, 7, 9), copy_to_clipboard=False)
    assert code4 == 0
    text4 = _latest_handoff_text(tmp_path)
    assert "Liczba znalezionych raportów: 1" in text4
    assert "GWO-IFG-1003" in text4
    assert "HANDOFF-0003" in text4


def test_handoff_all_ignores_state(tmp_path: Path):
    _init_journal(tmp_path)
    reports = tmp_path / "docs" / "reports"
    _write_report(reports / "2026-07-09_GWO-IFG-2001_A.md", "# GWO-IFG-2001\n\n## Decyzje dla ChatGPT\n\nBrak.\n")
    _write_report(
        reports / "2026-07-09_GWO-IFG-2002_B.md",
        "# GWO-IFG-2002\n\n## Decyzje dla ChatGPT\n\nBrak.\n",
        mtime_offset_s=1,
    )
    run_ifg_handoff_latest(root=tmp_path, today=dt.date(2026, 7, 9), copy_to_clipboard=False)

    code = run_ifg_handoff_latest(
        root=tmp_path,
        today=dt.date(2026, 7, 9),
        copy_to_clipboard=False,
        include_all=True,
        limit=2,
    )
    assert code == 0
    text = _latest_handoff_text(tmp_path)
    assert "Liczba znalezionych raportów: 2" in text


def test_handoff_reset_clears_memory(tmp_path: Path):
    _init_journal(tmp_path)
    reports = tmp_path / "docs" / "reports"
    _write_report(reports / "2026-07-09_GWO-IFG-3001_A.md", "# GWO-IFG-3001\n\n## Decyzje dla ChatGPT\n\nBrak.\n")
    run_ifg_handoff_latest(root=tmp_path, today=dt.date(2026, 7, 9), copy_to_clipboard=False)
    run_ifg_handoff_latest(root=tmp_path, today=dt.date(2026, 7, 9), copy_to_clipboard=False, reset_state=True)
    text = _latest_handoff_text(tmp_path)
    assert "Liczba znalezionych raportów: 1" in text


def test_handoff_corrupted_state_file_is_treated_as_empty(tmp_path: Path):
    _init_journal(tmp_path)
    reports = tmp_path / "docs" / "reports"
    _write_report(reports / "2026-07-09_GWO-IFG-4001_A.md", "# GWO-IFG-4001\n\n## Decyzje dla ChatGPT\n\nBrak.\n")
    state_path = tmp_path / ".state" / "handoff.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("{broken json", encoding="utf-8")

    code = run_ifg_handoff_latest(root=tmp_path, today=dt.date(2026, 7, 9), copy_to_clipboard=False)
    assert code == 0
    text = _latest_handoff_text(tmp_path)
    assert "Liczba znalezionych raportów: 1" in text
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert "sent_reports" in payload


def test_handoff_latest_ignores_non_gwo_artifacts(tmp_path: Path):
    """Regression GWO-GUARDIAN-0065: repository/guardian_recover must not win over GWO task."""
    reports = tmp_path / "docs" / "reports"
    _write_report(
        reports / "repository_orphans.md",
        "# Repository Orphans\n\nCount: 0",
        mtime_offset_s=10,
    )
    _write_report(
        reports / "guardian_recover_20260707_1038.md",
        "# guardian recover",
        mtime_offset_s=9,
    )
    _write_report(
        reports / "2026-07-10_GWO-IFG-0064_RELEASE_GATE_UNBLOCK.md",
        "# GWO-IFG-0064\n\n## Decyzje dla ChatGPT\n\nBrak.\n\nRelease gate unblock.",
        mtime_offset_s=11,
    )

    selection = select_latest_reports(root=tmp_path, today=dt.date(2026, 7, 11), limit=1)
    assert len(selection.reports) == 1
    assert selection.reports[0].name == "2026-07-10_GWO-IFG-0064_RELEASE_GATE_UNBLOCK.md"


def test_handoff_latest_selects_yesterday_gwo_when_no_today_report(tmp_path: Path):
    _init_journal(tmp_path)
    reports = tmp_path / "docs" / "reports"
    _write_report(
        reports / "2026-07-10_GWO-IFG-0064_RELEASE_GATE_UNBLOCK.md",
        "# GWO-IFG-0064\n\n## Decyzje dla ChatGPT\n\nBrak.\n",
    )

    code = run_ifg_handoff_latest(root=tmp_path, today=dt.date(2026, 7, 11), copy_to_clipboard=False)
    assert code == 0
    text = _latest_handoff_text(tmp_path)
    assert "Liczba znalezionych raportów: 1" in text
    assert "GWO-IFG-0064" in text
    assert "repository_orphans" not in text
    assert "HANDOFF-0001" in text


def test_handoff_metadata_selects_non_gwo_filename(tmp_path: Path):
    """GDD-0011: ADR/RFC reports use front matter instead of filename regex."""
    reports = tmp_path / "docs" / "reports"
    _write_report(
        reports / "2026-07-10_GWO-IFG-0064_LEGACY.md",
        "# GWO-IFG-0064\n\n## Decyzje dla ChatGPT\n\nBrak.\n",
        mtime_offset_s=5,
    )
    _write_report(
        reports / "architecture-review-0066.md",
        """---
kind: review
project: IFG
workflow: GWO-GUARDIAN-0066
handoff: true
created_at: 2099-12-31T23:59:59Z
---

# Review

## Decyzje dla ChatGPT

Brak.
""",
        mtime_offset_s=10,
    )

    selection = select_latest_reports(root=tmp_path, today=dt.date(2026, 7, 11), limit=1)
    assert len(selection.reports) == 1
    assert selection.reports[0].name == "architecture-review-0066.md"


def test_handoff_metadata_handoff_false_excludes_report(tmp_path: Path):
    reports = tmp_path / "docs" / "reports"
    _write_report(
        reports / "2026-07-11_GWO-IFG-9999_HIDDEN.md",
        """---
kind: gwo
project: IFG
workflow: GWO-IFG-9999
handoff: false
created_at: 2026-07-11T23:00:00Z
---

# Hidden
""",
    )
    _write_report(
        reports / "2026-07-11_GWO-IFG-8888_VISIBLE.md",
        "# GWO-IFG-8888\n\n## Decyzje dla ChatGPT\n\nBrak.\n",
    )

    selection = select_latest_reports(root=tmp_path, today=dt.date(2026, 7, 11), limit=1)
    assert len(selection.reports) == 1
    assert selection.reports[0].name == "2026-07-11_GWO-IFG-8888_VISIBLE.md"


def test_handoff_legacy_fallback_without_metadata_still_works(tmp_path: Path):
    reports = tmp_path / "docs" / "reports"
    _write_report(
        reports / "repository_orphans.md",
        "# orphans",
        mtime_offset_s=10,
    )
    _write_report(
        reports / "2026-07-09_GWO-IFG-0055_LEGACY.md",
        "# GWO-IFG-0055\n\n## Decyzje dla ChatGPT\n\nBrak.\n",
    )

    selection = select_latest_reports(root=tmp_path, limit=1)
    assert len(selection.reports) == 1
    assert selection.reports[0].name == "2026-07-09_GWO-IFG-0055_LEGACY.md"
