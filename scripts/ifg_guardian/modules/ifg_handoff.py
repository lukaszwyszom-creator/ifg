from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ifg_guardian.config import ROOT
from ifg_guardian.core.clipboard import copy_text_to_clipboard
from ifg_guardian.core.handoff_journal.models import (
    HANDOFF_GENERATOR_GUARDIAN,
    HandoffMetadata,
    HandoffStatus,
)
from ifg_guardian.core.handoff_journal.service import (
    HandoffJournalService,
    PublishStep,
    infer_workflow_type,
    utc_now_iso,
)
from ifg_guardian.core.report_metadata import (
    ReportMetadata,
    metadata_created_on,
    parse_report_metadata,
    read_report_metadata,
    report_sort_epoch,
)

GWO_PATTERN = re.compile(r"(GWO[-_][A-Z]+[-_]\d+[A-Z]?)", re.IGNORECASE)
# Legacy handoff candidates: dated IFG task reports only (not Guardian ops dumps).
GWO_TASK_REPORT_NAME = re.compile(
    r"^\d{4}-\d{2}-\d{2}_GWO[-_]IFG([-_].+)?\.md$",
    re.IGNORECASE,
)
DECISION_SECTION = '## Decyzje dla ChatGPT'
HANDOFF_STATE_FILE = Path(".state") / "handoff.json"


class HandoffSelectionError(Exception):
    """Ambiguous or invalid handoff report selection."""


@dataclass(frozen=True)
class HandoffSelection:
    reports: list[Path]
    preferred_today: bool
    conflict: str | None = None


@dataclass(frozen=True)
class DecisionPoint:
    source: str
    text: str


def _today_stamp(today: date | None = None) -> str:
    return (today or date.today()).strftime("%Y-%m-%d")


def _extract_gwo_tokens(text: str) -> set[str]:
    found = set()
    for token in GWO_PATTERN.findall(text):
        normalized = token.upper().replace("_", "-")
        found.add(normalized)
    return found


def _is_legacy_gwo_task_report(path: Path) -> bool:
    """Fallback for reports without YAML front matter."""
    return bool(GWO_TASK_REPORT_NAME.match(path.name))


def _is_handoff_candidate(path: Path, *, content: str | None = None) -> tuple[bool, ReportMetadata | None]:
    try:
        body = content if content is not None else path.read_text(encoding="utf-8")
    except OSError:
        return False, None
    metadata = parse_report_metadata(body)
    if metadata is not None:
        return metadata.handoff, metadata
    return _is_legacy_gwo_task_report(path), None


def _discover_report_candidates(root: Path) -> list[tuple[Path, float]]:
    """Return handoff-eligible reports sorted newest-first by created_at/mtime."""
    docs_reports = root / "docs" / "reports"
    if not docs_reports.exists():
        return []
    candidates: list[tuple[Path, float]] = []
    for path in docs_reports.glob("*.md"):
        if not path.is_file():
            continue
        eligible, metadata = _is_handoff_candidate(path)
        if not eligible:
            continue
        candidates.append((path, report_sort_epoch(path, metadata=metadata)))
    candidates.sort(key=lambda item: (item[1], item[0].name), reverse=True)
    return candidates


def _filename_date_prefix(path: Path) -> str | None:
    match = re.match(r"^(\d{4}-\d{2}-\d{2})_", path.name)
    return match.group(1) if match else None


def _resolve_explicit_report(root: Path, report: str | Path) -> Path:
    raw = Path(report)
    path = raw if raw.is_absolute() else (root / raw)
    if not path.is_file():
        raise HandoffSelectionError(f"Explicit report not found: {report}")
    eligible, _metadata = _is_handoff_candidate(path)
    if not eligible:
        raise HandoffSelectionError(
            f"Explicit report is not a handoff candidate: {report}"
        )
    return path.resolve()


def _state_path(root: Path) -> Path:
    return root / HANDOFF_STATE_FILE


