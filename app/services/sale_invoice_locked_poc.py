"""Locked graphic underlay binder POC (GWO-0015N).

Layers: background → stained glass → scalar fields → items → VAT/due → KSeF/QR.
Does NOT redesign the underlay. Does NOT bind production pdf_service.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.services.invoice_items_paginator import (
    PageKind,
    PagePlan,
    PaginationGeometry,
    PaginationResult,
    PaginatableRow,
    paginate_invoice_items,
)
from app.services.invoice_items_row_measure import (
    ITEMS_TABLE_CSS,
    measure_item_row_heights_master_px,
)
from app.services.ksef_qr import (
    build_invoice_verification_url,
    render_qr_png_data_uri,
)

_ASSETS = Path(__file__).resolve().parents[2] / "app" / "assets" / "invoice" / "sale_locked"
_BG = _ASSETS / "sale_invoice_background_locked.png"
_FIELDS = _ASSETS / "sale_invoice_fields.json"
_PROFILE = _ASSETS / "sale_invoice_binding_profile.json"
_GLASS_MOD = _ASSETS / "stained_glass_module.json"
_GLASS_PNG = _ASSETS / "stained_glass_current.png"

SCALE = 297.0 / 1536.0
OFFSET_X_MM = 6.0
NAVY = "#1a2744"
BROWN = "#8a7348"


@dataclass
class FieldOverflow:
    field: str
    reason: str


@dataclass
class LockedBindResult:
    html: str
    plan: PaginationResult
    overflows: list[FieldOverflow] = field(default_factory=list)
    qr_status: str = "INCOMPLETE"
    summary_count: int = 0
    payable_count: int = 0
    qr_count: int = 0
    background_sha256: str = ""
    fields_sha256: str = ""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_fields() -> dict[str, Any]:
    return json.loads(_FIELDS.read_text(encoding="utf-8"))


def load_binding_profile() -> dict[str, Any]:
    return json.loads(_PROFILE.read_text(encoding="utf-8"))


def load_glass_module() -> dict[str, Any]:
    return json.loads(_GLASS_MOD.read_text(encoding="utf-8"))


def geometry_from_profile(profile: dict[str, Any]) -> PaginationGeometry:
    fp = profile["FIRST_PAGE_ITEMS_HEIGHT"]
    cont = profile["CONTINUATION"]
    return PaginationGeometry(
        table_top_first=int(profile["TABLE_ITEMS_TOP_PX"]),
        table_top_continuation=int(cont["TABLE_TOP_CONTINUATION_PX"]),
        table_left_px=int(profile["TABLE_LEFT_PX"]),
        table_right_px=int(profile["TABLE_RIGHT_PX"]),
        first_normal_items_height=float(fp["normal"]),
        first_final_items_height=float(fp["final"]),
        continuation_normal_items_height=float(cont["NORMAL_ITEMS_HEIGHT"]),
        continuation_final_items_height=float(cont["FINAL_ITEMS_HEIGHT"]),
    )


def px_to_mm(x: float = 0, y: float = 0, w: float = 0, h: float = 0) -> dict[str, float]:
    return {
        "x": OFFSET_X_MM + x * SCALE,
        "y": y * SCALE,
        "w": w * SCALE,
        "h": h * SCALE,
    }


def rect_to_mm(rect: list[int]) -> dict[str, float]:
    x1, y1, x2, y2 = rect
    return px_to_mm(x1, y1, x2 - x1, y2 - y1)


def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _money(v: Decimal) -> str:
    q = v.quantize(Decimal("0.01"))
    sign = "-" if q < 0 else ""
    a = abs(q)
    raw = f"{a:.2f}"
    whole, frac = raw.split(".")
    groups = []
    while whole:
        groups.append(whole[-3:])
        whole = whole[:-3]
    return f"{sign}{' '.join(reversed(groups))},{frac}"


def _parse_style(token: str) -> dict[str, str]:
    """Map fields.json style tokens → CSS (MASTER px size → mm via SCALE)."""
    # e.g. serif_bold_26_navy / serif_19_navy / serif_bold_18_brown
    bold = "bold" in token
    m = re.search(r"_(\d+)_", token)
    size_px = int(m.group(1)) if m else 18
    color = BROWN if "brown" in token else NAVY
    return {
        "font-family": '"Palatino Linotype", Palatino, Georgia, serif',
        "font-weight": "700" if bold else "400",
        "font-size": f"{size_px * SCALE:.4f}mm",
        "color": color,
        "line-height": "1.2",
    }


def _style_attr(style: dict[str, str]) -> str:
    return ";".join(f"{k}:{v}" for k, v in style.items())


def _estimate_overflow(
    field_name: str,
    text: str,
    rect: list[int],
    *,
    style_token: str | None,
    max_lines: int | None,
) -> FieldOverflow | None:
    if not text:
        return None
    size_px = 18
    if style_token:
        m = re.search(r"_(\d+)_", style_token)
        if m:
            size_px = int(m.group(1))
    x1, y1, x2, y2 = rect
    avail_w = float(x2 - x1)
    avail_h = float(y2 - y1)
    char_w = size_px * 0.55
    if max_lines and max_lines > 1:
        chars_per = max(1, int(avail_w / char_w))
        lines_needed = max(1, (len(text) + chars_per - 1) // chars_per)
        if lines_needed > max_lines:
            return FieldOverflow(field_name, f"wrap exceeds max_lines={max_lines}")
        if lines_needed * size_px * 1.2 > avail_h:
            return FieldOverflow(field_name, "multiline taller than slot")
        return None
    need_w = len(text) * char_w
    if need_w > avail_w:
        return FieldOverflow(field_name, "single-line wider than slot")
    if size_px > avail_h * 0.98:
        return FieldOverflow(field_name, "font taller than slot")
    return None


def _file_data_uri(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _stained_glass_html(mod: dict[str, Any]) -> str:
    anchor = mod["anchor"]
    viewport = mod["viewport"]
    diam = float(viewport["diameter_px"])
    cx = float(anchor["center_x_px"]) + float(mod.get("local_offset_x_px") or 0)
    cy = float(anchor["center_y_px"]) + float(mod.get("local_offset_y_px") or 0)
    left = cx - diam / 2
    top = cy - diam / 2
    box = px_to_mm(left, top, diam, diam)
    rot = float(mod.get("rotation_deg") or 0)
    scale = float(mod.get("scale") or 1.0)
    uri = _file_data_uri(_GLASS_PNG)
    # Circular clip; crop center of asset via background-size/position
    crop_x = float(mod.get("crop_x") or 0.5) * 100
    crop_y = float(mod.get("crop_y") or 0.5) * 100
    return f"""
    <div class="abs glass stained-glass has-asset" data-slot="stained_glass"
         data-stained-glass="provided"
         style="left:{box['x']:.4f}mm;top:{box['y']:.4f}mm;width:{box['w']:.4f}mm;height:{box['h']:.4f}mm;
                border-radius:50%;overflow:hidden;z-index:{int(mod.get('z_index') or 20)};
                transform:rotate({rot}deg) scale({scale});transform-origin:center center;">
      <img src="{uri}" alt="" style="width:100%;height:100%;object-fit:cover;
           object-position:{crop_x:.1f}% {crop_y:.1f}%;"/>
    </div>"""

def _amount_due_value(*, remaining: Decimal | None, total_gross: Decimal) -> Decimal:
    if remaining is not None:
        return remaining
    return total_gross


@dataclass
class PocInvoiceFixture:
    """Locked-layout render model (POC fixtures + production adapter share this)."""

    invoice_number: str
    issue_date: str
    sale_date: str
    due_date: str
    payment_method: str
    bank_account: str
    seller_name: str
    seller_address: str
    seller_nip: str
    buyer_name: str
    buyer_address: str
    buyer_nip: str
    items: list[dict]
    remaining_amount: Decimal | None
    ksef_number: str | None = None
    ksef_xml_bytes: bytes | None = None
    ksef_environment: str = "test"
    # Optional production extras (defaults keep 0015N POC behaviour).
    vat_rows: list[tuple[str, Decimal, Decimal, Decimal]] | None = None
    currency: str = "PLN"
    production_bound: bool = False
    # When set (production), amount-due fallback uses invoice.total_gross SoT.
    total_gross: Decimal | None = None
    # Dynamic document title (0015O-A): replaces baked underlay "FAKTURA VAT" text only.
    document_title: str = "FAKTURA VAT"

# Production alias
LockedInvoiceData = PocInvoiceFixture


def build_fixture(n_items: int, *, remaining: Decimal | None, partial: bool = False) -> PocInvoiceFixture:
    items = []
    for i in range(1, n_items + 1):
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
                "net": Decimal("100.00"),
                "vat_amt": Decimal("5.00"),
                "gross": Decimal("105.00"),
            }
        )
    total = Decimal("105.00") * n_items
    rem = remaining
    if partial and rem is None:
        rem = (total * Decimal("0.4")).quantize(Decimal("0.01"))
    return PocInvoiceFixture(
        invoice_number=f"FV/26/{n_items:04d}",
        issue_date="02.10.2026",
        sale_date="02.10.2026",
        due_date="16.10.2026",
        payment_method="przelew",
        bank_account="12 ACCT-000009 9012 3456",
        seller_name="Wydawnictwo Ikona Sp. z o.o.",
        seller_address="ul. Dominika 11, 83-130 Pelplin",
        seller_nip="9670402857",
        buyer_name="Parafia pw. św. Jana w Przykładowie",
        buyer_address="ul. Kościelna 3, 00-001 Warszawa",
        buyer_nip="5250000000",
        items=items,
        remaining_amount=rem,
        ksef_number=None,
        ksef_xml_bytes=None,
    )


def _document_title_html(
    fixture: PocInvoiceFixture,
    profile: dict[str, Any],
) -> str:
    """Cream-mask baked underlay title + paint dynamic document_title (same geometry)."""
    cream = profile["CREAM_RGB"]
    cream_css = f"rgb({cream[0]},{cream[1]},{cream[2]})"
    box = rect_to_mm(_DOC_TITLE_RECT)
    style = _parse_style(_DOC_TITLE_STYLE)
    style["white-space"] = "nowrap"
    style["overflow"] = "hidden"
    style["text-overflow"] = "clip"
    style["display"] = "flex"
    style["align-items"] = "center"
    title = (fixture.document_title or "FAKTURA VAT").strip() or "FAKTURA VAT"
    return f"""
    <div class="abs" data-slot="document_title_mask" data-visual="doc_title_mask"
         style="left:{box['x']:.4f}mm;top:{box['y']:.4f}mm;width:{box['w']:.4f}mm;height:{box['h']:.4f}mm;
                background:{cream_css};z-index:28;"></div>
    <div class="abs field" data-slot="document_title" data-visual-text="document_title"
         style="left:{box['x']:.4f}mm;top:{box['y']:.4f}mm;width:{box['w']:.4f}mm;height:{box['h']:.4f}mm;
                z-index:30;{_style_attr(style)}">{_esc(title)}</div>"""


