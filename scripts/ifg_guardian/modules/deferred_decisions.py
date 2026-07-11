from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from ifg_guardian.config import ROOT
from ifg_guardian.core.deferred_decisions.service import (
    AddDecisionResult,
    DeferredDecisionService,
    ensure_registry_valid,
)
from ifg_guardian.core.deferred_decisions.store import GddIntegrityError


def _service(store_path: Path | None = None) -> DeferredDecisionService:
    return DeferredDecisionService(store_path=store_path)


def run_deferred_add(
    *,
    project: str,
    module: str,
    decision_type: str,
    priority: str,
    defer_reason: str,
    description: str,
    review_when: str,
    source: str,
    store_path: Path | None = None,
) -> int:
    try:
        response = _service(store_path).add(
            project=project,
            module=module,
            decision_type=decision_type,
            priority=priority,
            defer_reason=defer_reason,
            description=description,
            review_when=review_when,
            source=source,
        )
    except (ValueError, GddIntegrityError) as exc:
        print(f"deferred add failed: {exc}", file=sys.stderr)
        return 2

    item = response.item
    if item is None:
        print(f"deferred add failed: {response.message}", file=sys.stderr)
        return 2

    if response.result == AddDecisionResult.CREATED:
        print(f"Created {item.id}")
    elif response.result == AddDecisionResult.ALREADY_EXISTS:
        print(f"Already exists: {item.id} ({response.result.value})")
    elif response.result == AddDecisionResult.ID_CONFLICT:
        print(f"ID conflict: {response.message}", file=sys.stderr)
        return 3
    elif response.result == AddDecisionResult.DUPLICATE_DECISION:
        print(f"Duplicate decision: {response.message}", file=sys.stderr)
        return 4

    print(f"Project: {item.project}")
    print(f"Module: {item.module}")
    print(f"Type: {item.type.value}")
    print(f"Priority: {item.priority.value}")
    return 0


def run_deferred_list(
    *,
    project: str | None = None,
    status: str | None = "OPEN",
    decision_type: str | None = None,
    priority: str | None = None,
    output_format: str = "terminal",
    store_path: Path | None = None,
) -> int:
    try:
        items = _service(store_path).list_items(
            project=project,
            status=status,
            decision_type=decision_type,
            priority=priority,
        )
    except ValueError as exc:
        print(f"deferred list failed: {exc}", file=sys.stderr)
        return 2

    if output_format == "json":
        print(json.dumps([item.to_dict() for item in items], ensure_ascii=False, indent=2))
        return 0

    if not items:
        print("Brak wpisów GDD dla podanych kryteriów.")
        return 0

    for item in items:
        print(
            f"{item.id} [{item.status.value}] {item.priority.value} "
            f"{item.type.value} — {item.module}"
        )
        print(f"  {item.description}")
        print(f"  review: {item.review_when} | source: {item.source}")
    return 0


def run_deferred_show(*, item_id: str, output_format: str = "terminal", store_path: Path | None = None) -> int:
    item = _service(store_path).get(item_id)
    if item is None:
        print(f"GDD not found: {item_id}", file=sys.stderr)
        return 1
    if output_format == "json":
        print(json.dumps(item.to_dict(), ensure_ascii=False, indent=2))
        return 0
    print(_service(store_path).render_item_markdown(item))
    return 0


def run_deferred_done(*, item_id: str, store_path: Path | None = None) -> int:
    try:
        item = _service(store_path).mark_done(item_id)
    except KeyError:
        print(f"GDD not found: {item_id}", file=sys.stderr)
        return 1
    print(f"Marked {item.id} as DONE (closed_at={item.closed_at})")
    return 0


def run_deferred_cancel(*, item_id: str, store_path: Path | None = None) -> int:
    try:
        item = _service(store_path).cancel(item_id)
    except KeyError:
        print(f"GDD not found: {item_id}", file=sys.stderr)
        return 1
    print(f"Marked {item.id} as CANCELLED (closed_at={item.closed_at})")
    return 0


def run_deferred_review(
    *,
    project: str | None = None,
    report_path: Path | None = None,
    output_format: str = "terminal",
    today: date | None = None,
    store_path: Path | None = None,
) -> int:
    service = _service(store_path)
    markdown = service.render_review_markdown(project=project, today=today)
    out_path = report_path
    if out_path is None and output_format != "json":
        stamp = (today or date.today()).isoformat()
        out_path = ROOT / "docs" / "guardian" / f"GDD_REVIEW_{stamp}.md"

    if output_format == "json":
        open_items = service.list_items(project=project, status="OPEN")
        print(json.dumps([item.to_dict() for item in open_items], ensure_ascii=False, indent=2))
        return 0

    if output_format == "markdown":
        print(markdown)
        if out_path:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(markdown + "\n", encoding="utf-8")
            print(f"\nReport: {out_path.relative_to(ROOT)}")
        return 0

    open_items = service.list_items(project=project, status="OPEN")
    print(f"GDD review — otwarte wpisy: {len(open_items)}")
    for item in open_items:
        print(
            f"- {item.id} [{item.priority.value}] {item.type.value} "
            f"{item.module}: {item.description}"
        )
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(markdown + "\n", encoding="utf-8")
        try:
            rel = out_path.relative_to(ROOT)
        except ValueError:
            rel = out_path
        print(f"\nReport: {rel}")
    return 0


def run_deferred_validate(*, store_path: Path | None = None) -> int:
    report = _service(store_path).validate()
    if report.valid:
        print("GDD registry valid.")
        return 0
    print("GDD registry integrity violations:", file=sys.stderr)
    for issue in report.issues:
        prefix = f"[{issue.item_id}] " if issue.item_id else ""
        print(f"  {prefix}{issue.code.value}: {issue.message}", file=sys.stderr)
    return report.exit_code


def run_deferred_repair(*, apply: bool = False, store_path: Path | None = None) -> int:
    service = _service(store_path)
    before, repair_report = service.repair(apply=False)
    if not repair_report.actions:
        print("No repair actions proposed.")
        return 0 if before.valid else before.exit_code

    mode = "APPLY" if apply else "DRY-RUN"
    print(f"GDD repair ({mode}) — proposed actions: {len(repair_report.actions)}")
    for action in repair_report.actions:
        prefix = f"[{action.item_id}] " if action.item_id else ""
        print(f"  {prefix}{action.action}: {action.description}")

    if not apply:
        print("\nDry-run only — no changes written. Use --yes to apply.")
        return 0

    try:
        after, applied = service.repair(apply=True)
    except GddIntegrityError as exc:
        print(f"Repair failed: {exc}", file=sys.stderr)
        return 2

    print(f"\nApplied {len(applied.actions)} repair action(s).")
    if after.valid:
        print("GDD registry valid after repair.")
        return 0
    print("GDD registry still invalid after repair:", file=sys.stderr)
    for issue in after.issues:
        prefix = f"[{issue.item_id}] " if issue.item_id else ""
        print(f"  {prefix}{issue.code.value}: {issue.message}", file=sys.stderr)
    return after.exit_code
