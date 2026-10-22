"""GWO-0015M-B: continuation page budgets and packing."""
from __future__ import annotations

import pytest

from app.services.invoice_items_paginator import (
    CONTINUATION_FINAL_ITEMS_HEIGHT,
    CONTINUATION_NORMAL_ITEMS_HEIGHT,
    FIRST_FINAL_ITEMS_HEIGHT,
    FIRST_NORMAL_ITEMS_HEIGHT,
    TABLE_TOP_CONTINUATION,
    TABLE_TOP_FIRST,
    PageKind,
    PaginatableRow,
    paginate_invoice_items,
)
from app.services.invoice_items_row_measure import measure_item_row_heights_master_px


def test_continuation_geometry_budgets() -> None:
    assert TABLE_TOP_CONTINUATION < TABLE_TOP_FIRST
    assert TABLE_TOP_FIRST == 780
    assert TABLE_TOP_CONTINUATION == 124
    assert FIRST_NORMAL_ITEMS_HEIGHT == 577.0
    assert FIRST_FINAL_ITEMS_HEIGHT == 330.0
    assert CONTINUATION_NORMAL_ITEMS_HEIGHT == 1233.0
    assert CONTINUATION_FINAL_ITEMS_HEIGHT == 986.0
    assert CONTINUATION_NORMAL_ITEMS_HEIGHT > CONTINUATION_FINAL_ITEMS_HEIGHT


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


@pytest.mark.parametrize("n", [1, 8, 9, 10, 11, 50])
def test_continuation_paginate_invariants(n: int) -> None:
    rows = _rows_measured(n)
    result = paginate_invoice_items(rows)
    flat = [r.lp for p in result.pages for r in p.rows]
    assert flat == list(range(1, n + 1))
    assert sum(p.show_summary for p in result.pages) == 1
    assert sum(p.show_payable for p in result.pages) == 1
    assert sum(p.show_ksef_qr for p in result.pages) == 1
    if result.page_count == 1:
        assert result.pages[0].page_kind == PageKind.FIRST
        assert result.pages[0].table_top_px == TABLE_TOP_FIRST
    else:
        assert result.pages[0].page_kind == PageKind.FIRST
        assert result.pages[-1].page_kind == PageKind.FINAL_CONTINUATION
        assert result.pages[-1].table_top_px == TABLE_TOP_CONTINUATION
        assert len(result.pages[-1].rows) >= 1
        for p in result.pages[1:-1]:
            assert p.page_kind == PageKind.CONTINUATION
            assert p.table_top_px == TABLE_TOP_CONTINUATION
            assert p.table_top_px < TABLE_TOP_FIRST


def test_no_summary_only_last_page() -> None:
    h = 40.0
    rows = [PaginatableRow(lp=i, height_px=h) for i in range(1, 41)]
    result = paginate_invoice_items(rows)
    assert result.pages[-1].rows
    assert result.pages[-1].show_summary
