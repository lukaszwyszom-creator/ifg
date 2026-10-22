#!/usr/bin/env python3
"""GWO-0015O-A: KOR + normal FV control PNGs (production binder, no layout change)."""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.pdf_service import render_invoice_pdf  # noqa: E402
from app.services.sale_invoice_locked_bind import adapt_invoice_response_to_locked  # noqa: E402
from app.services.sale_invoice_locked_poc import sha256_file, _BG, _FIELDS, _PROFILE  # noqa: E402
from tests.unit.test_sale_invoice_production_bind_0015o import _short_items_invoice  # noqa: E402

OUT = Path("/Volumes/WorkspaceSSD/temp")
BANK = "12345678901234567890123456"
PDFIUM_PY = ROOT / ".venv_0015mb" / "bin" / "python"


def _pdf_page_to_png(pdf_path: Path, page_index: int, png_path: Path, *, scale: float = 2.0) -> None:
    """Convert via isolated pypdfium2 venv (avoid mixing site-packages)."""
    import subprocess

    code = (
        "import sys; from pathlib import Path; "
        "import pypdfium2 as pdfium; "
        f"pdf=pdfium.PdfDocument(sys.argv[1]); page=pdf[int(sys.argv[2])]; "
        f"page.render(scale={scale}).to_pil().convert('RGB').save(sys.argv[3]); pdf.close()"
    )
    subprocess.check_call(
        [str(PDFIUM_PY), "-c", code, str(pdf_path), str(page_index), str(png_path)]
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    bg_b, fields_b, prof_b = sha256_file(_BG), sha256_file(_FIELDS), sha256_file(_PROFILE)

    fv = _short_items_invoice(10, remaining=Decimal("400"))
    assert fv.invoice_type == "VAT"
    assert fv.remaining_amount == Decimal("400")
    assert fv.total_gross == Decimal("1050.00")

    kor = _short_items_invoice(10, remaining=Decimal("400"))
    kor.invoice_type = "KOR"
    kor.correction_reason = "Błąd stawki VAT"
    kor.number_local = "KOR/26/0010"

    model_fv = adapt_invoice_response_to_locked(fv, seller_bank_account=BANK)
    model_kor = adapt_invoice_response_to_locked(kor, seller_bank_account=BANK)
    assert model_fv.document_title == "FAKTURA VAT"
    assert model_kor.document_title == "FAKTURA KORYGUJĄCA"
    assert model_fv.remaining_amount == Decimal("400")
    assert model_kor.remaining_amount == Decimal("400")

    for label, inv, png_name in (
        ("FV", fv, "IFG-0015OA-FV-P1.png"),
        ("KOR", kor, "IFG-0015OA-KOR-P1.png"),
    ):
        pdf_bytes = render_invoice_pdf(inv, seller_bank_account=BANK)
        pdf_path = OUT / f"IFG-0015OA-{label}.pdf"
        pdf_path.write_bytes(pdf_bytes)
        png_path = OUT / png_name
        _pdf_page_to_png(pdf_path, 0, png_path)
        print(f"{label}: pdf={pdf_path} png={png_path} title={adapt_invoice_response_to_locked(inv).document_title}")

    bg_a, fields_a, prof_a = sha256_file(_BG), sha256_file(_FIELDS), sha256_file(_PROFILE)
    assert (bg_b, fields_b, prof_b) == (bg_a, fields_a, prof_a), "locked assets mutated"
    print("ASSET_SHA256_UNCHANGED=yes")
    print(f"FIELDS_SHA256={fields_a}")
    print(f"REMAINING_400_SOURCE=explicit remaining_amount=400 on 10x105 fixture (total_gross=1050)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
