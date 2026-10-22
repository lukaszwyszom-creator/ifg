"""GWO-0015N locked underlay binder — smoke tests."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from PIL import Image

from app.services.sale_invoice_locked_poc import (
    _ASSETS,
    _BG,
    _FIELDS,
    build_fixture,
    geometry_from_profile,
    load_binding_profile,
    load_fields,
    render_locked_invoice,
    sha256_file,
)


def test_assets_present_and_size() -> None:
    assert _BG.exists()
    assert _FIELDS.exists()
    assert (_ASSETS / "stained_glass_current.png").exists()
    assert (_ASSETS / "stained_glass_module.json").exists()
    assert (_ASSETS / "sale_invoice_binding_profile.json").exists()
    assert Image.open(_BG).size == (1024, 1536)


def test_binding_profile_from_fields() -> None:
    fields = load_fields()
    profile = load_binding_profile()
    assert profile["TABLE_LEFT_PX"] == fields["fields"]["items"]["rect"][0]
    assert profile["TABLE_RIGHT_PX"] == fields["fields"]["items"]["rect"][2]
    assert profile["TABLE_ITEMS_TOP_PX"] == fields["fields"]["items"]["rect"][1]
    assert profile["SUMMARY_TOP_PX"] == fields["fields"]["vat_summary"]["rect"][1]
    assert profile["KSEF_TOP_PX"] == fields["fields"]["ksef_qr"]["rect"][1]
    assert profile["A4_MAPPING"]["MASTER_OFFSET_X_MM"] == 6
    geom = geometry_from_profile(profile)
    assert geom.table_top_first == profile["TABLE_ITEMS_TOP_PX"]
    assert geom.table_top_continuation < geom.table_top_first


def test_render_one_and_ten_invariants() -> None:
    for n, rem in [(1, Decimal("105")), (8, Decimal("400")), (10, Decimal("400")), (50, None)]:
        bound = render_locked_invoice(build_fixture(n, remaining=rem))
        assert bound.summary_count == 1
        assert bound.payable_count == 1
        assert bound.qr_count <= 1
        flat = [r.lp for p in bound.plan.pages for r in p.rows]
        assert flat == list(range(1, n + 1))
        assert "stained_glass" in bound.html
        assert 'data-layer="background"' in bound.html
        assert bound.qr_status == "INCOMPLETE"


def test_remaining_amount_variants() -> None:
    a = render_locked_invoice(build_fixture(3, remaining=None))
    b = render_locked_invoice(build_fixture(3, remaining=Decimal("0")))
    c = render_locked_invoice(build_fixture(3, remaining=Decimal("50.00")))
    assert a.payable_count == b.payable_count == c.payable_count == 1


def test_immutability_of_assets() -> None:
    before_bg = sha256_file(_BG)
    before_fields = sha256_file(_FIELDS)
    render_locked_invoice(build_fixture(5, remaining=Decimal("10")))
    assert sha256_file(_BG) == before_bg
    assert sha256_file(_FIELDS) == before_fields
