from __future__ import annotations

from decimal import Decimal

from app.integrations.ksef.xml_parser import parse_fa3_xml


def test_parse_fa3_xml_reads_nested_identity_and_due_date() -> None:
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<Faktura xmlns="http://crd.gov.pl/wzor/2025/06/25/13775/">
  <Podmiot1>
    <Sprzedawca>
      <DaneIdentyfikacyjne>
        <NIP>1112223344</NIP>
        <Nazwa>Testowy Sprzedawca Sp. z o.o.</Nazwa>
      </DaneIdentyfikacyjne>
      <Adres>
        <AdresL1>ul. Sprzedawcy 1</AdresL1>
        <KodPocztowy>00-001</KodPocztowy>
        <Miejscowosc>Warszawa</Miejscowosc>
        <KodKraju>PL</KodKraju>
      </Adres>
    </Sprzedawca>
  </Podmiot1>
  <Podmiot2>
    <Nabywca>
      <DaneIdentyfikacyjne>
        <NIP>9670402857</NIP>
        <Nazwa>Nabywca Testowy</Nazwa>
      </DaneIdentyfikacyjne>
    </Nabywca>
  </Podmiot2>
  <Fa>
    <KodWaluty>PLN</KodWaluty>
    <P_1>2026-04-02</P_1>
    <P_1M>2026-04-02</P_1M>
    <P_2>FV/TEST/1</P_2>
    <P_13_1>100.00</P_13_1>
    <P_14_1>23.00</P_14_1>
    <P_15>123.00</P_15>
    <RodzajFaktury>VAT</RodzajFaktury>
    <Platnosc>
      <TerminPlatnosci>
        <Termin>2026-04-16</Termin>
      </TerminPlatnosci>
    </Platnosc>
  </Fa>
</Faktura>
"""

    parsed = parse_fa3_xml(xml)

    assert parsed["seller_snapshot"]["nip"] == "1112223344"
    assert parsed["seller_snapshot"]["name"] == "Testowy Sprzedawca Sp. z o.o."
    assert parsed["buyer_snapshot"]["nip"] == "9670402857"
    assert parsed["number_local"] == "FV/TEST/1"
    assert parsed["due_date"] == "2026-04-16"


def test_parse_fa3_xml_sale_date_uses_p6_not_p1m_place_of_issue() -> None:
    """P_1M to miejscowość wystawienia (np. Warszawa), nie data sprzedaży."""
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<Faktura xmlns="http://crd.gov.pl/wzor/2025/06/25/13775/">
  <Podmiot1>
    <DaneIdentyfikacyjne>
      <NIP>1112223344</NIP>
      <Nazwa>Sprzedawca SA</Nazwa>
    </DaneIdentyfikacyjne>
  </Podmiot1>
  <Podmiot2>
    <DaneIdentyfikacyjne>
      <NIP>9670402857</NIP>
      <Nazwa>Nabywca Sp. z o.o.</Nazwa>
    </DaneIdentyfikacyjne>
  </Podmiot2>
  <Fa>
    <KodWaluty>PLN</KodWaluty>
    <P_1>2026-05-10</P_1>
    <P_1M>Warszawa</P_1M>
    <P_2>FV/KSEF/1</P_2>
    <P_6>2026-05-08</P_6>
    <P_13_1>100.00</P_13_1>
    <P_14_1>23.00</P_14_1>
    <P_15>123.00</P_15>
    <RodzajFaktury>VAT</RodzajFaktury>
  </Fa>
</Faktura>
"""

    parsed = parse_fa3_xml(xml)

    assert parsed["issue_date"] == "2026-05-10"
    assert parsed["sale_date"] == "2026-05-08"
    assert parsed["sale_date"] != "Warszawa"

    from datetime import date

    date.fromisoformat(parsed["sale_date"])


def test_parse_fa3_xml_reads_gross_line_fields_p11a_p9b() -> None:
    """FA(3) art. 106e ust. 7/8: pozycja z P_11A/P_9B zamiast P_11/P_9A."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Faktura xmlns="http://crd.gov.pl/wzor/2025/06/25/13775/">
  <Podmiot1>
    <DaneIdentyfikacyjne>
      <NIP>1112223344</NIP>
      <Nazwa>Biuro Rachunkowe</Nazwa>
    </DaneIdentyfikacyjne>
  </Podmiot1>
  <Podmiot2>
    <DaneIdentyfikacyjne>
      <NIP>9670402857</NIP>
      <Nazwa>Nabywca</Nazwa>
    </DaneIdentyfikacyjne>
  </Podmiot2>
  <Fa>
    <KodWaluty>PLN</KodWaluty>
    <P_1>2026-05-01</P_1>
    <P_2>FV/KS/1</P_2>
    <P_13_1>219.51</P_13_1>
    <P_14_1>50.49</P_14_1>
    <P_15>270.00</P_15>
    <RodzajFaktury>VAT</RodzajFaktury>
    <FaWiersz>
      <P_7>Usługi księgowe</P_7>
      <P_8A>mies</P_8A>
      <P_8B>1</P_8B>
      <P_9B>270.00</P_9B>
      <P_11A>270.00</P_11A>
      <P_12>23</P_12>
    </FaWiersz>
  </Fa>
</Faktura>
""".encode("utf-8")

    parsed = parse_fa3_xml(xml)

    assert parsed["total_gross"] == parsed["items"][0]["gross_total"]
    item = parsed["items"][0]
    assert item["name"] == "Usługi księgowe"
    assert item["net_total"] == Decimal("219.51")
    assert item["vat_total"] == Decimal("50.49")
    assert item["gross_total"] == Decimal("270.00")
    assert item["unit_price_net"] == Decimal("219.51")


