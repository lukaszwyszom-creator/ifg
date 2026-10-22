"""Deterministic tests for invoice items pagination (GWO-0015M)."""
from __future__ import annotations

import pytest

from app.services.invoice_items_paginator import (
    CONTINUATION_FINAL_ITEMS_HEIGHT,
    CONTINUATION_NORMAL_ITEMS_HEIGHT,
    FINAL_PAGE_ITEMS_HEIGHT,
    FIRST_FINAL_ITEMS_HEIGHT,
    FIRST_NORMAL_ITEMS_HEIGHT,
    KSEF_FOOTER_TOP_PX,
    NORMAL_PAGE_ITEMS_HEIGHT,
    PAGE_CONTENT_BOTTOM_PX,
    SUMMARY_BOTTOM_PX,
    SUMMARY_TOP_PX,
    TABLE_LEFT_PX,
    TABLE_RIGHT_PX,
    TABLE_TOP_CONTINUATION,
    TABLE_TOP_FIRST,
    TABLE_TOP_PX,
    TABLE_WIDTH_PX,
    THEAD_HEIGHT_PX,
    PageKind,
    PaginatableRow,
    PaginationResult,
    RowTooTallError,
    estimate_row_height_px,
    paginate_invoice_items,
    rows_from_names,
)


def _assert_invariants(result: PaginationResult, input_rows: list[PaginatableRow]) -> None:
    pages = result.pages
    assert sum(1 for p in pages if p.show_summary) == 1
    assert sum(1 for p in pages if p.show_payable) == 1
    assert sum(1 for p in pages if p.show_ksef_qr) == 1
    flat = [r for p in pages for r in p.rows]
    assert len(flat) == len(input_rows)
    assert len(flat) == result.total_items
    assert [r.lp for r in flat] == [r.lp for r in input_rows]
    assert [r.lp for r in flat] == list(range(1, len(input_rows) + 1)) or [
        r.lp for r in flat
    ] == [r.lp for r in input_rows]
    # no duplication
    assert len({id(r) for r in flat}) == len(flat)
    assert len({r.lp for r in flat}) == len(flat)
    # last page only for summary; budgets depend on page kind (0015M-B)
    for p in pages:
        if p.is_last:
            assert p.show_summary and p.show_payable and p.show_ksef_qr
            assert sum(r.height_px for r in p.rows) <= p.items_budget_px + 1e-9
            if len(pages) == 1:
                assert p.page_kind == PageKind.FIRST
                assert p.table_top_px == TABLE_TOP_FIRST
                assert p.items_budget_px == FIRST_FINAL_ITEMS_HEIGHT
            else:
                assert p.page_kind == PageKind.FINAL_CONTINUATION
                assert p.table_top_px == TABLE_TOP_CONTINUATION
                assert p.items_budget_px == CONTINUATION_FINAL_ITEMS_HEIGHT
                assert len(p.rows) >= 1 or len(input_rows) == 0
        else:
            assert not p.show_summary and not p.show_payable and not p.show_ksef_qr
            assert sum(r.height_px for r in p.rows) <= p.items_budget_px + 1e-9
            if p.is_first:
                assert p.page_kind == PageKind.FIRST
                assert p.table_top_px == TABLE_TOP_FIRST
                assert p.items_budget_px == FIRST_NORMAL_ITEMS_HEIGHT
            else:
                assert p.page_kind == PageKind.CONTINUATION
                assert p.table_top_px == TABLE_TOP_CONTINUATION
                assert p.items_budget_px == CONTINUATION_NORMAL_ITEMS_HEIGHT


def test_geometry_anchors_match_master_contract() -> None:
    """Freeze gate: anchors are the measured MASTER constants."""
    assert TABLE_TOP_PX == 780
    assert TABLE_TOP_FIRST == 780
    assert TABLE_TOP_CONTINUATION == 124
    assert TABLE_TOP_CONTINUATION < TABLE_TOP_FIRST
    assert TABLE_LEFT_PX == 120
    assert TABLE_RIGHT_PX == 977
    assert TABLE_WIDTH_PX == 857
    assert SUMMARY_TOP_PX == 1138
    assert SUMMARY_BOTTOM_PX == 1260
    assert KSEF_FOOTER_TOP_PX == 1385
    assert PAGE_CONTENT_BOTTOM_PX == 1385
    assert THEAD_HEIGHT_PX == 28
    assert NORMAL_PAGE_ITEMS_HEIGHT == 577.0
    assert FINAL_PAGE_ITEMS_HEIGHT == 330.0
    assert FIRST_NORMAL_ITEMS_HEIGHT == 577.0
    assert FIRST_FINAL_ITEMS_HEIGHT == 330.0
    assert CONTINUATION_NORMAL_ITEMS_HEIGHT == 1233.0
    assert CONTINUATION_FINAL_ITEMS_HEIGHT == 986.0
    assert NORMAL_PAGE_ITEMS_HEIGHT > FINAL_PAGE_ITEMS_HEIGHT


def test_a_one_item_single_page() -> None:
    rows = rows_from_names(["Książka"])
    result = paginate_invoice_items(rows)
    assert result.page_count == 1
    assert result.pages[0].show_summary
    assert result.pages[0].show_payable
    assert [r.lp for r in result.pages[0].rows] == [1]
    _assert_invariants(result, rows)