def _load_handoff_state(root: Path) -> dict[str, list[str]]:
    path = _state_path(root)
    if not path.exists():
        return {"sent_reports": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"sent_reports": []}
    sent = payload.get("sent_reports")
    if not isinstance(sent, list):
        return {"sent_reports": []}
    normalized = [str(item) for item in sent if isinstance(item, str)]
    return {"sent_reports": normalized}


def _save_handoff_state(root: Path, sent_reports: list[str]) -> None:
    path = _state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"sent_reports": sent_reports}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _clear_handoff_state(root: Path) -> None:
    path = _state_path(root)
    if path.exists():
        path.unlink()


def _normalize_line(line: str) -> str:
    return " ".join(line.split())


def _extract_named_section(content: str, heading: str) -> tuple[bool, list[str]]:
    lines = content.splitlines()
    snippets: list[str] = []
    found = False
    capture = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if capture:
                break
            capture = stripped.lower() == heading.lower()
            found = found or capture
            continue
        if not capture:
            continue
        if not stripped:
            continue
        if re.match(r"^[A-Z]\.\s+", stripped):
            break
        if stripped.startswith("- ") or stripped.startswith("* "):
            snippets.append(_normalize_line(stripped[2:].strip()))
        else:
            snippets.append(_normalize_line(stripped))
    return found, snippets


def _derive_report_label(path: Path, content: str, metadata: ReportMetadata | None = None) -> str:
    meta = metadata if metadata is not None else parse_report_metadata(content)
    if meta is not None and meta.workflow:
        return meta.workflow
    tokens = sorted(_extract_gwo_tokens(path.name) | _extract_gwo_tokens(content))
    if tokens:
        return tokens[0]
    return path.name


def extract_decision_points(content: str, source: str) -> list[DecisionPoint]:
    found, snippets = _extract_named_section(content, DECISION_SECTION)
    if not found:
        return [
            DecisionPoint(
                source=source,
                text='(Raport nie zawiera sekcji "Decyzje dla ChatGPT".)',
            )
        ]
    if not snippets:
        return [DecisionPoint(source=source, text="Brak.")]
    if len(snippets) >= 1 and snippets[0].lower().strip(".") == "brak":
        return [DecisionPoint(source=source, text="Brak.")]

    points: list[DecisionPoint] = []
    for snippet in snippets:
        if not snippet:
            continue
        points.append(DecisionPoint(source=source, text=snippet))
    return points


def select_latest_reports(
    *,
    root: Path = ROOT,
    today: date | None = None,
    limit: int = 1,
    include_all: bool = False,
    explicit_report: str | Path | None = None,
) -> HandoffSelection:
    """Return the newest handoff-eligible report(s) deterministically.

    Selection order:
    1. Explicit ``--report`` / workflow artifact (if provided)
    2. Newest eligible report in ``docs/reports`` (created_at, else mtime)
    3. Never fall back to an older unsent report when a newer one was already sent

    Primary eligibility uses YAML front matter (``handoff: true``).
    Legacy fallback: ``YYYY-MM-DD_GWO-IFG*.md`` only (Guardian ops dumps excluded).
    """
    root = root.resolve()
    if explicit_report is not None:
        path = _resolve_explicit_report(root, explicit_report)
        try:
            rel = str(path.relative_to(root))
        except ValueError:
            rel = str(path)
        if not include_all:
            sent = set(_load_handoff_state(root).get("sent_reports", []))
            if rel in sent:
                return HandoffSelection(reports=[], preferred_today=False)
        stamp = _today_stamp(today)
        today_date = today or date.today()
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise HandoffSelectionError(f"Cannot read explicit report: {exc}") from exc
        metadata = parse_report_metadata(content)
        preferred_today = (
            metadata_created_on(metadata.created_at, today=today_date)
            if metadata is not None
            else path.name.startswith(stamp)
        )
        return HandoffSelection(reports=[path], preferred_today=preferred_today)

    ranked = _discover_report_candidates(root)
    if not ranked:
        return HandoffSelection(reports=[], preferred_today=False)

    newest_path, newest_epoch = ranked[0]
    if len(ranked) > 1 and ranked[1][1] == newest_epoch:
        twin = ranked[1][0]
        return HandoffSelection(
            reports=[],
            preferred_today=False,
            conflict=(
                "Ambiguous newest report epoch: "
                f"{newest_path.name} and {twin.name} share sort key {newest_epoch}"
            ),
        )

    if not include_all:
        sent = set(_load_handoff_state(root).get("sent_reports", []))
        newest_rel = str(newest_path.relative_to(root))
        if newest_rel in sent:
            # Do not fall back to older unsent reports — that caused historical
            # handoffs to pick 2026-07-11 after 2026-07-20 reports were marked sent.
            return HandoffSelection(reports=[], preferred_today=False)
        pool = [(p, epoch) for p, epoch in ranked if str(p.relative_to(root)) not in sent]
    else:
        pool = ranked

    if not pool:
        return HandoffSelection(reports=[], preferred_today=False)

    limit_n = max(1, limit)
    selected_pairs = pool[:limit_n]
    if limit_n >= 2 and len(pool) >= 2 and pool[0][1] == pool[1][1]:
        return HandoffSelection(
            reports=[],
            preferred_today=False,
            conflict=(
                "Ambiguous report selection: "
                f"{pool[0][0].name} and {pool[1][0].name} share sort key {pool[0][1]}"
            ),
        )

    selected = [path for path, _epoch in selected_pairs]
    stamp = _today_stamp(today)
    today_date = today or date.today()
    preferred_today = False
    first = selected[0]
    try:
        content = first.read_text(encoding="utf-8")
    except OSError:
        content = ""
    metadata = parse_report_metadata(content)
    if metadata is not None:
        preferred_today = metadata_created_on(metadata.created_at, today=today_date)
    else:
        preferred_today = first.name.startswith(stamp) or _filename_date_prefix(first) == stamp
    return HandoffSelection(reports=selected, preferred_today=preferred_today)


