"""Wspólny model raportów Guardiana (GWO-GUARDIAN-0077)."""
from __future__ import annotations

from dataclasses import dataclass, field

STANDARD_SECTIONS: tuple[str, ...] = (
    "## Executive Summary",
    "## Decision Matrix",
    "## Trigger Files",
    "## Local vs Remote",
    "## Impact",
    "## Build Actions",
    "## Operator Actions",
    "## Wygenerowane raporty",
    "## Wygenerowane handoffy",
)

IMPACT_COMPONENTS: tuple[str, ...] = (
    "API Image",
    "Worker Image",
    "Frontend",
    "Compose",
    "Alembic",
    "Database",
    "Scheduler",
    "Static Assets",
    "Reverse Proxy",
    "Restart Required",
)

STANDARD_BUILD_ACTIONS: tuple[str, ...] = (
    "docker build api",
    "docker build worker",
    "npm build",
    "alembic",
    "compose up",
    "health",
    "logs",
)


@dataclass
class ExecutiveSummary:
    status: str
    decision: str
    risk: str
    workflow: str
    duration_ms: int = 0
    extras: dict[str, str] = field(default_factory=dict)


@dataclass
class DecisionRow:
    component: str
    decision: str
    confidence: str
    reason: str
    trigger_files: list[str] = field(default_factory=list)
    impact: str = ""


@dataclass
class TriggerFileGroup:
    category: str
    files: list[str] = field(default_factory=list)


@dataclass
class ScopeCheckRow:
    status: str
    check_id: str
    name: str
    message: str


@dataclass
class ImpactRow:
    component: str
    decision: str
    reason: str


@dataclass
class BuildActionRow:
    action: str
    decision: str
    reason: str
    command: str = ""


@dataclass
class DetailSection:
    title: str
    lines: list[str] = field(default_factory=list)


@dataclass
class GuardianReport:
    title: str
    generated_at: str
    executive_summary: ExecutiveSummary
    decision_matrix: list[DecisionRow] = field(default_factory=list)
    trigger_files: list[TriggerFileGroup] = field(default_factory=list)
    local_checks: list[ScopeCheckRow] = field(default_factory=list)
    remote_checks: list[ScopeCheckRow] = field(default_factory=list)
    impact: list[ImpactRow] = field(default_factory=list)
    build_actions: list[BuildActionRow] = field(default_factory=list)
    operator_actions: list[str] = field(default_factory=list)
    generated_reports: list[str] = field(default_factory=list)
    generated_handoffs: list[str] = field(default_factory=list)
    detail_sections: list[DetailSection] = field(default_factory=list)

    def schema_version(self) -> str:
        return "guardian_standard_report_v1"
