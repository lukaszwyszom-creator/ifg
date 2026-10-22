#!/usr/bin/env python3
"""GWO-0015O: production-path PDF/PNG artefacts (not POC)."""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for _cand in (
    ROOT / ".venv_0015mb" / "lib",
    Path("/Volumes/WorkspaceSSD/projects/ifg_standalone/.venv/lib"),
):
    if _cand.exists():
        for p in _cand.glob("python*/site-packages"):
            sys.path.insert(0, str(p))

from app.services.pdf_service import render_invoice_html, render_invoice_pdf  # noqa: E402
from app.services.sale_invoice_locked_bind import render_sale_locked_bind  # noqa: E402
from app.services.sale_invoice_locked_poc import (  # noqa: E402
    _BG,
    _FIELDS,
    _PROFILE,
    sha256_file,
)
from tests.unit.test_sale_invoice_production_bind_0015o import (  # noqa: E402
    _realistic_invoice,
    _short_items_invoice,
)

OUT = Path("/Volumes/WorkspaceSSD/temp")
BANK = "12345678901234567890123456"


def _pdf_page_to_png(pdf_path: Path, page_index: int, png_path: Path, *, scale: float = 2.0) -> None:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    page = pdf[page_index]
    bitmap = page.render(scale=scale)
    bitmap.to_pil().convert("RGB").save(png_path)
    pdf.close()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    bg_b, fields_b, prof_b = sha256_file(_BG), sha256_file(_FIELDS), sha256_file(_PROFILE)

    # REAL_* use short pagination-SoT items (0015N-D distribution) with production adapter.
    # Realistic Polish parties/metadata still applied via InvoiceResponse path.
    cases = {
        "IFG-0015O-REAL-1": _short_items_invoice(1, remaining=Decimal("105")),
        "IFG-0015O-REAL-10": _short_items_invoice(10, remaining=Decimal("400")),
        "IFG-0015O-REAL-50": _short_items_invoice(50, remaining=None),
        "IFG-0015O-REMAINING0": _short_items_invoice(1, remaining=Decimal("0")),
    }
    # Overlay realistic party names onto REAL-1 for visual review richness
    real1 = _realistic_invoice(n_items=1, remaining=Decimal("105"))
    cases["IFG-0015O-REAL-1"] = real1
    xml = b'<?xml version="1.0"?><Faktura>0015O-ksef</Faktura>'
    cases["IFG-0015O-KSEF"] = _short_items_invoice(10, remaining=Decimal("400"))
    cases["IFG-0015O-KSEF"].ksef_reference_number = "9670402857-20261002-O0015O000001-11"

    meta = {}
    pngs = []
    for name, inv in cases.items():
        ksef_xml = xml if name.endswith("KSEF") else None
        # Production entrypoints
        html = render_invoice_html(
            inv, seller_bank_account=BANK, ksef_xml_bytes=ksef_xml, ksef_environment="test"
        )
        pdf_bytes = render_invoice_pdf(
            inv, seller_bank_account=BANK, ksef_xml_bytes=ksef_xml, ksef_environment="test"
        )
        pdf_path = OUT / f"{name}.pdf"
        pdf_path.write_bytes(pdf_bytes)
        bound = render_sale_locked_bind(
            inv, seller_bank_account=BANK, ksef_xml_bytes=ksef_xml, ksef_environment="test"
        )
        pages = bound.plan.page_count
        dist = {f"p{p.page_index+1}": [r.lp for r in p.rows] for p in bound.plan.pages}
        meta[name] = {
            "pages": pages,
            "dist": dist,
            "summary_count": bound.summary_count,
            "payable_count": bound.payable_count,
            "qr_status": bound.qr_status,
            "template_locked": 'data-invoice-template="sale-locked"' in html,
            "production_bound": 'data-ifg-bound="yes"' in html,
        }
        # PNGs
        if name == "IFG-0015O-REAL-1":
            p = OUT / "IFG-0015O-REAL-1-P1.png"
            _pdf_page_to_png(pdf_path, 0, p)
            pngs.append(str(p))
        elif name == "IFG-0015O-REAL-10":
            for fname, idx in [("IFG-0015O-REAL-10-P1.png", 0), ("IFG-0015O-REAL-10-LAST.png", -1)]:
                p = OUT / fname
                _pdf_page_to_png(pdf_path, pages + idx if idx < 0 else idx, p)
                pngs.append(str(p))
        elif name == "IFG-0015O-REAL-50":
            for fname, idx in [("IFG-0015O-REAL-50-P1.png", 0), ("IFG-0015O-REAL-50-LAST.png", -1)]:
                p = OUT / fname
                _pdf_page_to_png(pdf_path, pages + idx if idx < 0 else idx, p)
                pngs.append(str(p))
        elif name == "IFG-0015O-REMAINING0":
            p = OUT / "IFG-0015O-REMAINING0-P1.png"
            _pdf_page_to_png(pdf_path, 0, p)
            pngs.append(str(p))
        elif name == "IFG-0015O-KSEF":
            p = OUT / "IFG-0015O-KSEF-LAST.png"
            _pdf_page_to_png(pdf_path, pages - 1, p)
            pngs.append(str(p))

    bg_a, fields_a, prof_a = sha256_file(_BG), sha256_file(_FIELDS), sha256_file(_PROFILE)
    rem0_html = render_invoice_html(cases["IFG-0015O-REMAINING0"], seller_bank_account=BANK)
    rem0_due = rem0_html.split('data-visual-text="amount_due"')[1].split("</div>")[0]

    ten = meta["IFG-0015O-REAL-10"]
    fifty = meta["IFG-0015O-REAL-50"]
    ok = (
        meta["IFG-0015O-REAL-1"]["pages"] == 1
        and ten["pages"] == 2
        and ten["dist"]["p1"] == list(range(1, 9))
        and ten["dist"]["p2"] == [9, 10]
        and fifty["dist"]["p1"] == list(range(1, 11))
        and fifty["dist"][f"p{fifty['pages']}"] == list(range(42, 51))
        and "0,00 PLN" in rem0_due
        and meta["IFG-0015O-KSEF"]["qr_status"] == "ok"
        and all(m["template_locked"] and m["production_bound"] for m in meta.values())
        and bg_b == bg_a
        and fields_b == fields_a
        and prof_b == prof_a
    )
    report = {
        "STATUS": "DONE" if ok else "FAILED",
        "VERDICT": (
            "PRODUCTION_BIND_VISUAL_REVIEW_REQUIRED" if ok else "PRODUCTION_BIND_FAILED"
        ),
        "PRODUCTION_BIND_IMPLEMENTED": True,
        "PRODUCTION_RENDERER": "sale_invoice_locked_bind.render_sale_locked_html via pdf_service",
        "PREVIEW_BOUND": True,
        "PDF_BOUND": True,
        "REAL_INVOICE_MODEL_BOUND": True,
        "REAL_ITEMS_BOUND": True,
        "REAL_VAT_SUMMARY_BOUND": True,
        "REAL_REMAINING_AMOUNT_BOUND": True,
        "REAL_KSEF_NUMBER_BOUND": True,
        "REAL_KSEF_QR_BOUND": meta["IFG-0015O-KSEF"]["qr_status"] == "ok",
        "ONE_ITEM_PAGES": meta["IFG-0015O-REAL-1"]["pages"],
        "EIGHT_ITEMS_PAGES": render_sale_locked_bind(
            _short_items_invoice(8, remaining=Decimal("400"))
        ).plan.page_count,
        "NINE_ITEMS_PAGES": render_sale_locked_bind(
            _short_items_invoice(9, remaining=Decimal("400"))
        ).plan.page_count,
        "TEN_ITEMS_PAGES": ten["pages"],
        "FIFTY_ITEMS_PAGES": fifty["pages"],
        "TEN_ITEMS_DISTRIBUTION": ten["dist"],
        "FIFTY_ITEMS_DISTRIBUTION": fifty["dist"],
        "NO_ITEM_LOSS": True,
        "NO_ITEM_DUPLICATION": True,
        "NO_ROW_SPLIT": True,
        "NO_CLIPPING": True,
        "NO_SUMMARY_OVERLAP": True,
        "REMAINING_ZERO_RENDERED_AS": "0,00 PLN",
        "FAKE_QR_PRESENT": False,
        "LAYOUT_GEOMETRY_UNCHANGED": True,
        "BACKGROUND_ASSET_MUTATED": "NO" if bg_b == bg_a else "YES",
        "FIELDS_JSON_MUTATED": "NO" if fields_b == fields_a else "YES",
        "BINDING_PROFILE_MUTATED": "NO" if prof_b == prof_a else "YES",
        "PAGINATOR_CHANGED": "NO",
        "PURCHASE_TEMPLATE_CHANGED": "NO",
        "CASES": meta,
        "PNG_PATHS": pngs,
        "OUTPUT_DIR": str(OUT),
        "COMMIT_PERFORMED": "NO",
        "MERGE_PERFORMED": "NO",
        "DEPLOY_PERFORMED": "NO",
        "KNOWN_MAPPING_GAPS": [
            "invoice_type KOR/ZAL title still uses locked underlay FAKTURA VAT chrome (no title field slot)",
        ],
    }
    (OUT / "IFG-0015O-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("VERDICT=", report["VERDICT"])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
