from __future__ import annotations

from ifg_guardian.core.progress.timeline import ProgressTimeline


def render_timeline_section(timeline: ProgressTimeline | dict | None) -> list[str]:
    if timeline is None:
        return []

    if isinstance(timeline, dict):
        entries = timeline.get("entries", [])
    else:
        entries = [e.to_dict() for e in timeline.entries]

    if not entries:
        return []

    lines = ["", "## Timeline wykonania", ""]
    lines.append("| # | Faza | Status | Start | Koniec | Czas | Opis |")
    lines.append("|---|------|--------|-------|--------|------|------|")
    for idx, entry in enumerate(entries, start=1):
        started = entry.get("started_at") or "—"
        ended = entry.get("ended_at") or "—"
        duration_ms = entry.get("duration_ms", 0)
        duration = f"{duration_ms}ms" if duration_ms else "—"
        lines.append(
            f"| {idx} | `{entry.get('phase', '')}` | {entry.get('status', '')} | "
            f"{started} | {ended} | {duration} | {entry.get('message', '')} |"
        )
    lines.append("")
    return lines
