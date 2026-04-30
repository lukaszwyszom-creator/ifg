from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from app.persistence.repositories.payment_allocation_repository import PaymentAllocationRepository


def test_list_open_invoices_with_paid_amount_returns_decimal_paid_amount() -> None:
    session = MagicMock()
    session.execute.return_value.all.return_value = [
        (
            "inv-1",
            "FV/1/04/2026",
            {"name": "Nabywca A"},
            {"name": "Sprzedawca A"},
            date(2026, 4, 1),
            {"total_gross": "456.78"},
            "partially_paid",
            "VAT",
            "sale",
            "123.45",
        )
    ]

    repo = PaymentAllocationRepository(session)
    rows = repo.list_open_invoices_with_paid_amount()

    assert len(rows) == 1
    assert rows[0].invoice_id == "inv-1"
    assert rows[0].contractor_name == "Nabywca A"
    assert rows[0].gross_total == Decimal("456.78")
    assert rows[0].paid_amount == Decimal("123.45")


def test_list_open_invoices_with_paid_amount_accepts_direction_and_month_range() -> None:
    session = MagicMock()
    session.execute.return_value.all.return_value = []

    repo = PaymentAllocationRepository(session)
    result = repo.list_open_invoices_with_paid_amount(
        direction="sale",
        month_start=date(2026, 4, 1),
        month_end=date(2026, 5, 1),
    )

    assert result == []
    assert session.execute.called
