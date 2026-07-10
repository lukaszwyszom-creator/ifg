from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from ifg_guardian.config import ROOT
from ifg_guardian.core.deferred_decisions.service import DeferredDecisionService


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
        item = _service(store_path).add(
            project=project,
            module=module,
            decision_type=decision_type,
            priority=priority,
            defer_reason=defer_reason,
            description=description,
            review_when=review_when,
            source=source,
        )
    except ValueError as exc:
        print(f"deferred add failed: {exc}", file=sys.stderr)
        return 2
    print(f"Created {item.id}")
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
