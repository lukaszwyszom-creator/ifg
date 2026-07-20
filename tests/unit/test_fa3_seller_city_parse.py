"""Testy mapowania FA(3) AdresL1/AdresL2 → seller_snapshot.city (GWO-IFG-0029)."""

from __future__ import annotations

from app.integrations.ksef.fa3_address import (
    extract_city_only_from_stored_address_fields,
    purchase_seller_city_integrity_error,
    split_fa3_address_lines,
)
from app.integrations.ksef.xml_parser import (
    parse_fa3_xml,
    purchase_seller_city_validation_error,
)


def _fa3_invoice_xml(*, seller_adres: str, seller_adres_l2: str = "") -> bytes:
    l2 = f"<AdresL2>{seller_adres_l2}</AdresL2>" if seller_adres_l2 else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Faktura xmlns="http://crd.gov.pl/wzor/2025/06/25/13775/">
  <Podmiot1>
    <DaneIdentyfikacyjne>
      <NIP>1112223344</NIP>
      <Nazwa>Testowy Sprzedawca Sp. z o.o.</Nazwa>
    </DaneIdentyfikacyjne>
    <Adres>
      <KodKraju>PL</KodKraju>
      <AdresL1>{seller_adres}</AdresL1>
      {l2}
    </Adres>
  </Podmiot1>
  <Podmiot2>
    <DaneIdentyfikacyjne>
      <NIP>9670402857</NIP>
      <Nazwa>Nabywca Testowy</Nazwa>
    </DaneIdentyfikacyjne>
    <Adres>
      <KodKraju>PL</KodKraju>
      <AdresL1>ul. Nabywcy 9, 00-001 Warszawa</AdresL1>
    </Adres>
  </Podmiot2>
  <Fa>
    <KodWaluty>PLN</KodWaluty>
    <P_1>2026-07-10</P_1>
    <P_2>FV/TEST/CITY/1</P_2>
    <P_13_1>100.00</P_13_1>
    <P_14_1>23.00</P_14_1>
    <P_15>123.00</P_15>
    <RodzajFaktury>VAT</RodzajFaktury>
    <FaWiersz>
      <NrWierszaFa>1</NrWierszaFa>
      <P_7>Usługa</P_7>
      <P_8A>szt.</P_8A>
      <P_8B>1</P_8B>
      <P_9A>100.00</P_9A>
      <P_11>100.00</P_11>
      <P_12>23</P_12>
    </FaWiersz>
  </Fa>
