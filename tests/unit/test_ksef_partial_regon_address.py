"""Regresje AdresL1 / częściowy adres REGON (GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0001)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4
from unittest.mock import MagicMock

import pytest

from app.domain.enums import InvoiceStatus
from app.domain.exceptions import InvalidInvoiceError
from app.domain.models.invoice import Invoice, InvoiceItem
from app.domain.party_address import can_build_adres_l1, format_adres_l1
from app.integrations.ksef.mapper import KSeFMapper
from app.persistence.mappers.invoice_mapper import InvoiceMapper
from app.services.contractor_service import ContractorService


def _party(**kwargs):
    base = {
        "nip": "1000000070",
        "name": "Firma Test",
        "country": "PL",
    }
    base.update(kwargs)
    return base


class TestFormatAdresL1:
    def test_standard_street_address(self):
        line = format_adres_l1(
            _party(street="ul. Testowa", building_no="10", postal_code="00-001", city="Warszawa")
        )
        assert line == "ul. Testowa 10, 00-001 Warszawa"

    def test_village_without_street_uses_city_and_building(self):
        line = format_adres_l1(
            _party(street=None, building_no="10", postal_code="98-331", city="Prusicko")
        )
        assert line == "Prusicko 10, 98-331 Prusicko"

    def test_place_name_as_street(self):
        line = format_adres_l1(
            _party(street="Moczydła", building_no="2", postal_code="98-331", city="Prusicko")
        )
        assert line == "Moczydła 2, 98-331 Prusicko"


class TestCanBuildAdresL1:
    def test_full_standard_pass(self):
        assert can_build_adres_l1(
            _party(street="ul. Testowa", building_no="10", postal_code="00-001", city="Warszawa")
        )

    def test_missing_street_but_building_and_locality_pass(self):
        assert can_build_adres_l1(
            _party(street=None, building_no="10", postal_code="98-331", city="Prusicko")
        )

    def test_only_postal_and_city_block(self):
        assert not can_build_adres_l1(
            _party(street=None, building_no=None, postal_code="98-331", city="Prusicko")
        )

    def test_missing_postal_block(self):
        assert not can_build_adres_l1(
            _party(street="ul. X", building_no="1", postal_code=None, city="Warszawa")
        )

    def test_literal_none_street_treated_as_empty(self):
        line = format_adres_l1(
            _party(street="None", building_no="10", postal_code="98-331", city="Prusicko")
        )
        assert line == "Prusicko 10, 98-331 Prusicko"
        assert "None" not in line


def _sale_invoice(buyer_snapshot: dict) -> Invoice:
    now = datetime.now(UTC)
    item = InvoiceItem(
        name="Pozycja",
        quantity=Decimal("1"),
        unit="szt.",
        unit_price_net=Decimal("100"),
        vat_rate=Decimal("23"),
        net_total=Decimal("100"),
        vat_total=Decimal("23"),
        gross_total=Decimal("123"),
        sort_order=0,
    )
    return Invoice(
        id=uuid4(),
        status=InvoiceStatus.READY_FOR_SUBMISSION,
        direction="sale",
        issue_date=now.date(),
        sale_date=now.date(),
        currency="PLN",
        number_local="FV/1/09/2026",
        seller_snapshot=_party(
            nip="9670402857",
            name="Sprzedawca",
            street="ul. S",
            building_no="1",
            postal_code="00-001",
            city="Warszawa",
        ),
        buyer_snapshot=buyer_snapshot,
        items=[item],
        total_net=Decimal("100"),
        total_vat=Decimal("23"),
        total_gross=Decimal("123"),
        created_at=now,
        updated_at=now,
    )


class TestSaleValidationPartialAddress:
    def test_full_address_pass(self):
        inv = _sale_invoice(
            _party(street="ul. Testowa", building_no="10", postal_code="00-001", city="Warszawa")
        )
        inv.validate_sale_formal_requirements(require_number_local=True)

    def test_no_street_with_building_pass(self):
        inv = _sale_invoice(
            _party(street=None, building_no="10", postal_code="98-331", city="Prusicko")
        )
        inv.validate_sale_formal_requirements(require_number_local=True)

    def test_insufficient_address_block(self):
        inv = _sale_invoice(
            _party(street=None, building_no=None, postal_code="98-331", city="Prusicko")
        )
        with pytest.raises(InvalidInvoiceError, match="adresowych"):
            inv.validate_sale_formal_requirements(require_number_local=True)


class TestFa3BuyerAdresL1:
    def _xml_adres(self, buyer: dict):
        xml = KSeFMapper.invoice_to_xml(_sale_invoice(buyer))
        from lxml import etree

        root = etree.fromstring(xml)
        ns = {"fa": "http://crd.gov.pl/wzor/2025/06/25/13775/"}
        adres = root.find(".//fa:Podmiot2/fa:Adres", ns)
        assert adres is not None
        return (
            adres.findtext("fa:KodKraju", namespaces=ns),
            adres.findtext("fa:AdresL1", namespaces=ns),
        )

    def test_standard_adres_l1(self):
        country, l1 = self._xml_adres(
            _party(street="ul. Testowa", building_no="10", postal_code="00-001", city="Warszawa")
        )
        assert country == "PL"
        assert l1 == "ul. Testowa 10, 00-001 Warszawa"

    def test_village_adres_l1(self):
        country, l1 = self._xml_adres(
            _party(street=None, building_no="10", postal_code="98-331", city="Prusicko")
        )
        assert country == "PL"
        assert l1 == "Prusicko 10, 98-331 Prusicko"

    def test_moczydla_adres_l1(self):
        country, l1 = self._xml_adres(
            _party(street="Moczydła", building_no="2", postal_code="98-331", city="Prusicko")
        )
        assert country == "PL"
        assert l1 == "Moczydła 2, 98-331 Prusicko"


class TestManualOverridePrecedence:
    def test_snapshot_prefers_override_over_incomplete_regon(self):
        contractor = MagicMock()
        contractor.nip = "5741680143"
        contractor.regon = "123"
        contractor.krs = None
        contractor.name = "REGON NAME"
        contractor.legal_form = None
        contractor.street = None
        contractor.building_no = None
        contractor.apartment_no = None
        contractor.postal_code = "98-331"
        contractor.city = "Prusicko"
        contractor.voivodeship = None
        contractor.county = None
        contractor.commune = None
        contractor.country = "PL"

        override = MagicMock()
        override.is_active = True
        override.name = None
        override.legal_form = None
        override.street = None
        override.building_no = "10"
        override.apartment_no = None
        override.postal_code = None
        override.city = None
        override.voivodeship = None
        override.county = None
        override.commune = None

        snap = InvoiceMapper.build_contractor_snapshot(contractor, override)
        assert snap["building_no"] == "10"
        assert snap["city"] == "Prusicko"
        assert snap["postal_code"] == "98-331"
        assert can_build_adres_l1(snap)
        assert format_adres_l1(snap) == "Prusicko 10, 98-331 Prusicko"

    def test_build_response_keeps_override_after_empty_regon_fields(self):
        contractor = MagicMock()
        contractor.id = uuid4()
        contractor.nip = "5741680143"
        contractor.regon = None
        contractor.krs = None
        contractor.name = "Firma"
        contractor.legal_form = None
        contractor.street = None
        contractor.building_no = None
        contractor.apartment_no = None
        contractor.postal_code = "98-331"
        contractor.city = "Prusicko"
        contractor.voivodeship = None
        contractor.county = None
        contractor.commune = None
        contractor.country = "PL"
        contractor.status = None
        contractor.source = "regon"
        contractor.source_fetched_at = None
        contractor.cache_valid_until = None
        contractor.lookup_last_status = "success"
        contractor.lookup_last_error = None

        override = MagicMock()
        override.street = "Moczydła"
        override.building_no = "2"
        override.apartment_no = None
        override.postal_code = "98-331"
        override.city = "Prusicko"
        for attr in ("name", "legal_form", "county", "commune", "voivodeship"):
            setattr(override, attr, None)

        service = ContractorService(
            session=MagicMock(),
            contractor_repository=MagicMock(),
            contractor_override_repository=MagicMock(),
            audit_service=MagicMock(),
            regon_client=MagicMock(),
            regon_mapper=MagicMock(),
        )
        response = service._build_response(contractor, override)
        assert response["street"] == "Moczydła"
        assert response["building_no"] == "2"
        assert response["source"] == "regon_with_override"
        assert can_build_adres_l1(response)
