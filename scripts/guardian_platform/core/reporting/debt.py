"""Re-export standardu Debt — kanoniczna implementacja w ifg_guardian."""

from ifg_guardian.core.reporting.debt import (  # noqa: F401
    DebtCategory,
    DebtItem,
    DebtPriority,
    ReportDebt,
    append_debt_sections,
    finish_markdown,
    resolve_report_debt,
)

__all__ = [
    "DebtCategory",
    "DebtItem",
    "DebtPriority",
    "ReportDebt",
    "append_debt_sections",
    "finish_markdown",
    "resolve_report_debt",
]