</Faktura>
""".encode()


def test_split_fa3_address_postal_city_in_adres_l1() -> None:
    result = split_fa3_address_lines(adres_l1="ul. Puławska 2 02-566 Warszawa")
    assert result["city"] == "Warszawa"
    assert result["postal_code"] == "02-566"
    assert result["street"] == "ul. Puławska 2"


def test_split_fa3_address_postal_city_in_adres_l2() -> None:
    result = split_fa3_address_lines(adres_l1="Wynalazek 1", adres_l2="02-677 Warszawa")
    assert result["city"] == "Warszawa"
    assert result["postal_code"] == "02-677"
    assert result["street"] == "Wynalazek 1"
    assert result["apartment_no"] == ""


def test_split_fa3_address_five_digit_postal() -> None:
    result = split_fa3_address_lines(adres_l1="UL. SZOSA GDAŃSKA 3, 86031 OSIELSKO")
    assert result["city"] == "OSIELSKO"
    assert result["postal_code"] == "86-031"


def test_split_fa3_address_prefers_structured_miejscowosc() -> None:
    result = split_fa3_address_lines(
        adres_l1="ul. X 1",
        structured_city="Kraków",
        structured_postal="30-001",
        structured_street="ul. X 1",
    )
    assert result["city"] == "Kraków"
    assert result["postal_code"] == "30-001"


def test_parse_fa3_xml_seller_city_from_real_fa3_adres_l1() -> None:
    parsed = parse_fa3_xml(
        _fa3_invoice_xml(seller_adres="Ks. Bp.K. Dominika 11, 83-130 Pelplin")
    )
    seller = parsed["seller_snapshot"]
    assert seller["city"] == "Pelplin"
    assert seller["postal_code"] == "83-130"
    assert "Pelplin" not in seller["street"]
    assert purchase_seller_city_validation_error(parsed) is None
    # brak regresji nabywcy
    assert parsed["buyer_snapshot"]["city"] == "Warszawa"
    assert parsed["buyer_snapshot"]["nip"] == "9670402857"


def test_parse_fa3_xml_seller_city_from_adres_l2() -> None:
    parsed = parse_fa3_xml(
        _fa3_invoice_xml(seller_adres="Wynalazek 1", seller_adres_l2="02-677 Warszawa")
    )
    seller = parsed["seller_snapshot"]
    assert seller["city"] == "Warszawa"
    assert seller["postal_code"] == "02-677"
    assert seller["street"] == "Wynalazek 1"
    assert seller["apartment_no"] == ""


def test_parse_fa3_xml_legacy_miejscowosc_still_works() -> None:
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<Faktura xmlns="http://crd.gov.pl/wzor/2025/06/25/13775/">
  <Podmiot1>
    <DaneIdentyfikacyjne>
      <NIP>1112223344</NIP>
      <Nazwa>Legacy Seller</Nazwa>
    </DaneIdentyfikacyjne>
    <Adres>
      <AdresL1>ul. Sprzedawcy 1</AdresL1>
      <KodPocztowy>00-001</KodPocztowy>
      <Miejscowosc>Warszawa</Miejscowosc>
      <KodKraju>PL</KodKraju>
    </Adres>
  </Podmiot1>
  <Podmiot2>
    <DaneIdentyfikacyjne>
      <NIP>9670402857</NIP>
      <Nazwa>Nabywca</Nazwa>
    </DaneIdentyfikacyjne>
  </Podmiot2>
  <Fa>
    <KodWaluty>PLN</KodWaluty>
    <P_1>2026-04-02</P_1>
    <P_2>FV/LEGACY/1</P_2>
    <P_15>10.00</P_15>
    <RodzajFaktury>VAT</RodzajFaktury>
  </Fa>
</Faktura>
"""
    parsed = parse_fa3_xml(xml)
    assert parsed["seller_snapshot"]["city"] == "Warszawa"
    assert parsed["seller_snapshot"]["postal_code"] == "00-001"


def test_integrity_error_when_source_has_city_but_snapshot_empty() -> None:
    err = purchase_seller_city_integrity_error(
        seller_snapshot={"name": "X", "city": ""},
        adres_l1="ul. Test 1, 00-001 Warszawa",
    )
    assert err is not None
    assert "seller_snapshot.city puste" in err


def test_integrity_ok_when_no_extractable_city() -> None:
    err = purchase_seller_city_integrity_error(
        seller_snapshot={"name": "X", "city": ""},
        adres_l1="Some Foreign Street 12",
        adres_l2="",
    )
    assert err is None


def test_backfill_extract_city_only_from_stored_fields() -> None:
    city = extract_city_only_from_stored_address_fields(
        street="ul. Puławska 2 02-566 Warszawa",
        apartment_no="",
        city="",
    )
    assert city == "Warszawa"
    # idempotencja — istniejące city bez zmian źródła
    assert (
        extract_city_only_from_stored_address_fields(
            street="ul. Puławska 2 02-566 Warszawa",
            city="Warszawa",
        )
        == "Warszawa"
    )
    assert (
        extract_city_only_from_stored_address_fields(
            street="Wynalazek 1",
            apartment_no="02-677 Warszawa",
            city="",
        )
        == "Warszawa"
    )
    assert (
        extract_city_only_from_stored_address_fields(
            street="Only street without postal",
            city="",
        )
        is None
    )