def _scalar_fields_html(
    fixture: PocInvoiceFixture,
    fields: dict[str, Any],
    overflows: list[FieldOverflow],
) -> str:
    mapping = {
        "invoice_number": fixture.invoice_number,
        "issue_date": fixture.issue_date,
        "sale_date": fixture.sale_date,
        "due_date": fixture.due_date,
        "payment_method": fixture.payment_method,
        "bank_account": fixture.bank_account,
        "seller_name": fixture.seller_name,
        "seller_address": fixture.seller_address,
        "seller_nip": f"NIP: {fixture.seller_nip}",
        "buyer_name": fixture.buyer_name,
        "buyer_address": fixture.buyer_address,
        "buyer_nip": f"NIP: {fixture.buyer_nip}",
    }
    parts = []
    for name, text in mapping.items():
        meta = fields["fields"][name]
        rect = meta["rect"]
        style_token = meta.get("style")
        max_lines = meta.get("max_lines")
        ov = _estimate_overflow(
            name, text, rect, style_token=style_token, max_lines=max_lines
        )
        if ov:
            overflows.append(ov)
        box = rect_to_mm(rect)
        style = _parse_style(style_token or "serif_19_navy")
        align = meta.get("align")
        if align:
            style["text-align"] = align
        if max_lines and max_lines > 1:
            style["overflow"] = "hidden"
            style["display"] = "-webkit-box"
            style["-webkit-line-clamp"] = str(max_lines)
            style["-webkit-box-orient"] = "vertical"
        else:
            style["white-space"] = "nowrap"
            style["overflow"] = "hidden"
            style["text-overflow"] = "clip"
        parts.append(
            f'<div class="abs field" data-slot="{name}" '
            f'style="left:{box["x"]:.4f}mm;top:{box["y"]:.4f}mm;'
            f'width:{box["w"]:.4f}mm;height:{box["h"]:.4f}mm;{_style_attr(style)}">'
            f"{_esc(text)}</div>"
        )
    return "\n".join(parts)


