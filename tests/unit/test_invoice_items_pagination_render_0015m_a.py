"""GWO-0015M-A: pagination ↔ render consistency (measured heights)."""
from __future__ import annotations

import pytest

from app.services.invoice_items_paginator import (
    FINAL_PAGE_ITEMS_HEIGHT,
    NORMAL_PAGE_ITEMS_HEIGHT,
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


@pytest.mark.parametrize("n", [1, 7, 8, 9, 10, 11, 50])
def test_measured_paginate_preserves_all_lps(n: int) -> None:
    rows = _rows_measured(n)
    result = paginate_invoice_items(rows)
    flat = [r.lp for p in result.pages for r in p.rows]
    assert flat == list(range(1, n + 1))
    assert sum(p.show_summary for p in result.pages) == 1
    for p in result.pages:
        assert sum(r.height_px for r in p.rows) <= p.items_budget_px + 1e-6


def test_barely_over_final_fills_first_page_efficiently() -> None:
    """Regression: do not leave a near-empty page 1 when total ≈ FINAL+ε."""
    # 15 × 22 = 330 exactly fits final; 16 × 22 = 352 needs 2 pages
    h = 22.0
    n = int(FINAL_PAGE_ITEMS_HEIGHT // h) + 1
    rows = [PaginatableRow(lp=i, height_px=h) for i in range(1, n + 1)]
    result = paginate_invoice_items(rows)
    assert result.page_count == 2
    # First page should take most rows (NORMAL), not a single leftover head
    assert len(result.pages[0].rows) >= n - 2
    assert len(result.pages[1].rows) >= 1
    assert not result.pages[0].show_summary
    assert result.pages[1].show_summary


def test_measure_heights_positive_and_stable() -> None:
    items = _fixture_items(3)
    h1, th1 = measure_item_row_heights_master_px(items)
    h2, th2 = measure_item_row_heights_master_px(items)
    assert h1 == h2
    assert th1 == th2
    assert all(h > 10 for h in h1)
    assert th1 > 10
