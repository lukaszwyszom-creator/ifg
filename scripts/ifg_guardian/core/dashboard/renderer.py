from __future__ import annotations

from ifg_guardian.core.dashboard.model import (
    DashboardState,
    PhaseDisplayStatus,
    WorkflowRunStatus,
)

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def phase_icon(status: PhaseDisplayStatus) -> str:
    return {
        PhaseDisplayStatus.DONE: "✔",
        PhaseDisplayStatus.ACTIVE: "▶",
        PhaseDisplayStatus.FAILED: "✗",
        PhaseDisplayStatus.SKIPPED: "⊘",
        PhaseDisplayStatus.PENDING: "○",
    }[status]


def status_label(status: WorkflowRunStatus) -> str:
    return status.value


def render_dashboard_plain(state: DashboardState) -> str:
    """Plain-text dashboard layout (testable, no terminal library)."""
    spinner = SPINNER_FRAMES[state.spinner_frame % len(SPINNER_FRAMES)]
    lines = [
        "══════════════════════════════════════════════",
        "",
        "Guardian",
        "",
        "Workflow:",
        state.workflow_type or "—",
        "",
        "Status:",
        status_label(state.run_status),
        "",
        f"{state.progress_bar} {state.progress_percent}% {spinner}",
        "",
        "Etap:",
        state.current_phase or "—",
        "",
        "Krok:",
        f"{state.step} / {state.total}",
        "",
        "Czas:",
        state.elapsed_label,
        "",
        "ETA:",
        state.eta_label,
        "",
        "Ostatnia akcja:",
        "",
        state.last_action or "—",
        "",
        "──────────────────────────────────────────────",
        "",
        "Etapy",
        "",
    ]

    for phase in state.phases:
        lines.append(f"{phase_icon(phase.status)} {phase.label}")

    lines.extend(
        [
            "",
            "──────────────────────────────────────────────",
            "",
            "Heartbeat",
            "",
            "alive" if state.heartbeat_alive else "—",
            "30 s",
            "",
            "──────────────────────────────────────────────",
            "",
            "Ostatnie zdarzenia",
            "",
        ]
    )

    if state.events:
        for event in state.events[-20:]:
            lines.append(f"{event.timestamp} {event.message}")
    else:
        lines.append("—")

    lines.extend(["", "══════════════════════════════════════════════", ""])
    return "\n".join(lines)


def render_dashboard_rich(state: DashboardState):
    """Rich renderable for Live display (requires rich)."""
    from rich.panel import Panel
    from rich.text import Text

    spinner = SPINNER_FRAMES[state.spinner_frame % len(SPINNER_FRAMES)]
    body = Text()
    body.append("Guardian\n\n", style="bold white")

    body.append("Workflow:\n", style="bold cyan")
    body.append(f"{state.workflow_type or '—'}\n\n")

    status_style = {
        WorkflowRunStatus.RUNNING: "bold yellow",
        WorkflowRunStatus.SUCCESS: "bold green",
        WorkflowRunStatus.FAILED: "bold red",
        WorkflowRunStatus.PENDING: "dim",
    }.get(state.run_status, "white")
    body.append("Status:\n", style="bold cyan")
    body.append(f"{status_label(state.run_status)}\n\n", style=status_style)

    bar_style = "green" if state.run_status != WorkflowRunStatus.FAILED else "red"
    body.append(f"{state.progress_bar} {state.progress_percent}% ", style=bar_style)
    body.append(f"{spinner}\n\n", style="bold magenta")

    body.append("Etap:\n", style="bold cyan")
    body.append(f"{state.current_phase or '—'}\n\n")
    body.append("Krok:\n", style="bold cyan")
    body.append(f"{state.step} / {state.total}\n\n")
    body.append("Czas:\n", style="bold cyan")
    body.append(f"{state.elapsed_label}\n\n")
    body.append("ETA:\n", style="bold cyan")
    body.append(f"{state.eta_label}\n\n")
    body.append("Ostatnia akcja:\n\n", style="bold cyan")
    body.append(f"{state.last_action or '—'}\n\n")

    body.append("─" * 46 + "\n\nEtapy\n\n", style="dim")
    for phase in state.phases:
        style = {
            PhaseDisplayStatus.DONE: "green",
            PhaseDisplayStatus.ACTIVE: "yellow bold",
            PhaseDisplayStatus.FAILED: "red bold",
            PhaseDisplayStatus.SKIPPED: "dim",
            PhaseDisplayStatus.PENDING: "dim",
        }[phase.status]
        body.append(f"{phase_icon(phase.status)} {phase.label}\n", style=style)

    body.append("\n" + "─" * 46 + "\n\nHeartbeat\n\n", style="dim")
    body.append("alive\n" if state.heartbeat_alive else "—\n", style="green" if state.heartbeat_alive else "dim")
    body.append("30 s\n\n", style="dim")

    body.append("─" * 46 + "\n\nOstatnie zdarzenia\n\n", style="dim")
    if state.events:
        for event in state.events[-20:]:
            body.append(f"{event.timestamp} ", style="cyan")
            body.append(f"{event.message}\n")
    else:
        body.append("—\n", style="dim")

    return Panel(body, border_style="blue", title="Guardian Live Dashboard", padding=(1, 2))