def _items_table_html(page: PagePlan, *, include_thead: bool) -> str:
    thead = ""
    if include_thead:
        thead = """
        <thead><tr>
          <th class="lp">LP</th><th class="name">Nazwa towaru / usługi</th>
          <th class="num qty">Ilość</th><th class="jm">JM</th>
          <th class="num cnet">Cena netto</th><th class="num cbru">Cena brutto</th>
          <th class="num vat">VAT</th><th class="num vnet">Wartość netto</th>
          <th class="num kvat">Kwota VAT</th><th class="num vbru">Wartość brutto</th>
        </tr></thead>"""
    rows = []
    for r in page.rows:
        it = r.payload
        isbn = f'<div class="sub">ISBN: {_esc(it["isbn"])}</div>' if it.get("isbn") else ""
        rows.append(
            f'<tr data-lp="{it["lp"]}" style="break-inside:avoid;page-break-inside:avoid;">'
            f'<td class="lp">{it["lp"]}</td>'
            f'<td class="name">{_esc(it["name"])}{isbn}</td>'
            f'<td class="num qty">{it["qty"]}</td><td class="jm">{it["unit"]}</td>'
            f'<td class="num cnet">{it["cnet"]}</td><td class="num cbru">{it["cbru"]}</td>'
            f'<td class="num vat">{it["vat"]}</td><td class="num vnet">{it["vnet"]}</td>'
            f'<td class="num kvat">{it["kvat"]}</td>'
            f'<td class="num bold vbru">{it["vbru"]}</td></tr>'
        )
    return f'<table class="items">{thead}<tbody>{"".join(rows)}</tbody></table>'


