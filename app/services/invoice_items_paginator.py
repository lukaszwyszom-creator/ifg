"""Sales-invoice items pagination (GWO-0015M / 0015M-B) — mechanics only.

0015M-B: three page kinds with different TABLE_TOP / item budgets.
WeasyPrint-measured row heights remain the height source of truth (0015M-A).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

# ---------------------------------------------------------------------------
# Named anchors from app/assets/invoice/layout_shell/master_geometry.json
# (measured_gates / elements) — DO NOT invent alternate X/Y for page-1 chrome.
# ---------------------------------------------------------------------------

TABLE_LEFT_PX = 120
TABLE_RIGHT_PX = 977
TABLE_TOP_PX = 780  # alias: TABLE_TOP_FIRST (frozen page-1)
TABLE_WIDTH_PX = TABLE_RIGHT_PX - TABLE_LEFT_PX  # 857 — frozen X geometry

# Summary band (VAT + DO ZAPŁATY) — frozen anchors
SUMMARY_TOP_PX = 1138
SUMMARY_BOTTOM_PX = 1260

KSEF_FOOTER_TOP_PX = 1385
PAGE_CONTENT_BOTTOM_PX = KSEF_FOOTER_TOP_PX

THEAD_HEIGHT_PX = 28

# ---------------------------------------------------------------------------
# Page-1 budgets (unchanged from 0015M)
# ---------------------------------------------------------------------------

TABLE_TOP_FIRST = TABLE_TOP_PX  # 780

FIRST_NORMAL_ITEMS_HEIGHT = float(
    PAGE_CONTENT_BOTTOM_PX - TABLE_TOP_FIRST - THEAD_HEIGHT_PX
)  # 577

FIRST_FINAL_ITEMS_HEIGHT = float(SUMMARY_TOP_PX - TABLE_TOP_FIRST - THEAD_HEIGHT_PX)
# 330 — single-page / page-1-as-last only

# Back-compat aliases (0015M / 0015M-A tests)
NORMAL_PAGE_ITEMS_HEIGHT = FIRST_NORMAL_ITEMS_HEIGHT
FINAL_PAGE_ITEMS_HEIGHT = FIRST_FINAL_ITEMS_HEIGHT

# ---------------------------------------------------------------------------
# Continuation budgets (0015M-B) — measured from physical continuation chrome
# Minimal ID block (invoice # + „Ciąg dalszy”) bottom ≈ 103.4 MASTER px;
# + 4 mm gap ≈ 20.7 px → TABLE_TOP_CONTINUATION = 124.
# ---------------------------------------------------------------------------

TABLE_TOP_CONTINUATION = 124

CONTINUATION_NORMAL_ITEMS_HEIGHT = float(
    PAGE_CONTENT_BOTTOM_PX - TABLE_TOP_CONTINUATION - THEAD_HEIGHT_PX
)  # 1233

CONTINUATION_FINAL_ITEMS_HEIGHT = float(
    SUMMARY_TOP_PX - TABLE_TOP_CONTINUATION - THEAD_HEIGHT_PX
)  # 986

assert FIRST_NORMAL_ITEMS_HEIGHT > FIRST_FINAL_ITEMS_HEIGHT > 0
assert CONTINUATION_NORMAL_ITEMS_HEIGHT > CONTINUATION_FINAL_ITEMS_HEIGHT > 0
assert TABLE_TOP_CONTINUATION < TABLE_TOP_FIRST


@dataclass(frozen=True)
class PaginationGeometry:
    """Page-geometry profile for paginator budgets (MASTER px).

    Defaults preserve 0015M-C. Locked underlay binder (0015N) injects underlay-bound values.
    """

    table_top_first: int = TABLE_TOP_FIRST
    table_top_continuation: int = TABLE_TOP_CONTINUATION
    table_left_px: int = TABLE_LEFT_PX
    table_right_px: int = TABLE_RIGHT_PX
    first_normal_items_height: float = FIRST_NORMAL_ITEMS_HEIGHT
    first_final_items_height: float = FIRST_FINAL_ITEMS_HEIGHT
    continuation_normal_items_height: float = CONTINUATION_NORMAL_ITEMS_HEIGHT
    continuation_final_items_height: float = CONTINUATION_FINAL_ITEMS_HEIGHT


DEFAULT_GEOMETRY = PaginationGeometry()


class PageKind(str, Enum):
    FIRST = "PAGE_FIRST"
    CONTINUATION = "PAGE_CONTINUATION"
    FINAL_CONTINUATION = "PAGE_FINAL_CONTINUATION"


class RowTooTallError(RuntimeError):
    """Single row taller than allowed page items budget — do not shrink fonts."""

    def __init__(self, *, lp: int, row_height: float, budget: float, page_kind: str):
        self.lp = lp
        self.row_height = row_height
        self.budget = budget
        self.page_kind = page_kind
        super().__init__(
            f"ROW_TOO_TALL lp={lp} height={row_height} budget={budget} page={page_kind}"
        )


@dataclass(frozen=True)
class PaginatableRow:
    lp: int
    height_px: float
    payload: object = None


@dataclass(frozen=True)
class PagePlan:
    page_index: int  # 0-based
    rows: tuple[PaginatableRow, ...]
    is_first: bool
    is_last: bool
    show_summary: bool
    show_payable: bool
    show_ksef_qr: bool
    items_budget_px: float
    table_top_px: int = TABLE_TOP_FIRST
    table_left_px: int = TABLE_LEFT_PX
    table_right_px: int = TABLE_RIGHT_PX
    page_kind: PageKind = PageKind.FIRST

    @property
    def show_continuation_chrome(self) -> bool:
        return self.page_kind in (
            PageKind.CONTINUATION,
            PageKind.FINAL_CONTINUATION,
        )


@dataclass(frozen=True)
class PaginationResult:
    pages: tuple[PagePlan, ...]
    total_items: int
    normal_page_items_height: float = FIRST_NORMAL_ITEMS_HEIGHT
    final_page_items_height: float = FIRST_FINAL_ITEMS_HEIGHT
    first_normal_items_height: float = FIRST_NORMAL_ITEMS_HEIGHT
    continuation_normal_items_height: float = CONTINUATION_NORMAL_ITEMS_HEIGHT
    continuation_final_items_height: float = CONTINUATION_FINAL_ITEMS_HEIGHT
    table_top_first: int = TABLE_TOP_FIRST
    table_top_continuation: int = TABLE_TOP_CONTINUATION

    @property
    def page_count(self) -> int:
        return len(self.pages)


def _height(rows: Sequence[PaginatableRow]) -> float:
    return float(sum(r.height_px for r in rows))


def _pack(
    rows: Sequence[PaginatableRow],
    budget: float,
    *,
    page_kind: str,
) -> tuple[list[PaginatableRow], list[PaginatableRow]]:
    """Greedy pack whole rows into budget; never split a row."""
    taken: list[PaginatableRow] = []
    used = 0.0
    for row in rows:
        if row.height_px > budget + 1e-9:
            raise RowTooTallError(
                lp=row.lp,
                row_height=row.height_px,
                budget=budget,
                page_kind=page_kind,
            )
        if used + row.height_px <= budget + 1e-9:
            taken.append(row)
            used += row.height_px
        else:
            break
    return taken, list(rows[len(taken) :])


def _split_into_budget_pages(
    rows: Sequence[PaginatableRow],
    budget: float,
    *,
    page_kind: str,
) -> list[list[PaginatableRow]]:
    remaining = list(rows)
    out: list[list[PaginatableRow]] = []
    while remaining:
        chunk, remaining = _pack(remaining, budget, page_kind=page_kind)
        if not chunk:
            raise RowTooTallError(
                lp=remaining[0].lp,
                row_height=remaining[0].height_px,
                budget=budget,
                page_kind=page_kind,
            )
        out.append(chunk)
    return out


def _ensure_final_suffix(
    rows: Sequence[PaginatableRow],
    *,
    final_budget: float,
    head_budget: float,
    head_kind: str,
    final_kind: str,
    force_multi: bool = False,
) -> list[list[PaginatableRow]]:
    """Split so last page fits ``final_budget``; prefer smallest valid suffix.

    When ``force_multi`` is True (caller already knows rows do not fit a
    single FIRST final page), never collapse back to one page even if the
    rows would fit ``final_budget`` alone — move a suffix to the final page.
    """
    rows = list(rows)
    if not rows:
        return [[]]
    if not force_multi and _height(rows) <= final_budget + 1e-9:
        packed, left = _pack(rows, final_budget, page_kind=final_kind)
        if left:
            raise RuntimeError("internal pack inconsistency")
        return [packed]

    split_at = len(rows) - 1
    while split_at > 0 and _height(rows[split_at:]) > final_budget + 1e-9:
        split_at -= 1

    tail = rows[split_at:]
    if _height(tail) > final_budget + 1e-9:
        for r in tail:
            if r.height_px > final_budget + 1e-9:
                raise RowTooTallError(
                    lp=r.lp,
                    row_height=r.height_px,
                    budget=final_budget,
                    page_kind=final_kind,
                )
        raise RowTooTallError(
            lp=tail[0].lp,
            row_height=tail[0].height_px,
            budget=final_budget,
            page_kind=final_kind,
        )
    if split_at == 0:
        raise RuntimeError("internal: cannot place any rows on a prior page")

    head = rows[:split_at]
    pages = (
        _split_into_budget_pages(head, head_budget, page_kind=head_kind) if head else []
    )
    pages.append(tail)
    return pages


def _build_page_plan(
    *,
    page_index: int,
    chunk: Sequence[PaginatableRow],
    is_first: bool,
    is_last: bool,
    total_pages: int,
    geom: PaginationGeometry,
) -> PagePlan:
    """Assign page kind, table top, and items budget."""
    if total_pages == 1:
        return PagePlan(
            page_index=page_index,
            rows=tuple(chunk),
            is_first=True,
            is_last=True,
            show_summary=True,
            show_payable=True,
            show_ksef_qr=True,
            items_budget_px=geom.first_final_items_height,
            table_top_px=geom.table_top_first,
            table_left_px=geom.table_left_px,
            table_right_px=geom.table_right_px,
            page_kind=PageKind.FIRST,
        )

    if is_first:
        kind = PageKind.FIRST
        top = geom.table_top_first
        budget = geom.first_normal_items_height
        show_sum = False
    elif is_last:
        kind = PageKind.FINAL_CONTINUATION
        top = geom.table_top_continuation
        budget = geom.continuation_final_items_height
        show_sum = True
    else:
        kind = PageKind.CONTINUATION
        top = geom.table_top_continuation
        budget = geom.continuation_normal_items_height
        show_sum = False

    if _height(chunk) > budget + 1e-9:
        raise RuntimeError(
            f"page {page_index} items height {_height(chunk)} exceeds budget {budget} ({kind})"
        )

    return PagePlan(
        page_index=page_index,
        rows=tuple(chunk),
        is_first=is_first,
        is_last=is_last,
        show_summary=show_sum,
        show_payable=show_sum,
        show_ksef_qr=show_sum,
        items_budget_px=budget,
        table_top_px=top,
        table_left_px=geom.table_left_px,
        table_right_px=geom.table_right_px,
        page_kind=kind,
    )


def _anti_orphan_rebalance(
    pages_rows: list[list[PaginatableRow]],
    *,
    final_budget: float,
) -> list[list[PaginatableRow]]:
    """If the last page has exactly one row, try pulling one more from the previous page."""
    if len(pages_rows) < 2:
        return pages_rows
    last = pages_rows[-1]
    prev = pages_rows[-2]
    if len(last) != 1:
        return pages_rows
    if len(prev) < 2:
        return pages_rows

    candidate = prev[-1]
    proposed_last = [candidate, last[0]]
    if _height(proposed_last) > final_budget + 1e-9:
        return pages_rows

    new_pages = [list(p) for p in pages_rows]
    new_pages[-2] = prev[:-1]
    new_pages[-1] = proposed_last
    if not new_pages[-2]:
        return pages_rows
    return new_pages


def paginate_invoice_items(
    rows: Sequence[PaginatableRow],
    *,
    geometry: PaginationGeometry | None = None,
) -> PaginationResult:
    """Plan pages with FIRST / CONTINUATION / FINAL_CONTINUATION budgets.

    SUMMARY / DO ZAPŁATY / KSeF+QR only on the last page.
    Last page always has ≥1 row when input is non-empty (no summary-only page).
    """
    geom = geometry or DEFAULT_GEOMETRY
    rows = tuple(rows)
    n = len(rows)

    if n == 0:
        page = _build_page_plan(
            page_index=0,
            chunk=(),
            is_first=True,
            is_last=True,
            total_pages=1,
            geom=geom,
        )
        return PaginationResult(
            pages=(page,),
            total_items=0,
            first_normal_items_height=geom.first_normal_items_height,
            final_page_items_height=geom.first_final_items_height,
            continuation_normal_items_height=geom.continuation_normal_items_height,
            continuation_final_items_height=geom.continuation_final_items_height,
            table_top_first=geom.table_top_first,
            table_top_continuation=geom.table_top_continuation,
        )

    taken, rest = _pack(rows, geom.first_final_items_height, page_kind="first_final")
    if not rest:
        page = _build_page_plan(
            page_index=0,
            chunk=taken,
            is_first=True,
            is_last=True,
            total_pages=1,
            geom=geom,
        )
        return PaginationResult(
            pages=(page,),
            total_items=n,
            first_normal_items_height=geom.first_normal_items_height,
            final_page_items_height=geom.first_final_items_height,
            continuation_normal_items_height=geom.continuation_normal_items_height,
            continuation_final_items_height=geom.continuation_final_items_height,
            table_top_first=geom.table_top_first,
            table_top_continuation=geom.table_top_continuation,
        )

    pages_rows: list[list[PaginatableRow]] = []
    remaining = list(rows)

    chunk, remaining_after = _pack(
        remaining, geom.first_normal_items_height, page_kind="first_normal"
    )
    if not chunk:
        raise RowTooTallError(
            lp=remaining[0].lp,
            row_height=remaining[0].height_px,
            budget=geom.first_normal_items_height,
            page_kind="first_normal",
        )

    if not remaining_after:
        pages_rows.extend(
            _ensure_final_suffix(
                chunk,
                final_budget=geom.continuation_final_items_height,
                head_budget=geom.first_normal_items_height,
                head_kind="first_normal",
                final_kind="continuation_final",
                force_multi=True,
            )
        )
    else:
        pages_rows.append(chunk)
        remaining = remaining_after

        while remaining:
            if _height(remaining) <= geom.continuation_final_items_height + 1e-9:
                packed, left = _pack(
                    remaining,
                    geom.continuation_final_items_height,
                    page_kind="continuation_final",
                )
                if left:
                    raise RuntimeError("internal pack inconsistency on continuation final")
                pages_rows.append(packed)
                break

            chunk, remaining_after = _pack(
                remaining,
                geom.continuation_normal_items_height,
                page_kind="continuation_normal",
            )
            if not chunk:
                raise RowTooTallError(
                    lp=remaining[0].lp,
                    row_height=remaining[0].height_px,
                    budget=geom.continuation_normal_items_height,
                    page_kind="continuation_normal",
                )

            if not remaining_after:
                pages_rows.extend(
                    _ensure_final_suffix(
                        chunk,
                        final_budget=geom.continuation_final_items_height,
                        head_budget=geom.continuation_normal_items_height,
                        head_kind="continuation_normal",
                        final_kind="continuation_final",
                        force_multi=True,
                    )
                )
                break

            pages_rows.append(chunk)
            remaining = remaining_after

    pages_rows = _anti_orphan_rebalance(
        pages_rows, final_budget=geom.continuation_final_items_height
    )

    total_pages = len(pages_rows)
    plans: list[PagePlan] = []
    for i, chunk in enumerate(pages_rows):
        plans.append(
            _build_page_plan(
                page_index=i,
                chunk=chunk,
                is_first=(i == 0),
                is_last=(i == total_pages - 1),
                total_pages=total_pages,
                geom=geom,
            )
        )

    flat = [r for p in plans for r in p.rows]
    if len(flat) != n:
        raise RuntimeError(f"item count mismatch: rendered {len(flat)} != input {n}")
    if [r.lp for r in flat] != [r.lp for r in rows]:
        raise RuntimeError("LP_SEQUENCE broken or items reordered/duplicated")
    if n > 0 and any(p.is_last and len(p.rows) == 0 for p in plans):
        raise RuntimeError("summary-only last page is forbidden when items exist")

    return PaginationResult(
        pages=tuple(plans),
        total_items=n,
        normal_page_items_height=geom.first_normal_items_height,
        final_page_items_height=geom.first_final_items_height,
        first_normal_items_height=geom.first_normal_items_height,
        continuation_normal_items_height=geom.continuation_normal_items_height,
        continuation_final_items_height=geom.continuation_final_items_height,
        table_top_first=geom.table_top_first,
        table_top_continuation=geom.table_top_continuation,
    )


def estimate_row_height_px(
    *,
    name: str,
    isbn: str | None = None,
    extra_lines: int = 0,
    base_px: float = 22.0,
    line_px: float = 14.0,
    name_chars_per_line: int = 42,
) -> float:
    """Deterministic height estimate for fixtures/tests (MASTER px)."""
    name = name or ""
    lines = max(1, (len(name) + name_chars_per_line - 1) // name_chars_per_line)
    h = base_px + max(0, lines - 1) * line_px
    if isbn:
        h += line_px
    h += max(0, extra_lines) * line_px
    return float(h)


def rows_from_names(
    names: Sequence[str],
    *,
    isbns: Sequence[str | None] | None = None,
) -> list[PaginatableRow]:
    out: list[PaginatableRow] = []
    for i, name in enumerate(names, start=1):
        isbn = None if isbns is None else isbns[i - 1]
        out.append(
            PaginatableRow(
                lp=i,
                height_px=estimate_row_height_px(name=name, isbn=isbn),
                payload={"name": name, "isbn": isbn, "lp": i},
            )
        )
    return out