def _describe_source_report(content: str, decision_points: list[DecisionPoint]) -> str:
    normalized = [p.text.lower().strip().strip(".") for p in decision_points]
    if normalized and normalized != ["brak"]:
        if any("czy " in text or "wymaga" in text or "decyzj" in text for text in normalized):
            return "Raport zawiera decyzję wymagającą oceny ChatGPT."
        return "Przeanalizowano raport; zidentyfikowano punkty wymagające uwagi operatora."

    lower = content.lower()
    if any(token in lower for token in ("wdroż", "deploy", "production deploy")):
        if any(token in lower for token in ("sukces", "success", "zakończon", "implemented")):
            return "Wdrożenie zakończone sukcesem; brak kroków operatorskich wynikających z raportu."
    if "brak decyzji" in lower:
        return "Przeanalizowano; raport nie zawiera decyzji wymagających eskalacji."
    if normalized == ["brak"] or (
        len(normalized) == 1
        and "(raport nie zawiera sekcji" in normalized[0]
    ):
        return "Przeanalizowano; raport nie zawiera decyzji wymagających eskalacji."
    return "Przeanalizowano raport źródłowy; istotne ustalenia przeniesiono do sekcji streszczenia i decyzji."


def _extract_next_step(content: str) -> str | None:
    headings = (
        "## Następny oczekiwany krok",
        "## Następny krok",
        "E. Następny krok",
    )
    for heading in headings:
        found, snippets = _extract_named_section(content, heading)
        if found and snippets:
            return "\n".join(snippets).strip()
    return None


def _resolve_next_step(chosen: list[Path], root: Path) -> str:
    for path in chosen:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        step = _extract_next_step(content)
        if step and step.lower().strip(".") != "brak":
            return step
    return "Brak."