# Static underlay chrome measured on sale_invoice_background_locked.png (MASTER px).
# Do not invent — used only to avoid covering baked labels / separators.
_VAT_TITLE_TOP_PX = 1140  # static "PODSUMOWANIE VAT" ink ~1143..1154; cream must stop above
_KSEF_LABEL_RECT = [128, 1422, 210, 1448]  # measured "KSeF:" ink ~134..202 × 1426..1443
_KSEF_LINE_Y_PX = 1389
_QR_MASK_RECT = [820, 1395, 990, 1518]  # below horizontal line; no line/ornament overlap
# Baked "FAKTURA VAT" ink ~[120,383]–[425,412]; wider rect for longer KOR titles.
# Bottom stays above the gold rule (~y413). fields.json unchanged — runtime constant only.
_DOC_TITLE_RECT = [118, 380, 720, 412]
_DOC_TITLE_STYLE = "serif_bold_36_navy"

# 0015N-D: continuation final reuses locked underlay pixels for summary/payable chrome
# (title, headers, frame, DO ZAPŁATY box) — same visual language as PAGE_FIRST_FINAL.
_SUMMARY_CHROME_RECT = [118, 1140, 987, 1278]
_PAYABLE_LABEL_LEFT_PX = 740  # underlay "DO ZAPŁATY" ink ~x740..805

_summary_chrome_uri_cache: str | None = None


