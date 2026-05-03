"""Analiza rozrachunków (należności / zobowiązania) na podstawie danych demo."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from agent.demo_data_validator import (
    _merge_contractor_lookups,
    _parse_baseline_contractor_names,
    _parse_seed_demo_april,
    _parse_seed_demo_april_contractors,
    _parse_seed_monthly_invoices,
)

_MONEY = Decimal("0.01")


@dataclass
class SettlementEntry:
    invoice_id: str
    direction: str
    contractor: str
    amount: Decimal
    due_date: date | None
    days_overdue: int
    payment_status: str


@dataclass
class SettlementReport:
    receivables: list[SettlementEntry]
    payables: list[SettlementEntry]
    overdue: list[SettlementEntry]
    totals: dict[str, Decimal]
    warnings: list[str]


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    return None


def _invoice_due_date(invoice: dict[str, Any]) -> date | None:
    due = _parse_date(invoice.get("due_date"))
    if due is not None:
        return due
    return _parse_date(invoice.get("payment_due_date"))


def _to_money(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value.quantize(_MONEY)
    if isinstance(value, int):
        return Decimal(value).quantize(_MONEY)
    if isinstance(value, float):
        return Decimal(str(value)).quantize(_MONEY)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return Decimal("0.00")
        try:
            return Decimal(text).quantize(_MONEY)
        except InvalidOperation:
            return Decimal("0.00")
    return Decimal("0.00")


def _invoice_gross_amount(invoice: dict[str, Any]) -> Decimal | None:
    for key in ("total_gross", "gross_total", "gross_amount", "amount_gross"):
        if key in invoice and invoice.get(key) not in (None, ""):
            return _to_money(invoice.get(key))
    return None


def _invoice_id(invoice: dict[str, Any], index: int) -> str:
    for key in ("seed_key", "slug", "number_local", "id", "_id"):
        value = invoice.get(key)
        if value not in (None, ""):
            return str(value)
    return f"#{index}"


def _resolve_contractor_name(invoice: dict[str, Any], lookup: dict[str, str]) -> str:
    for key in (
        "buyer_name",
        "customer_name",
        "seller_name",
        "supplier_name",
        "vendor_name",
    ):
        value = invoice.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for key in ("buyer_id", "seller_id", "contractor_id", "contractor_slug", "nip"):
        value = invoice.get(key)
        if isinstance(value, str) and value.strip():
            candidate = lookup.get(value.strip().lower())
            if candidate:
                return candidate

    return "unknown"


def _is_paid(invoice: dict[str, Any]) -> bool:
    for key in ("payment_status", "status_payment"):
        value = invoice.get(key)
        if isinstance(value, str) and value.strip().lower() == "paid":
            return True
    return False


def analyze_settlements(invoices: list[dict[str, Any]]) -> SettlementReport:
    today = date.today()
    receivables: list[SettlementEntry] = []
    payables: list[SettlementEntry] = []
    overdue: list[SettlementEntry] = []
    warnings: list[str] = []

    for index, invoice in enumerate(invoices, start=1):
        invoice_label = _invoice_id(invoice, index)
        direction = str(invoice.get("direction") or "").strip().lower()
        if direction not in {"sale", "purchase"}:
            continue

        amount = _invoice_gross_amount(invoice)
        if amount is None:
            warnings.append(
                f"invoice {invoice_label}: missing gross amount (expected one of: total_gross, gross_total, gross_amount, amount_gross)"
            )
            continue

        due = _invoice_due_date(invoice)
        if due is None:
            warnings.append(f"invoice {invoice_label}: missing due_date")

        paid = _is_paid(invoice)
        days_overdue = (today - due).days if (due is not None and due < today and not paid) else 0
        payment_status = "paid" if paid else "unpaid"

        entry = SettlementEntry(
            invoice_id=invoice_label,
            direction=direction,
            contractor=_resolve_contractor_name(invoice, {}),
            amount=amount,
            due_date=due,
            days_overdue=days_overdue,
            payment_status=payment_status,
        )

        if direction == "sale":
            receivables.append(entry)
        else:
            payables.append(entry)

        if days_overdue > 0:
            overdue.append(entry)

    totals = {
        "receivables_total": sum((item.amount for item in receivables), Decimal("0.00")).quantize(_MONEY),
        "payables_total": sum((item.amount for item in payables), Decimal("0.00")).quantize(_MONEY),
        "overdue_total": sum((item.amount for item in overdue), Decimal("0.00")).quantize(_MONEY),
    }

    overdue.sort(key=lambda item: (-item.days_overdue, -item.amount, item.invoice_id))

    return SettlementReport(
        receivables=receivables,
        payables=payables,
        overdue=overdue,
        totals=totals,
        warnings=warnings,
    )


def analyze_repo_settlements(root_dir: str = ".") -> SettlementReport:
    root = Path(root_dir)
    invoices: list[dict[str, Any]] = []

    monthly_seed = root / "scripts" / "seed_monthly_invoices.py"
    april_seed = root / "scripts" / "seed_demo_april_2026.py"
    baseline_seed = root / "tests" / "fixtures" / "baseline_seed.json"

    contractors_lookup: dict[str, str] = {}
    baseline_lookup: dict[str, str] = {}

    if monthly_seed.is_file():
        try:
            invoices.extend(_parse_seed_monthly_invoices(monthly_seed))
        except Exception:
            pass

    if april_seed.is_file():
        try:
            invoices.extend(_parse_seed_demo_april(april_seed))
            contractors_lookup = _parse_seed_demo_april_contractors(april_seed)
        except Exception:
            pass

    if baseline_seed.is_file():
        try:
            baseline_lookup = _parse_baseline_contractor_names(baseline_seed)
        except Exception:
            pass

    report = analyze_settlements(invoices)
    lookup = _merge_contractor_lookups(contractors_lookup, baseline_lookup)

    def _with_contractor(entry: SettlementEntry) -> SettlementEntry:
        source = next((inv for inv in invoices if str(inv.get("seed_key") or inv.get("slug") or inv.get("_id") or "") == entry.invoice_id), None)
        if source is None:
            return entry
        return SettlementEntry(
            invoice_id=entry.invoice_id,
            direction=entry.direction,
            contractor=_resolve_contractor_name(source, lookup),
            amount=entry.amount,
            due_date=entry.due_date,
            days_overdue=entry.days_overdue,
            payment_status=entry.payment_status,
        )

    receivables = [_with_contractor(item) for item in report.receivables]
    payables = [_with_contractor(item) for item in report.payables]
    overdue = [_with_contractor(item) for item in report.overdue]

    return SettlementReport(
        receivables=receivables,
        payables=payables,
        overdue=overdue,
        totals=report.totals,
        warnings=report.warnings,
    )
