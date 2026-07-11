from __future__ import annotations

import sys
from pathlib import Path

from ifg_guardian.config import ROOT
from ifg_guardian.core.handoff_journal.models import format_handoff_id
from ifg_guardian.core.handoff_journal.store import HandoffJournalRebuildError
from ifg_guardian.core.handoff_journal.service import HandoffJournalService


def _service(root: Path | None = None) -> HandoffJournalService:
    return HandoffJournalService(root=root or ROOT)


def run_handoff_validate(*, root: Path | None = None) -> int:
    report = _service(root).validate()
    if report.legacy_notices:
        print(f"Legacy format notices: {len(report.legacy_notices)}")
        for issue in report.legacy_notices:
            prefix = f"[{format_handoff_id(issue.handoff_id)}] " if issue.handoff_id is not None else ""
            print(f"  {prefix}{issue.code.value}: {issue.message}")
    if report.valid:
        print("Handoff journal valid.")
        return 0
    print("Handoff journal integrity violations:", file=sys.stderr)
    for issue in report.issues:
        prefix = f"[{format_handoff_id(issue.handoff_id)}] " if issue.handoff_id is not None else ""
        print(f"  {prefix}{issue.code.value}: {issue.message}", file=sys.stderr)
    return report.exit_code


def run_handoff_rebuild_index(*, root: Path | None = None) -> int:
    service = _service(root)
    try:
        rebuilt = service.rebuild_index()
    except HandoffJournalRebuildError as exc:
        print("rebuild-index failed:", file=sys.stderr)
        for issue in exc.issues:
            prefix = f"[{format_handoff_id(issue.handoff_id)}] " if issue.handoff_id is not None else ""
            print(f"  {prefix}{issue.code.value}: {issue.message}", file=sys.stderr)
        return 1
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
    if report.summary is not None:
        summary = report.summary
        print(
            "Handoff journal doctor summary: "
            f"count={summary.count}, latest={summary.latest_handoff_id}, "
            f"next={format_handoff_id(summary.next_handoff_id) if summary.next_handoff_id else summary.next_handoff_id}, "
            f"latest_status={summary.latest_status}, clipboard={summary.clipboard_status}"
        )
        if summary.gaps:
            print(f"  Gaps: {', '.join(format_handoff_id(g) for g in summary.gaps)}")
    if report.legacy_notices:
        print(f"Legacy format notices: {len(report.legacy_notices)}")
        for issue in report.legacy_notices:
            prefix = f"[{format_handoff_id(issue.handoff_id)}] " if issue.handoff_id is not None else ""
            print(f"  {prefix}{issue.code.value}: {issue.message}")
    if report.healthy:
        print("Handoff journal doctor: OK")
        return 0
    print("Handoff journal doctor findings:", file=sys.stderr)
    for issue in report.issues:
        prefix = f"[{format_handoff_id(issue.handoff_id)}] " if issue.handoff_id is not None else ""
        print(f"  {prefix}{issue.code.value}: {issue.message}", file=sys.stderr)
    if report.suggestions:
        print("\nSuggested actions:", file=sys.stderr)
        for suggestion in report.suggestions:
            print(f"  - {suggestion}", file=sys.stderr)
    return 1
