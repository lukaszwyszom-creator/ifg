from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.reporting.debt import (  # noqa: E402
    DebtCategory,
    DebtItem,
    DebtPriority,
    ReportDebt,
    append_debt_sections,
    example_gwo_0053_debt,
    finish_markdown,
    normalize_report_debt,
    resolve_report_debt,
)


def test_normalize_report_debt_returns_none_for_empty():
    assert normalize_report_debt(None) is None
    assert normalize_report_debt([]) is None
    assert normalize_report_debt(ReportDebt()) is None


def test_append_debt_sections_skips_empty():
    lines = ["# Report", "", "## Summary", "", "OK"]
    append_debt_sections(lines, None)
    assert "## UX Debt" not in "\n".join(lines)


def test_append_debt_sections_renders_categories_and_priorities():
    debt = ReportDebt(
        items=[
            DebtItem(
                category=DebtCategory.TECHNICAL,
                priority=DebtPriority.HIGH,
                title="Backend process_status",
                description="Frontend nie powinien agregować statusu.",
                value="Spójna semantyka dla wszystkich klientów.",
            ),
            DebtItem(
                category=DebtCategory.UX,
                priority=DebtPriority.MEDIUM,
                title="Ikony procesów",
                description="Szybsze skanowanie listy.",
                value="Mniej pomyłek operatorskich.",
            ),
        ]
    )
    lines: list[str] = ["# Test"]
    append_debt_sections(lines, debt)
    text = "\n".join(lines)
    assert "## Technical Debt" in text
    assert "## UX Debt" in text
    assert "#### HIGH" in text
    assert "Backend process_status" in text


def test_finish_markdown_appends_debt_after_content():
    debt = example_gwo_0053_debt()
    md = finish_markdown(["# GWO", "", "## E. NASTĘPNY KROK", "", "Deploy."], debt=debt)
    assert "## E. NASTĘPNY KROK" in md
    assert md.index("Deploy.") < md.index("## UX Debt")
    assert md.index("## Technical Debt") < md.index("## Decyzje dla ChatGPT")
    assert "## Decyzje dla ChatGPT" in md
    assert "Brak." in md
    assert "## Technical Debt" in md
    assert md.endswith("\n")


def test_finish_markdown_accepts_explicit_decisions():
    md = finish_markdown(
        ["# GWO", "", "## E. NASTĘPNY KROK", "", "Deploy."],
        decisions=["Czy wdrożyć zmianę na produkcję?"],
    )
    assert "## Decyzje dla ChatGPT" in md
    assert "- Czy wdrożyć zmianę na produkcję?" in md


def test_resolve_report_debt_from_state():
    class _State:
        debt = [
            {
                "category": "performance",
                "priority": "LOW",
                "title": "Server-side grouping",
                "description": "Przy dużej skali.",
                "value": "Mniejszy transfer.",
            }
        ]

    resolved = resolve_report_debt(state=_State())
    assert resolved is not None
    assert resolved.items[0].category == DebtCategory.PERFORMANCE
