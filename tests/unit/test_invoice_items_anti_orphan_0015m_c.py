"""GWO-0015M-C: final-page anti-orphan rebalance."""
from __future__ import annotations

import pytest

from app.services.invoice_items_paginator import (
    CONTINUATION_FINAL_ITEMS_HEIGHT,
    PaginatableRow,
    paginate_invoice_items,
)
from app.services.invoice_items_row_measure import measure_item_row_heights_master_px


def _fixture_items(n: int) -> list[dict]:
    items = []
    for i in range(1, n + 1):
        if i % 7 == 0:
            name = (
                f"Pozycja {i}: Kościoły Archidiecezji Częstochowskiej — "
                f"dłuższy opis towaru wymagający zawinięcia wiersza ({i})"
            )
            isbn = f"978-83-{i:07d}"
        elif i % 5 == 0:
            name = f"Pozycja {i}: Nazwa średniej długości produktu IFG"
            isbn = None
        else:
            name = f"Pozycja {i}"
            isbn = f"978-{i:010d}" if i % 3 == 0 else None
        items.append(
            {
                "lp": i,
                "name": name,
                "isbn": isbn,
                "qty": "1",
                "unit": "szt.",
                "cnet": "100,00",
                "cbru": "105,00",
                "vat": "5%",
                "vnet": "100,00",
                "kvat": "5,00",
                "vbru": "105,00",
            }
        )
    return items


def _rows_measured(n: int) -> list[PaginatableRow]:
    items = _fixture_items(n)
    heights, _ = measure_item_row_heights_master_px(items)
    return [
        PaginatableRow(lp=it["lp"], height_px=h, payload=it)
        for it, h in zip(items, heights)
    ]


def test_eight_items_single_page_unchanged() -> None:
    result = paginate_invoice_items(_rows_measured(8))
    assert result.page_count == 1
    assert [r.lp for r in result.pages[0].rows] == list(range(1, 9))


def test_nine_items_anti_orphan() -> None:
    result = paginate_invoice_items(_rows_measured(9))
    assert result.page_count == 2
    assert [r.lp for r in result.pages[0].rows] == list(range(1, 8))
    assert [r.lp for r in result.pages[1].rows] == [8, 9]
    assert sum(r.height_px for r in result.pages[1].rows) <= CONTINUATION_FINAL_ITEMS_HEIGHT


def test_ten_items_anti_orphan() -> None:
    result = paginate_invoice_items(_rows_measured(10))
    assert result.page_count == 2
    assert [r.lp for r in result.pages[0].rows] == list(range(1, 9))
    assert [r.lp for r in result.pages[1].rows] == [9, 10]


def test_eleven_items_anti_orphan() -> None:
    result = paginate_invoice_items(_rows_measured(11))
    assert result.page_count == 2
    assert [r.lp for r in result.pages[0].rows] == list(range(1, 10))
    assert [r.lp for r in result.pages[1].rows] == [10, 11]


def test_fifty_items_keeps_multi_row_final() -> None:
    result = paginate_invoice_items(_rows_measured(50))
    assert len(result.pages[-1].rows) >= 2
    flat = [r.lp for p in result.pages for r in p.rows]
    assert flat == list(range(1, 51))


def test_anti_orphan_does_not_empty_previous_page() -> None:
    """If previous page has only one row, do not steal it (would leave an empty page)."""
    # Two pages via force_multi: head one row on P1, orphan on P2 — cannot pull.
    rows = [
        PaginatableRow(1, 200),
        PaginatableRow(2, 200),  # sum 400 > FIRST_FINAL 330
    ]
    result = paginate_invoice_items(rows)
    assert result.page_count == 2
    assert [r.lp for r in result.pages[0].rows] == [1]
    assert [r.lp for r in result.pages[1].rows] == [2]
