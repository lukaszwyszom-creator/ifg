"""Measure invoice item row heights with the same CSS the POC renderer uses.

Height source of truth for GWO-0015M-A: WeasyPrint layout boxes → MASTER px.
"""
from __future__ import annotations

from typing import Sequence

from app.services.invoice_items_paginator import (
    TABLE_LEFT_PX,
    TABLE_TOP_PX,
    TABLE_WIDTH_PX,
    THEAD_HEIGHT_PX,
)

# A4 MASTER grid
MASTER_HEIGHT_PX = 1536.0
MASTER_WIDTH_CONTENT_PX = float(TABLE_WIDTH_PX)
SCALE_MM_PER_PX = 297.0 / MASTER_HEIGHT_PX
OFFSET_X_MM = 6.0
# WeasyPrint CSS px: 96 px per inch
WEASY_PX_PER_MM = 96.0 / 25.4
A4_WEASY_HEIGHT_PX = 297.0 * WEASY_PX_PER_MM  # ≈1122.52

# Shared items-table CSS fragments (must match render POC exactly)
ITEMS_TABLE_CSS = """
  table.items {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
  }
  table.items th, table.items td {
    padding: 1mm 0.5mm;
    font-size: 7.5pt;
    border-bottom: 0.4pt solid #d2c2a4;
    vertical-align: top;
    font-family: "Palatino Linotype", Palatino, Georgia, serif;
    color: #1a2744;
  }
  table.items th {
    background: #e8d9c0;
    font-size: 5.8pt;
    text-transform: uppercase;
    font-family: "Segoe UI", Arial, sans-serif;
  }
  table.items .num { text-align: right; white-space: nowrap; }
  table.items .bold { font-weight: 700; }
  table.items .sub { font-size: 6.5pt; color: #6b5e4a; }
  table.items th.lp, table.items td.lp { width: 4%; white-space: nowrap; }
  table.items th.name, table.items td.name {
    width: 34%;
    word-wrap: break-word;
    overflow-wrap: anywhere;
  }
  table.items th.qty, table.items td.qty { width: 6%; }
  table.items th.jm, table.items td.jm { width: 5%; white-space: nowrap; }
  table.items th.cnet, table.items td.cnet,
  table.items th.cbru, table.items td.cbru,
  table.items th.vat, table.items td.vat,
  table.items th.vnet, table.items td.vnet,
  table.items th.kvat, table.items td.kvat,
  table.items th.vbru, table.items td.vbru { width: 7.2857%; }
  table.items tbody tr {
    break-inside: avoid;
    page-break-inside: avoid;
  }
"""


def table_width_mm(table_width_px: float | None = None) -> float:
    w = float(TABLE_WIDTH_PX if table_width_px is None else table_width_px)
    return w * SCALE_MM_PER_PX


def table_left_mm(table_left_px: float | None = None) -> float:
    x = float(TABLE_LEFT_PX if table_left_px is None else table_left_px)
    return OFFSET_X_MM + x * SCALE_MM_PER_PX


def _row_html(item: dict) -> str:
    isbn = ""
    if item.get("isbn"):
        isbn = f'<div class="sub">ISBN: {item["isbn"]}</div>'
    return f"""
    <tr data-lp="{item['lp']}">
      <td class="lp">{item['lp']}</td>
      <td class="name">{item['name']}{isbn}</td>
      <td class="num qty">{item.get('qty', '1')}</td>
      <td class="jm">{item.get('unit', 'szt.')}</td>
      <td class="num cnet">{item.get('cnet', '0,00')}</td>
      <td class="num cbru">{item.get('cbru', '0,00')}</td>
      <td class="num vat">{item.get('vat', '5%')}</td>
      <td class="num vnet">{item.get('vnet', '0,00')}</td>
      <td class="num kvat">{item.get('kvat', '0,00')}</td>
      <td class="num bold vbru">{item.get('vbru', '0,00')}</td>
    </tr>"""


