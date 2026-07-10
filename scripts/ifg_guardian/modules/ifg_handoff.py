from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ifg_guardian.config import ROOT

GWO_PATTERN = re.compile(r"(GWO[-_][A-Z]+[-_]\d+[A-Z]?)", re.IGNORECASE)
DECISION_SECTION = '## Decyzje dla ChatGPT'
HANDOFF_STATE_FILE = Path(".state") / "handoff.json"


@dataclass(frozen=True)
class HandoffSelection:
    reports: list[Path]
    preferred_today: bool


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


def _discover_report_candidates(root: Path) -> list[Path]:
    docs_reports = root / "docs" / "reports"
    if docs_reports.exists():
        return sorted(
            [p for p in docs_reports.glob("*.md") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    return []


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


def _derive_report_label(path: Path, content: str) -> str:
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
    limit: int = 10,
    include_all: bool = False,
) -> HandoffSelection:
    candidates = _discover_report_candidates(root)
    if not candidates:
        return HandoffSelection(reports=[], preferred_today=False)

    if not include_all:
        state = _load_handoff_state(root)
        sent = set(state.get("sent_reports", []))
        candidates = [p for p in candidates if str(p.relative_to(root)) not in sent]
        if not candidates:
            return HandoffSelection(reports=[], preferred_today=False)

    stamp = _today_stamp(today)
    todays = [p for p in candidates if p.name.startswith(stamp)]
    if todays:
        return HandoffSelection(reports=todays[:limit], preferred_today=True)
    return HandoffSelection(reports=candidates[:limit], preferred_today=False)


def _render_handoff_markdown(
    *,
    selection: HandoffSelection,
    output_path: Path,
    root: Path = ROOT,
    today: date | None = None,
) -> str:
    stamp = _today_stamp(today)
    chosen = selection.reports
    if not chosen:
        return "# CHATGPT HANDOFF\n\nBrak nowych raportów do przekazania.\n"

    lines: list[str] = []
    rel_paths = [str(p.relative_to(root)) for p in chosen]
    gwo_tokens: set[str] = set()
    decision_groups: list[tuple[str, list[DecisionPoint]]] = []
    for path in chosen:
        try:
            content = path.read_text(encoding="utf-8")
            gwo_tokens.update(_extract_gwo_tokens(content))
            gwo_tokens.update(_extract_gwo_tokens(path.name))
            source_rel = str(path.relative_to(root))
            decision_groups.append(
                (_derive_report_label(path, content), extract_decision_points(content, source_rel))
            )
        except OSError:
            continue

    lines.append(f"# CHATGPT HANDOFF {stamp}")
    lines.append("")
    lines.append("## Streszczenie")
    lines.append("")
    lines.append(f"- Liczba znalezionych raportów: {len(chosen)}")
    if gwo_tokens:
        lines.append(f"- Zakres GWO: {', '.join(sorted(gwo_tokens))}")
    else:
        lines.append("- Zakres GWO: brak jawnych identyfikatorów GWO")
    lines.append(f"- Preferencja raportów z dzisiaj: {'TAK' if selection.preferred_today else 'NIE'}")
    lines.append("- Scalono pliki:")
    if rel_paths:
        for rel in rel_paths:
            lines.append(f"  - `{rel}`")
    else:
        lines.append("  - brak plików do scalenia")
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

    for idx, report_path in enumerate(chosen, start=1):
        rel = report_path.relative_to(root)
        lines.append(f"## Raport {idx}: `{rel}`")
        lines.append("")
        lines.append(report_path.read_text(encoding="utf-8").rstrip())
        lines.append("")

    lines.append("## Wygenerowane raporty")
    lines.append("")
    lines.append(f"- `{output_path}`")
    for rel in rel_paths:
        lines.append(f"- `{rel}`")
    lines.append("")
    return "\n".join(lines)


def _copy_to_clipboard_if_possible(content: str) -> bool:
    if platform.system() != "Darwin":
        return False
    if shutil.which("pbcopy") is None:
        return False
    subprocess.run(["pbcopy"], input=content, text=True, check=True)
    return True


def run_ifg_handoff_latest(
    *,
    limit: int = 10,
    copy_to_clipboard: bool = True,
    include_all: bool = False,
    reset_state: bool = False,
    root: Path = ROOT,
    today: date | None = None,
) -> int:
    if reset_state:
        _clear_handoff_state(root)

    selection = select_latest_reports(
        root=root,
        today=today,
        limit=limit,
        include_all=include_all,
    )
    stamp = _today_stamp(today)
    out_dir = root / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"CHATGPT_HANDOFF_{stamp}.md"

    content = _render_handoff_markdown(
        selection=selection,
        output_path=output_path,
        root=root,
        today=today,
    )
    output_path.write_text(content, encoding="utf-8")

    # Mark reports as sent only after successful handoff generation.
    if selection.reports and not include_all:
        state = _load_handoff_state(root)
        sent = list(state.get("sent_reports", []))
        sent_set = set(sent)
        for report in selection.reports:
            rel = str(report.relative_to(root))
            if rel not in sent_set:
                sent.append(rel)
                sent_set.add(rel)
        _save_handoff_state(root, sent)

    print(f"Handoff report: {output_path.relative_to(root)}")
    print(f"Merged reports: {len(selection.reports)}")
    if copy_to_clipboard:
        try:
            copied = _copy_to_clipboard_if_possible(content)
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"Clipboard copy skipped: {exc}")
            copied = False
        if copied:
            print("Clipboard: copied via pbcopy")
        else:
            print("Clipboard: not available on this environment")

    return 0
