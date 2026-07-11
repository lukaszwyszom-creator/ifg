from __future__ import annotations

import sys
from pathlib import Path

from ifg_guardian.config import ROOT
from ifg_guardian.core.handoff_journal.service import HandoffJournalService


def _service(root: Path | None = None) -> HandoffJournalService:
    return HandoffJournalService(root=root or ROOT)


def run_handoff_validate(*, root: Path | None = None) -> int:
    report = _service(root).validate()
    if report.valid:
        print("Handoff journal valid.")
        return 0
    print("Handoff journal integrity violations:", file=sys.stderr)
    for issue in report.issues:
        prefix = f"[{issue.handoff_id:04d}] " if issue.handoff_id is not None else ""
        print(f"  {prefix}{issue.code.value}: {issue.message}", file=sys.stderr)
    return report.exit_code


def run_handoff_rebuild_index(*, root: Path | None = None) -> int:
    service = _service(root)
    rebuilt = service.rebuild_index()
    print(
        "Rebuilt index.json: "
        f"count={rebuilt.count}, latest={rebuilt.latest_handoff_id}, next={rebuilt.next_handoff_id}"
    )
    return 0


def run_handoff_rebuild_latest(*, root: Path | None = None) -> int:
    service = _service(root)
    try:
        path = service.rebuild_latest()
    except FileNotFoundError as exc:
        print(f"rebuild-latest failed: {exc}", file=sys.stderr)
        return 1
    print(f"Rebuilt latest.md from journal ({path})")
    return 0


def run_handoff_doctor(*, root: Path | None = None) -> int:
    report = _service(root).doctor()
    if report.healthy:
        print("Handoff journal doctor: OK")
        return 0
    print("Handoff journal doctor findings:", file=sys.stderr)
    for issue in report.issues:
        prefix = f"[{issue.handoff_id:04d}] " if issue.handoff_id is not None else ""
        print(f"  {prefix}{issue.code.value}: {issue.message}", file=sys.stderr)
    if report.suggestions:
        print("\nSuggested actions:", file=sys.stderr)
        for suggestion in report.suggestions:
            print(f"  - {suggestion}", file=sys.stderr)
    return 1