def test_purchase_items_validation_error_when_totals_without_line_amounts() -> None:
    from app.integrations.ksef.xml_parser import purchase_items_validation_error

    parsed = {
        "total_gross": Decimal("270.00"),
        "items": [
            {
                "name": "Usługi księgowe",
                "net_total": Decimal("0"),
                "vat_total": Decimal("0"),
                "gross_total": Decimal("0"),
            }
        ],
    }

    assert purchase_items_validation_error(parsed) is not None


def test_parse_fa3_xml_totals_fallback_from_items_when_header_p13_missing() -> None:
    """Nagłówek ma tylko P_15; net/VAT liczone z pozycji P_11A/P_9B."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Faktura xmlns="http://crd.gov.pl/wzor/2025/06/25/13775/">
  <Podmiot1>
    <DaneIdentyfikacyjne>
      <NIP>1112223344</NIP>
      <Nazwa>Biuro Rachunkowe</Nazwa>
    </DaneIdentyfikacyjne>
  </Podmiot1>
  <Podmiot2>
    <DaneIdentyfikacyjne>
      <NIP>9670402857</NIP>
      <Nazwa>Nabywca</Nazwa>
    </DaneIdentyfikacyjne>
  </Podmiot2>
  <Fa>
    <KodWaluty>PLN</KodWaluty>
    <P_1>2026-05-01</P_1>
    <P_2>FV/KS/2</P_2>
    <P_15>270.00</P_15>
    <RodzajFaktury>VAT</RodzajFaktury>
    <FaWiersz>
      <P_7>Usługi księgowe</P_7>
      <P_8A>mies</P_8A>
      <P_8B>1</P_8B>
      <P_9B>270.00</P_9B>
      <P_11A>270.00</P_11A>
      <P_12>23</P_12>
    </FaWiersz>
  </Fa>
</Faktura>
""".encode("utf-8")

    parsed = parse_fa3_xml(xml)

    assert parsed["total_net"] == Decimal("219.51")
    assert parsed["total_vat"] == Decimal("50.49")
    assert parsed["total_gross"] == Decimal("270.00")


def test_parse_fa3_xml_header_totals_not_overwritten_by_item_fallback() -> None:
    """Poprawne P_13/P_14/P_15 w nagłówku nie są nadpisywane sumą pozycji."""
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<Faktura xmlns="http://crd.gov.pl/wzor/2025/06/25/13775/">
  <Podmiot1>
    <DaneIdentyfikacyjne>
      <NIP>1112223344</NIP>
      <Nazwa>Sprzedawca</Nazwa>
    </DaneIdentyfikacyjne>
  </Podmiot1>
  <Podmiot2>
    <DaneIdentyfikacyjne>
      <NIP>9670402857</NIP>
      <Nazwa>Nabywca</Nazwa>
    </DaneIdentyfikacyjne>
  </Podmiot2>
  <Fa>
    <KodWaluty>PLN</KodWaluty>
    <P_1>2026-05-01</P_1>
    <P_2>FV/STD/1</P_2>
    <P_13_1>100.00</P_13_1>
    <P_14_1>23.00</P_14_1>
    <P_15>123.00</P_15>
    <RodzajFaktury>VAT</RodzajFaktury>
    <FaWiersz>
      <P_7>Towar</P_7>
      <P_8B>1</P_8B>
      <P_9A>100.00</P_9A>
      <P_11>100.00</P_11>
      <P_12>23</P_12>
    </FaWiersz>
  </Fa>
</Faktura>
"""

    parsed = parse_fa3_xml(xml)

    assert parsed["total_net"] == Decimal("100.00")
    assert parsed["total_vat"] == Decimal("23.00")
    assert parsed["total_gross"] == Decimal("123.00")


def test_parse_fa3_xml_gross_unit_price_uses_line_gross_as_source() -> None:
    """P_9B + ilość: brutto pozycji liczone z ceny brutto × qty, nie z zaokr. netto × qty."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Faktura xmlns="http://crd.gov.pl/wzor/2025/06/25/13775/">
  <Podmiot1><DaneIdentyfikacyjne><NIP>1112223344</NIP><Nazwa>S</Nazwa></DaneIdentyfikacyjne></Podmiot1>
  <Podmiot2><DaneIdentyfikacyjne><NIP>9670402857</NIP><Nazwa>B</Nazwa></DaneIdentyfikacyjne></Podmiot2>
  <Fa>
    <KodWaluty>PLN</KodWaluty>
    <P_1>2026-05-01</P_1>
    <P_2>FV/G/1</P_2>
    <P_15>7200.00</P_15>
    <RodzajFaktury>VAT</RodzajFaktury>
    <FaWiersz>
      <P_7>Towar</P_7>
      <P_8B>60</P_8B>
      <P_9B>120.00</P_9B>
      <P_12>5</P_12>
    </FaWiersz>
  </Fa>
</Faktura>
""".encode("utf-8")

    parsed = parse_fa3_xml(xml)
    item = parsed["items"][0]

    assert item["gross_total"] == Decimal("7200.00")
    assert item["net_total"] == Decimal("6857.14")
    assert item["vat_total"] == Decimal("342.86")