def test_b_max_rows_fitting_before_summary_one_page() -> None:
    # Uniform short rows of 22px; FINAL budget 330 → floor(330/22)=15
    h = 22.0
    n = int(FINAL_PAGE_ITEMS_HEIGHT // h)
    assert n * h <= FINAL_PAGE_ITEMS_HEIGHT
    assert (n + 1) * h > FINAL_PAGE_ITEMS_HEIGHT
    rows = [PaginatableRow(lp=i, height_px=h, payload=i) for i in range(1, n + 1)]
    result = paginate_invoice_items(rows)
    assert result.page_count == 1
    assert result.pages[0].show_summary
    _assert_invariants(result, rows)


def test_c_one_row_over_limit_two_pages() -> None:
    h = 22.0
    n = int(FINAL_PAGE_ITEMS_HEIGHT // h) + 1
    rows = [PaginatableRow(lp=i, height_px=h, payload=i) for i in range(1, n + 1)]
    result = paginate_invoice_items(rows)
    assert result.page_count == 2
    assert not result.pages[0].show_summary
    assert not result.pages[0].show_payable
    assert result.pages[1].show_summary
    assert result.pages[1].show_payable
    _assert_invariants(result, rows)


def test_d_ten_items() -> None:
    rows = rows_from_names([f"Pozycja {i}" for i in range(1, 11)])
    result = paginate_invoice_items(rows)
    assert result.total_items == 10
    _assert_invariants(result, rows)
    # 10 * ~22 = 220 < 330 → 1 page
    assert result.page_count == 1


def test_e_fifty_plus_items() -> None:
    rows = rows_from_names([f"Pozycja numer {i:03d}" for i in range(1, 51)])
    result = paginate_invoice_items(rows)
    assert result.total_items == 50
    assert result.page_count >= 2
    _assert_invariants(result, rows)
    # continuous LP across pages
    flat_lp = [r.lp for p in result.pages for r in p.rows]
    assert flat_lp == list(range(1, 51))


def test_f_long_multiline_names() -> None:
    long = "Kościoły Archidiecezji Częstochowskiej tom III — bardzo długa nazwa towaru " * 3
    rows = rows_from_names([long, "Krótka", long], isbns=["978-1", None, "978-2"])
    result = paginate_invoice_items(rows)
    _assert_invariants(result, rows)
    assert all(r.height_px > 22 for r in rows if r.lp in (1, 3))


def test_g_mixed_row_heights() -> None:
    rows = [
        PaginatableRow(1, 22),
        PaginatableRow(2, 50),
        PaginatableRow(3, 22),
        PaginatableRow(4, 80),
        PaginatableRow(5, 22),
        PaginatableRow(6, 100),
        PaginatableRow(7, 22),
        PaginatableRow(8, 60),
        PaginatableRow(9, 22),
        PaginatableRow(10, 40),
        PaginatableRow(11, 22),
        PaginatableRow(12, 90),
        PaginatableRow(13, 22),
        PaginatableRow(14, 70),
        PaginatableRow(15, 22),
        PaginatableRow(16, 55),
        PaginatableRow(17, 22),
        PaginatableRow(18, 45),
        PaginatableRow(19, 22),
        PaginatableRow(20, 35),
    ]
    result = paginate_invoice_items(rows)
    _assert_invariants(result, rows)


def test_h_partially_paid_does_not_affect_pagination() -> None:
    """Paginator must not depend on payment amounts — only row heights."""
    rows = rows_from_names([f"Item {i}" for i in range(1, 12)])
    # Simulate remaining_amount semantics outside paginator
    remaining_amount = 400.0
    total_gross = 1000.0
    amount_due = remaining_amount  # existing business rule
    result = paginate_invoice_items(rows)
    _assert_invariants(result, rows)
    assert amount_due == 400.0
    assert total_gross == 1000.0


def test_i_remaining_zero_does_not_affect_pagination() -> None:
    rows = rows_from_names(["A", "B", "C"])
    remaining_amount = 0.0
    result = paginate_invoice_items(rows)
    _assert_invariants(result, rows)
    assert remaining_amount == 0.0
    assert result.page_count == 1


def test_j_remaining_none_does_not_affect_pagination() -> None:
    rows = rows_from_names(["A", "B"])
    remaining_amount = None
    total_gross = 18000.0
    amount_due = total_gross if remaining_amount is None else remaining_amount
    result = paginate_invoice_items(rows)
    _assert_invariants(result, rows)
    assert amount_due == 18000.0


def test_row_too_tall_raises() -> None:
    rows = [PaginatableRow(lp=1, height_px=FINAL_PAGE_ITEMS_HEIGHT + 10)]
    with pytest.raises(RowTooTallError) as ei:
        paginate_invoice_items(rows)
    assert ei.value.lp == 1
    assert "ROW_TOO_TALL" in str(ei.value)


def test_row_too_tall_on_normal_budget() -> None:
    # Fits final? No — taller than normal too
    rows = [
        PaginatableRow(1, 22),
        PaginatableRow(2, NORMAL_PAGE_ITEMS_HEIGHT + 5),
    ]
    # First row alone doesn't fill; second is too tall for normal when multi needed
    # Actually: first packs into final attempt fails due to second; then normal pack
    # takes first, remaining=[row2], row2 too tall for final and for normal
    with pytest.raises(RowTooTallError):
        paginate_invoice_items(rows)


def test_estimate_row_height_isbn_and_wrap() -> None:
    short = estimate_row_height_px(name="X")
    long = estimate_row_height_px(name="Y" * 100, isbn="978")
    assert long > short


def test_summary_exactly_once_across_many_pages() -> None:
    h = 40.0
    n = 40
    rows = [PaginatableRow(lp=i, height_px=h) for i in range(1, n + 1)]
    result = paginate_invoice_items(rows)
    assert result.page_count >= 3
    assert sum(p.show_summary for p in result.pages) == 1
    assert sum(p.show_payable for p in result.pages) == 1
    assert sum(p.show_ksef_qr for p in result.pages) == 1
    _assert_invariants(result, rows)