def _measure_document_html(
    items: Sequence[dict],
    *,
    table_width_px: float | None = None,
) -> str:
    """Tall single-page canvas so all rows layout without A4 page-break loss."""
    rows = "".join(_row_html(it) for it in items)
    w = table_width_mm(table_width_px)
    page_h_mm = max(400.0, 20.0 + len(items) * 18.0)
    return f"""<!DOCTYPE html>
<html lang="pl"><head><meta charset="UTF-8">
<style>
  @page {{ size: {w + 20:.4f}mm {page_h_mm:.4f}mm; margin: 0; }}
  html, body {{ margin: 0; padding: 0; background: #fff; }}
  .wrap {{
    position: absolute;
    left: 10mm;
    top: 10mm;
    width: {w:.4f}mm;
  }}
  {ITEMS_TABLE_CSS}
</style></head>
<body>
  <div class="wrap" data-slot="measure">
    <table class="items">
      <thead>
        <tr>
          <th class="lp">LP</th>
          <th class="name">Nazwa towaru / usługi</th>
          <th class="num qty">Ilość</th>
          <th class="jm">JM</th>
          <th class="num cnet">Cena netto</th>
          <th class="num cbru">Cena brutto</th>
          <th class="num vat">VAT</th>
          <th class="num vnet">Wartość netto</th>
          <th class="num kvat">Kwota VAT</th>
          <th class="num vbru">Wartość brutto</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</body></html>"""


def weasy_px_to_master_px(weasy_h: float, *, page_height_weasy: float | None = None) -> float:
    """Map WeasyPrint CSS px → MASTER 1536 grid px (A4-calibrated, page-size independent)."""
    _ = page_height_weasy  # kept for call-site compat; conversion is absolute
    return float(weasy_h) * (MASTER_HEIGHT_PX / A4_WEASY_HEIGHT_PX)


def measure_item_row_heights_master_px(
    items: Sequence[dict],
    *,
    table_width_px: float | None = None,
) -> tuple[list[float], float]:
    """Return (per-row MASTER heights in input order, measured thead MASTER height)."""
    from weasyprint import HTML

    if not items:
        return [], float(THEAD_HEIGHT_PX)

    html = _measure_document_html(items, table_width_px=table_width_px)
    doc = HTML(string=html).render()
    heights_by_lp: dict[int, float] = {}
    thead_h = float(THEAD_HEIGHT_PX)

    def walk(box) -> None:
        nonlocal thead_h
        el = getattr(box, "element", None)
        tag = getattr(box, "element_tag", None)
        if tag == "thead":
            thead_h = weasy_px_to_master_px(float(box.height))
        if tag == "tr" and el is not None and el.get("data-lp"):
            lp = int(el.get("data-lp"))
            heights_by_lp[lp] = weasy_px_to_master_px(float(box.height))
        for child in box.all_children():
            walk(child)

    for page in doc.pages:
        walk(page._page_box)

    ordered: list[float] = []
    for it in items:
        lp = int(it["lp"])
        if lp not in heights_by_lp:
            raise RuntimeError(f"measure failed: missing layout box for LP={lp}")
        ordered.append(heights_by_lp[lp])
    return ordered, thead_h


def measure_page_row_bottoms_master_px(html: str) -> dict[int, float]:
    """After render: map LP → row bottom Y in MASTER px (origin top of A4 page)."""
    from weasyprint import HTML

    doc = HTML(string=html).render()
    out: dict[int, float] = {}

    def walk(box) -> None:
        el = getattr(box, "element", None)
        tag = getattr(box, "element_tag", None)
        if tag == "tr" and el is not None and el.get("data-lp"):
            lp = int(el.get("data-lp"))
            bottom = float(box.position_y) + float(box.height)
            out[lp] = weasy_px_to_master_px(bottom)
        for child in box.all_children():
            walk(child)

    for page in doc.pages:
        walk(page._page_box)
    return out