def _render_handoff_body(
    *,
    selection: HandoffSelection,
    root: Path = ROOT,
) -> str:
    chosen = selection.reports
    if not chosen:
        return ""

    lines: list[str] = []
    rel_paths = [str(p.relative_to(root)) for p in chosen]
    gwo_tokens: set[str] = set()
    decision_groups: list[tuple[str, list[DecisionPoint]]] = []
    for path in chosen:
        try:
            content = path.read_text(encoding="utf-8")
            metadata = parse_report_metadata(content)
            if metadata is not None and metadata.workflow:
                gwo_tokens.add(metadata.workflow.upper().replace("_", "-"))
            gwo_tokens.update(_extract_gwo_tokens(content))
            gwo_tokens.update(_extract_gwo_tokens(path.name))
            source_rel = str(path.relative_to(root))
            decision_groups.append(
                (_derive_report_label(path, content, metadata), extract_decision_points(content, source_rel))
            )
        except OSError:
            continue

    lines.append("## Streszczenie")
    lines.append("")
    lines.append(f"- Liczba znalezionych raportów: {len(chosen)}")
    if gwo_tokens:
        lines.append(f"- Zakres GWO: {', '.join(sorted(gwo_tokens))}")
    else:
        lines.append("- Zakres GWO: brak jawnych identyfikatorów GWO")
    lines.append(f"- Preferencja raportów z dzisiaj: {'TAK' if selection.preferred_today else 'NIE'}")
    lines.append("- Scalono pliki:")
    for rel in rel_paths:
        lines.append(f"  - `{rel}`")
    lines.append("")
    lines.append("## Co wymaga decyzji ChatGPT")
    lines.append("")
    all_have_explicit_brak = bool(decision_groups) and all(
        len(points) == 1 and points[0].text.lower().strip(".") == "brak"
        for _, points in decision_groups
    )
    if all_have_explicit_brak:
        lines.append("Brak decyzji wymagających oceny ChatGPT.")
    elif decision_groups:
        for label, points in decision_groups:
            lines.append(f"### {label}")
            lines.append("")
            for point in points:
                lines.append(f"- {point.text} _(źródło: `{point.source}`)_")
            lines.append("")
    else:
        lines.append("Brak jawnych punktów decyzyjnych w scalonych raportach.")
    lines.append("")
    lines.append("## Źródła")
    lines.append("")
    for report_path in chosen:
        rel = str(report_path.relative_to(root))
        try:
            content = report_path.read_text(encoding="utf-8")
        except OSError:
            content = ""
        points = extract_decision_points(content, rel)
        lines.append(f"### {rel}")
        lines.append("")
        lines.append(_describe_source_report(content, points))
        lines.append("")
    lines.append("## Następny oczekiwany krok")
    lines.append("")
    lines.append(_resolve_next_step(chosen, root))
    lines.append("")

    return "\n".join(lines).strip()


def _build_handoff_metadata(
    *,
    selection: HandoffSelection,
    root: Path,
    parent_handoff: str | None = None,
) -> HandoffMetadata:
    chosen = selection.reports
    rel_paths = [str(p.relative_to(root)) for p in chosen]
    # GDD-0017: workflow identity = front matter → filename → body (last resort).
    # Never let body mentions of older GWO IDs override an explicit front-matter workflow.
    front_matter_workflows: set[str] = set()
    filename_tokens: set[str] = set()
    body_tokens: set[str] = set()
    project_id = "IFG"
    for path in chosen:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        metadata = parse_report_metadata(content)
        if metadata is not None:
            if metadata.workflow:
                front_matter_workflows.add(metadata.workflow.upper().replace("_", "-"))
            if metadata.project:
                project_id = metadata.project
        filename_tokens.update(_extract_gwo_tokens(path.name))
        body_tokens.update(_extract_gwo_tokens(content))

    if len(front_matter_workflows) == 1:
        workflow = next(iter(front_matter_workflows))
    elif len(front_matter_workflows) > 1:
        workflow = sorted(front_matter_workflows)[0]
    elif len(filename_tokens) == 1:
        workflow = next(iter(filename_tokens))
    elif filename_tokens:
        workflow = sorted(filename_tokens)[0]
    elif body_tokens:
        workflow = sorted(body_tokens)[0]
    else:
        workflow = "IFG-HANDOFF"
    return HandoffMetadata(
        handoff_id=0,
        previous_handoff=None,
        parent_handoff=parent_handoff,
        project_id=project_id,
        workflow=workflow,
        workflow_type=infer_workflow_type(workflow),
        status=HandoffStatus.SUCCESS,
        created_at=utc_now_iso(),
        source_reports=rel_paths,
        generated_artifacts=[],
        handoff_generator=HANDOFF_GENERATOR_GUARDIAN,
    )


