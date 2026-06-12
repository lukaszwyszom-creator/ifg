from __future__ import annotations

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
