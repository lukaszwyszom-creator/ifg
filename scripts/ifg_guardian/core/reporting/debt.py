"""Standard sekcji Debt w raportach markdown Guardiana (GWO-GUARDIAN-STANDARD)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence


class DebtCategory(str, Enum):
    UX = "ux"
    TECHNICAL = "technical"
    ARCHITECTURE = "architecture"
    PERFORMANCE = "performance"


class DebtPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


_CATEGORY_HEADINGS: dict[DebtCategory, str] = {
    DebtCategory.UX: "## UX Debt",
    DebtCategory.TECHNICAL: "## Technical Debt",
    DebtCategory.ARCHITECTURE: "## Architecture Debt",
    DebtCategory.PERFORMANCE: "## Performance Debt",
}

_PRIORITY_ORDER: dict[DebtPriority, int] = {
    DebtPriority.HIGH: 0,
    DebtPriority.MEDIUM: 1,
    DebtPriority.LOW: 2,
}


@dataclass(frozen=True)
class DebtItem:
    """Pojedyncza obserwacja rozwojowa (nie backlog implementacyjny)."""

    category: DebtCategory
    priority: DebtPriority
    title: str
    description: str
    value: str
    deferred_reason: str = (
        "Nie wykonano w tym GWO, ponieważ wykracza poza ustalony zakres."
    )


@dataclass
class ReportDebt:
    items: list[DebtItem] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.items


ReportDebtInput = ReportDebt | Sequence[DebtItem | Mapping[str, Any]] | None
DecisionInput = Sequence[str] | str | None


def _coerce_category(raw: Any) -> DebtCategory:
    if isinstance(raw, DebtCategory):
        return raw
    text = str(raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "ux": DebtCategory.UX,
        "ux_debt": DebtCategory.UX,
        "technical": DebtCategory.TECHNICAL,
        "technical_debt": DebtCategory.TECHNICAL,
        "architecture": DebtCategory.ARCHITECTURE,
        "architecture_debt": DebtCategory.ARCHITECTURE,
        "performance": DebtCategory.PERFORMANCE,
        "performance_debt": DebtCategory.PERFORMANCE,
    }
    if text in aliases:
        return aliases[text]
    raise ValueError(f"unknown debt category: {raw!r}")


def _coerce_priority(raw: Any) -> DebtPriority:
    if isinstance(raw, DebtPriority):
        return raw
    text = str(raw or "MEDIUM").strip().upper()
    return DebtPriority(text)


def normalize_report_debt(raw: ReportDebtInput) -> ReportDebt | None:
    if raw is None:
        return None
    if isinstance(raw, ReportDebt):
        return None if raw.is_empty() else raw
    items: list[DebtItem] = []
    for entry in raw:
        if isinstance(entry, DebtItem):
            items.append(entry)
            continue
        if not isinstance(entry, Mapping):
            raise TypeError(f"unsupported debt entry type: {type(entry)!r}")
        items.append(
            DebtItem(
                category=_coerce_category(entry.get("category")),
                priority=_coerce_priority(entry.get("priority", "MEDIUM")),
                title=str(entry.get("title", "")).strip(),
                description=str(entry.get("description", "")).strip(),
                value=str(entry.get("value", "")).strip(),
                deferred_reason=str(
                    entry.get("deferred_reason")
                    or entry.get("reason")
                    or "Nie wykonano w tym GWO, ponieważ wykracza poza ustalony zakres."
                ).strip(),
            )
        )
    debt = ReportDebt(items=items)
    return None if debt.is_empty() else debt


def resolve_report_debt(
    *,
    debt: ReportDebtInput = None,
    state: object | None = None,
    transaction: object | None = None,
) -> ReportDebt | None:
    resolved = normalize_report_debt(debt)
    if resolved is not None:
        return resolved
    if state is not None:
        state_debt = getattr(state, "debt", None)
        resolved = normalize_report_debt(state_debt)
        if resolved is not None:
            return resolved
    if transaction is not None:
        for container in (
            getattr(transaction, "audit", None),
            getattr(transaction, "profile_data", None),
            getattr(transaction, "deploy_run", None),
        ):
            if isinstance(container, Mapping) and container.get("debt"):
                resolved = normalize_report_debt(container.get("debt"))
                if resolved is not None:
                    return resolved
    return None


def _render_debt_item(item: DebtItem) -> list[str]:
    lines = [
        f"#### {item.priority.value}",
        "",
        item.title,
        "",
        item.description,
        "",
    ]
    if item.value:
        lines.extend([item.value, ""])
    if item.deferred_reason:
        lines.extend([item.deferred_reason, ""])
    return lines


def append_debt_sections(lines: list[str], debt: ReportDebt | None) -> None:
    if debt is None or debt.is_empty():
        return

    by_category: dict[DebtCategory, list[DebtItem]] = {}
    for item in debt.items:
        by_category.setdefault(item.category, []).append(item)

    for category in (
        DebtCategory.UX,
        DebtCategory.TECHNICAL,
        DebtCategory.ARCHITECTURE,
        DebtCategory.PERFORMANCE,
    ):
        items = by_category.get(category)
        if not items:
            continue
        lines.extend(["", _CATEGORY_HEADINGS[category], ""])
        for item in sorted(items, key=lambda i: _PRIORITY_ORDER[i.priority]):
            lines.extend(_render_debt_item(item))


def _normalize_decisions(decisions: DecisionInput) -> list[str]:
    if decisions is None:
        return []
    if isinstance(decisions, str):
        text = decisions.strip()
        if not text:
            return []
        return [text]
    normalized: list[str] = []
    for entry in decisions:
        text = str(entry or "").strip()
        if text:
            normalized.append(text)
    return normalized


def append_decisions_section(lines: list[str], decisions: DecisionInput = None) -> None:
    normalized = _normalize_decisions(decisions)
    lines.extend(["", "## Decyzje dla ChatGPT", ""])
    if not normalized:
        lines.append("Brak.")
        return
    for item in normalized:
        lines.append(f"- {item}")


def finish_markdown(
    lines: list[str],
    *,
    debt: ReportDebtInput = None,
    decisions: DecisionInput = None,
    state: object | None = None,
    transaction: object | None = None,
) -> str:
    """Domyka raport markdown: opcjonalne sekcje Debt + trailing newline."""
    append_debt_sections(lines, resolve_report_debt(debt=debt, state=state, transaction=transaction))
    append_decisions_section(lines, decisions=decisions)
    return "\n".join(lines).rstrip() + "\n"


def example_gwo_0053_debt() -> ReportDebt:
    """Przykładowy zestaw Debt z GWO-IFG-0053 (dokumentacja standardu)."""
    return ReportDebt(
        items=[
            DebtItem(
                category=DebtCategory.UX,
                priority=DebtPriority.HIGH,
                title='Pokazywać "Dzisiaj", "Wczoraj" zamiast wyłącznie daty.',
                description="Ułatwia operatorowi szybką orientację czasową.",
                value="Szybsze rozpoznanie świeżości procesu bez czytania kalendarza.",
            ),
            DebtItem(
                category=DebtCategory.UX,
                priority=DebtPriority.MEDIUM,
                title="Dodać ikonę typu procesu (zakupy, sprzedaż, sesja).",
                description="Poprawia szybkość skanowania listy.",
                value="Mniej błędów interpretacji przy wielu równoległych procesach.",
            ),
            DebtItem(
                category=DebtCategory.TECHNICAL,
                priority=DebtPriority.HIGH,
                title="Agregować process_status po stronie backendu.",
                description="Frontend nie powinien wyliczać końcowego statusu procesu.",
                value="Jedna semantyka statusu dla UI, API i przyszłych klientów.",
            ),
            DebtItem(
                category=DebtCategory.PERFORMANCE,
                priority=DebtPriority.LOW,
                title="Grupowanie server-side zamiast frontendowego.",
                description="Przydatne dopiero przy bardzo dużej liczbie rekordów.",
                value="Mniejszy transfer danych i prostszy UI przy skali.",
            ),
        ]
    )