def _summary_chrome_data_uri() -> str:
    """Crop summary+payable chrome from locked underlay (immutable source; runtime only)."""
    global _summary_chrome_uri_cache
    if _summary_chrome_uri_cache is not None:
        return _summary_chrome_uri_cache
    from PIL import Image
    import io

    x1, y1, x2, y2 = _SUMMARY_CHROME_RECT
    img = Image.open(_BG).convert("RGB").crop((x1, y1, x2, y2))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    _summary_chrome_uri_cache = (
        "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    )
    return _summary_chrome_uri_cache


def _summary_values_overlay_html(
    *,
    vat_rows: list[tuple[str, Decimal, Decimal, Decimal]],
    due: Decimal,
    currency: str,
    vat_rect: list[int],
    due_rect: list[int],
    cream_css: str,
    due_style: dict[str, str],
    chrome_source: str,
) -> str:
    """Shared values-only paint used by PAGE_FIRST_FINAL and PAGE_CONTINUATION_FINAL."""
    vb = rect_to_mm(vat_rect)
    db = rect_to_mm(due_rect)
    td = f"padding:0.5mm 0.5mm;font-size:8pt;line-height:1.15;color:{NAVY};"
    body_rows = []
    for rate_label, net, vat, gross in vat_rows:
        body_rows.append(
            f"<tr>"
            f'<td style="{td}">{_esc(rate_label)}</td>'
            f'<td style="{td}text-align:right;">{_money(net)}</td>'
            f'<td style="{td}text-align:right;">{_money(vat)}</td>'
            f'<td style="{td}text-align:right;font-weight:700;">{_money(gross)}</td>'
            f"</tr>"
        )
    return f"""
    <div class="abs summary-layer" data-slot="vat_summary" data-visual="summary"
         data-summary-chrome="{chrome_source}"
         style="left:{vb['x']:.4f}mm;top:{vb['y']:.4f}mm;width:{vb['w']:.4f}mm;height:{vb['h']:.4f}mm;
                background:{cream_css};overflow:visible;z-index:45;padding:0.6mm 0.6mm;box-sizing:border-box;">
      <table class="vat" data-dynamic-vat-values="1" style="width:100%;border-collapse:collapse;table-layout:fixed;">
        <tbody>{"".join(body_rows)}</tbody>
      </table>
    </div>
    <div class="abs summary-layer" data-slot="amount_due" data-visual="payable"
         data-payable-label="static-underlay" data-payable-box="static-underlay"
         style="left:{db['x']:.4f}mm;top:{db['y']:.4f}mm;width:{db['w']:.4f}mm;height:{db['h']:.4f}mm;
                background:transparent;border:none;padding:0;box-sizing:border-box;
                overflow:visible;z-index:45;display:flex;align-items:flex-end;justify-content:flex-end;">
      <div data-visual-text="amount_due" class="due-amount"
           style="{_style_attr(due_style)};color:{NAVY};">{_money(due)} {_esc(currency)}</div>
    </div>"""


def _summary_html(
    fixture: PocInvoiceFixture,
    fields: dict[str, Any],
    profile: dict[str, Any],
    *,
    include_static_chrome: bool = False,
) -> str:
    """Summary / payable paint.

    PAGE_FIRST(_FINAL): values only — locked underlay already has title/headers/label.
    PAGE_CONTINUATION_FINAL (0015N-D): same values overlay + underlay-cropped chrome image
    so visual language matches PAGE_FIRST_FINAL 1:1 (no redesigned HTML chrome).
    """
    items_gross = sum((it["gross"] for it in fixture.items), Decimal("0"))
    total_gross = (
        fixture.total_gross if fixture.total_gross is not None else items_gross
    )
    due = _amount_due_value(
        remaining=fixture.remaining_amount, total_gross=total_gross
    )
    if fixture.vat_rows:
        vat_rows = list(fixture.vat_rows)
    else:
        # POC default: single 5% rollup of item Decimals
        vat_rows = [
            (
                "5%",
                sum((it["net"] for it in fixture.items), Decimal("0")),
                sum((it["vat_amt"] for it in fixture.items), Decimal("0")),
                items_gross,
            )
        ]
    vat_rect = fields["fields"]["vat_summary"]["rect"]
    due_rect = fields["fields"]["amount_due"]["rect"]
    cream = profile["CREAM_RGB"]
    cream_css = f"rgb({cream[0]},{cream[1]},{cream[2]})"

    due_style = _parse_style(fields["fields"]["amount_due"].get("style", "serif_bold_28_navy"))
    due_style["text-align"] = fields["fields"]["amount_due"].get("align", "right")
    due_h_mm = (due_rect[3] - due_rect[1]) * SCALE
    due_style["font-size"] = (
        f"{min(float(due_style['font-size'].replace('mm', '')), due_h_mm * 0.55):.4f}mm"
    )

    overlay = _summary_values_overlay_html(
        vat_rows=vat_rows,
        due=due,
        currency=fixture.currency or "PLN",
        vat_rect=vat_rect,
        due_rect=due_rect,
        cream_css=cream_css,
        due_style=due_style,
        chrome_source="underlay" if not include_static_chrome else "underlay-crop",
    )
    if not include_static_chrome:
        return overlay

    # Continuation final: place locked underlay chrome crop, then shared values overlay.
    cb = rect_to_mm(_SUMMARY_CHROME_RECT)
    chrome_uri = _summary_chrome_data_uri()
    return f"""
    <img class="abs summary-chrome" data-slot="summary_payable_chrome"
         data-summary-chrome="underlay-crop" alt=""
         src="{chrome_uri}"
         style="left:{cb['x']:.4f}mm;top:{cb['y']:.4f}mm;width:{cb['w']:.4f}mm;height:{cb['h']:.4f}mm;
                z-index:43;"/>
    {overlay}"""


def _ksef_mask_html(fields: dict[str, Any], profile: dict[str, Any]) -> str:
    """Cream overprint ONLY of baked KSeF: glyph (+ QR body below separator).

    Measured KSeF: text ≈ [134,1426]–[202,1443]. Horizontal rules at y=1389/1391
    must stay continuous — QR mask starts at y=1395 (below line).
    """
    _ = fields  # fields kept for call-site symmetry; mask uses measured chrome rects
    cream = profile["CREAM_RGB"]
    cream_css = f"rgb({cream[0]},{cream[1]},{cream[2]})"
    kb = rect_to_mm(_KSEF_LABEL_RECT)
    qb = rect_to_mm(_QR_MASK_RECT)
    assert _KSEF_LABEL_RECT[1] > _KSEF_LINE_Y_PX
    assert _QR_MASK_RECT[1] > _KSEF_LINE_Y_PX
    return f"""
    <div class="abs ksef-mask" data-slot="ksef_label_mask" data-visual="ksef_mask"
         style="left:{kb['x']:.4f}mm;top:{kb['y']:.4f}mm;width:{kb['w']:.4f}mm;height:{kb['h']:.4f}mm;
                background:{cream_css};z-index:42;"></div>
    <div class="abs ksef-mask" data-slot="ksef_qr_mask" data-visual="qr_mask"
         style="left:{qb['x']:.4f}mm;top:{qb['y']:.4f}mm;width:{qb['w']:.4f}mm;height:{qb['h']:.4f}mm;
                background:{cream_css};z-index:42;"></div>
    """


def _ksef_html(
    fixture: PocInvoiceFixture,
    fields: dict[str, Any],
) -> tuple[str, str, int]:
    """Return (html, qr_status, qr_count)."""
    ksef_rect = fields["fields"]["ksef_number"]["rect"]
    qr_rect = fields["fields"]["ksef_qr"]["rect"]
    kb = rect_to_mm(ksef_rect)
    qb = rect_to_mm(qr_rect)
    style = _parse_style(fields["fields"]["ksef_number"].get("style", "serif_bold_18_brown"))
    ref = fixture.ksef_number or ""
    ksef_text = f"KSEF: {_esc(ref)}" if ref else ""

    qr_status = "INCOMPLETE"
    qr_img = ""
    qr_count = 0
    qr_url_attr = ""
    if fixture.ksef_xml_bytes and fixture.seller_nip and fixture.issue_date:
        # parse DD.MM.YYYY
        try:
            d, m, y = fixture.issue_date.split(".")
            issue = date(int(y), int(m), int(d))
        except Exception:
            issue = None
        if issue:
            payload = build_invoice_verification_url(
                seller_nip=re.sub(r"\D", "", fixture.seller_nip),
                issue_date=issue,
                xml_bytes=fixture.ksef_xml_bytes,
                environment=fixture.ksef_environment,
            )
            if payload:
                uri = render_qr_png_data_uri(payload.url)
                if uri:
                    qr_img = (
                        f'<img src="{uri}" alt="Kod weryfikujący KSeF" '
                        f'style="width:100%;height:100%;object-fit:contain;"/>'
                    )
                    qr_status = "ok"
                    qr_count = 1
                    qr_url_attr = f' data-qr-url="{_esc(payload.url)}"'
                else:
                    qr_status = "LIBRARY_MISSING"

    html = f"""
    <div class="abs" data-slot="ksef_number"
         style="left:{kb['x']:.4f}mm;top:{kb['y']:.4f}mm;width:{kb['w']:.4f}mm;height:{kb['h']:.4f}mm;
                {_style_attr(style)}">{ksef_text}</div>
    <div class="abs qr-slot" data-slot="ksef_qr" data-qr-status="{qr_status}"{qr_url_attr}
         {'aria-hidden="true"' if qr_status == "INCOMPLETE" else ""}
         style="left:{qb['x']:.4f}mm;top:{qb['y']:.4f}mm;width:{qb['w']:.4f}mm;height:{qb['h']:.4f}mm;
                background:#fff;border:0.55pt solid #d2c2a4;box-sizing:border-box;">{qr_img}</div>
    """
    return html, qr_status, qr_count


def render_locked_invoice(fixture: PocInvoiceFixture) -> LockedBindResult:
    fields = load_fields()
    profile = load_binding_profile()
    glass = load_glass_module()
    geom = geometry_from_profile(profile)
    bg_sha = sha256_file(_BG)
    fields_sha = sha256_file(_FIELDS)

    heights, _ = measure_item_row_heights_master_px(
        fixture.items,
        table_width_px=float(profile["TABLE_WIDTH_PX"]),
    )
    rows = [
        PaginatableRow(lp=it["lp"], height_px=h, payload=it)
        for it, h in zip(fixture.items, heights)
    ]
    plan = paginate_invoice_items(rows, geometry=geom)
    overflows: list[FieldOverflow] = []

    cream = profile["CREAM_RGB"]
    cream_css = f"rgb({cream[0]},{cream[1]},{cream[2]})"
    bg_uri = _file_data_uri(_BG)
    master_w_mm = 198.0
    master_h_mm = 297.0

    pages_html = []
    summary_count = 0
    payable_count = 0
    qr_count_total = 0
    qr_status = "INCOMPLETE"

    for page in plan.pages:
        layers = []
        if page.page_kind == PageKind.FIRST:
            # LAYER 1 background
            layers.append(
                f'<img class="abs bg" data-layer="background" src="{bg_uri}" '
                f'style="left:{OFFSET_X_MM:.4f}mm;top:0;width:{master_w_mm:.4f}mm;height:{master_h_mm:.4f}mm;" alt=""/>'
            )
            # LAYER 2 glass
            layers.append(_stained_glass_html(glass))
            # LAYER 2b: dynamic document title over baked "FAKTURA VAT" (0015O-A)
            layers.append(_document_title_html(fixture, profile))
            # LAYER 3 scalars
            layers.append(_scalar_fields_html(fixture, fields, overflows))
            include_thead = False  # underlay paints thead
            items_top = page.table_top_px
            # BUG B: hide baked KSeF/QR chrome on non-final first page (runtime mask only)
            if plan.page_count > 1 and not page.show_ksef_qr:
                layers.append(_ksef_mask_html(fields, profile))
        else:
            # Continuation: functional chrome only
            left = px_to_mm(page.table_left_px)["x"]
            width = (page.table_right_px - page.table_left_px) * SCALE
            layers.append(
                f'<div class="cont-id" data-slot="continuation_id" '
                f'style="left:{left:.4f}mm;top:12mm;width:{width:.4f}mm;">'
                f'<div class="cont-num">{_esc(fixture.invoice_number)}</div>'
                f'<div class="cont-label">Ciąg dalszy</div></div>'
            )
            include_thead = True
            items_top = page.table_top_px

        # LAYER 4 items overprint
        # Pagination budgets unchanged; visual cream may stop above summary chrome
        # (PODSUMOWANIE VAT ~y1143) on any final page that paints summary.
        items_h = page.items_budget_px
        if include_thead:
            items_h = page.items_budget_px + float(profile["CONTINUATION"]["THEAD_HEIGHT_PX"])
        if page.show_summary:
            max_visual_h = float(_VAT_TITLE_TOP_PX - items_top)
            if max_visual_h > 0:
                items_h = min(items_h, max_visual_h)
        box = px_to_mm(
            page.table_left_px,
            items_top,
            page.table_right_px - page.table_left_px,
            items_h,
        )
        layers.append(
            f'<div class="abs table-wrap" data-slot="items" data-layer="items_dynamic" '
            f'style="left:{box["x"]:.4f}mm;top:{box["y"]:.4f}mm;width:{box["w"]:.4f}mm;'
            f'height:{box["h"]:.4f}mm;background:{cream_css};overflow:visible;">'
            f"{_items_table_html(page, include_thead=include_thead)}</div>"
        )

        if page.show_summary:
            # Continuation final has no locked underlay → paint full end-block chrome.
            paint_chrome = page.page_kind != PageKind.FIRST
            layers.append(
                _summary_html(
                    fixture, fields, profile, include_static_chrome=paint_chrome
                )
            )
            summary_count += 1
            payable_count += 1
        if page.show_ksef_qr:
            khtml, qr_status, qn = _ksef_html(fixture, fields)
            layers.append(khtml)
            qr_count_total += qn

        pages_html.append(
            f'<section class="page" data-page="{page.page_index + 1}" '
            f'data-page-kind="{page.page_kind.value}" '
            f'data-table-top-px="{page.table_top_px}">'
            f'<div class="sheet">{"".join(layers)}'
            f'<div class="page-no">Strona {page.page_index + 1} / {plan.page_count}</div>'
            f"</div></section>"
        )

    # Table CSS with underlay width — reuse shared CSS
    bound_flag = "yes" if fixture.production_bound else "no"
    template = "sale-locked"
    html = f"""<!DOCTYPE html>
<html lang="pl"><head><meta charset="UTF-8">
<title>Faktura {_esc(fixture.invoice_number)}</title>
<style>
@page {{ size: A4; margin: 0; }}
html, body {{ margin:0; padding:0; background:#fff; color:{NAVY}; color-scheme: light;
  font-family:"Palatino Linotype", Palatino, Georgia, serif; }}
.page {{ page-break-after: always; }}
.page:last-child {{ page-break-after: auto; }}
.sheet {{ position:relative; width:210mm; height:297mm; overflow:hidden; background:#fff; }}
.abs {{ position:absolute; box-sizing:border-box; }}
.bg {{ z-index:1; }}
.glass {{ z-index:20; }}
.field {{ z-index:30; }}
.table-wrap {{ z-index:40; }}
.summary-layer {{ z-index:45; }}
.ksef-mask {{ z-index:42; }}
.cont-id {{ position:absolute; color:#6b5e4a; z-index:30; }}
.cont-num {{ font-weight:700; color:{NAVY}; font-size:10pt; }}
.cont-label {{ margin-top:1mm; font-size:8pt; text-transform:uppercase; letter-spacing:0.04em; }}
{ITEMS_TABLE_CSS}
.page-no {{ position:absolute; right:12mm; bottom:6mm; font-size:8pt; color:#6b5e4a; z-index:50; }}
@media print {{ body {{ print-color-adjust: exact; -webkit-print-color-adjust: exact; }} }}
</style></head>
<body data-gwo="0015O" data-invoice-template="{template}" data-ifg-bound="{bound_flag}"
      data-bg-sha="{bg_sha}" data-fields-sha="{fields_sha}">
{''.join(pages_html)}
</body></html>"""
    return LockedBindResult(
        html=html,
        plan=plan,
        overflows=overflows,
        qr_status=qr_status,
        summary_count=summary_count,
        payable_count=payable_count,
        qr_count=qr_count_total,
        background_sha256=bg_sha,
        fields_sha256=fields_sha,
    )