def _print_handoff_failure(*, failed_step: PublishStep, message: str) -> None:
    print("✗ Handoff workflow FAILED", file=sys.stderr)
    print(f"  Etap: {failed_step.value}", file=sys.stderr)
    print(f"  Powód: {message}", file=sys.stderr)


def _print_handoff_summary(
    *,
    merged_count: int,
    copy_to_clipboard: bool,
    content: str,
    journal_path: Path | None = None,
    clipboard_done: bool = False,
) -> None:
    print("✓ Handoff wygenerowany")
    if journal_path is not None:
        print(f"  Journal: {journal_path}")
        print("  Latest: docs/handoff/latest.md")
    print(f"  Scalono raportów: {merged_count}")

    if not copy_to_clipboard:
        print("ℹ Kopiowanie do schowka wyłączone (--no-clipboard)")
        return

    if clipboard_done:
        print("✓ Skopiowano do schowka")
        print("✓ Gotowy do wklejenia do ChatGPT")
        return

    try:
        copied, reason = copy_text_to_clipboard(content)
    except OSError as exc:
        copied, reason = False, str(exc)

    if copied:
        print("✓ Skopiowano do schowka")
        print("✓ Gotowy do wklejenia do ChatGPT")
        return

    print("⚠ Nie udało się skopiować do schowka")
    print(f"Powód: {reason or 'nieznany błąd'}")


def run_ifg_handoff_latest(
    *,
    limit: int = 1,
    copy_to_clipboard: bool = True,
    include_all: bool = False,
    reset_state: bool = False,
    root: Path = ROOT,
    today: date | None = None,
    parent_handoff: str | None = None,
    explicit_report: str | Path | None = None,
) -> int:
    if reset_state:
        _clear_handoff_state(root)

    try:
        selection = select_latest_reports(
            root=root,
            today=today,
            limit=limit,
            include_all=include_all,
            explicit_report=explicit_report,
        )
    except HandoffSelectionError as exc:
        print(f"STATUS: FAILURE")
        print(f"VERDICT: HANDOFF_SELECTION_FAILED")
        print(f"Reason: {exc}")
        return 1

    if selection.conflict:
        print("STATUS: FAILURE")
        print("VERDICT: HANDOFF_REPORT_CONFLICT")
        print(f"Conflict: {selection.conflict}")
        print("Handoff journal bez zmian — nie wybrano przypadkowego raportu.")
        return 1

    if not selection.reports:
        print("Brak nowych raportów do przekazania — handoff journal bez zmian.")
        return 0

    journal = HandoffJournalService(root=root)
    metadata = _build_handoff_metadata(
        selection=selection,
        root=root,
        parent_handoff=parent_handoff,
    )
    body = _render_handoff_body(selection=selection, root=root)

    publish = journal.publish(
        metadata=metadata,
        body=body,
        report_saved=True,
        copy_to_clipboard=copy_to_clipboard,
    )
    if not publish.ok:
        _print_handoff_failure(
            failed_step=publish.failed_step or PublishStep.JOURNAL_VALIDATED,
            message=publish.message,
        )
        return publish.exit_code

    if not include_all:
        state = _load_handoff_state(root)
        sent = list(state.get("sent_reports", []))
        sent_set = set(sent)
        for report in selection.reports:
            rel = str(report.relative_to(root))
            if rel not in sent_set:
                sent.append(rel)
                sent_set.add(rel)
        _save_handoff_state(root, sent)

    rel_journal = publish.handoff_path.relative_to(root) if publish.handoff_path else None
    published_document = publish.handoff_path.read_text(encoding="utf-8") if publish.handoff_path else ""
    _print_handoff_summary(
        merged_count=len(selection.reports),
        copy_to_clipboard=copy_to_clipboard,
        content=published_document,
        journal_path=rel_journal,
        clipboard_done=copy_to_clipboard and PublishStep.CLIPBOARD_UPDATED in publish.completed_steps,
    )

    return 0
