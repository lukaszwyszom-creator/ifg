# KSeF FA(3) — weryfikacja rachunku bankowego przed deployem (2026-06-26)

## 1. Wygenerowany XML — faktura sprzedaży z rachunkiem

Źródło: faktura sprzedaży `FV/VERIFY/04/2026` (syntetyczna, snapshot sprzedawcy jak po `build_company_snapshot()` z ustawionym `seller_bank_account`).

### Fragment `<Platnosc>`

```xml
<Platnosc>
    <TerminPlatnosci>
        <Termin>2026-04-19</Termin>
    </TerminPlatnosci>
    <FormaPlatnosci>6</FormaPlatnosci>
    <RachunekBankowy>
        <NrRB>61114010140000310278885108</NrRB>
    </RachunekBankowy>
</Platnosc>
```

(W wygenerowanym pliku elementy mają prefiks namespace `fa:` — semantycznie identyczna struktura.)

## 2. Struktura

| Kryterium | Wynik |
|-----------|-------|
| `RachunekBankowy` wewnątrz `Platnosc` | TAK |
| `NrRB` jako bezpośrednie dziecko `RachunekBankowy` | TAK |
| Kolejność: `FormaPlatnosci` przed `RachunekBankowy` | TAK |
| Wartość `NrRB`: 26 cyfr (znormalizowany IBAN PL) | TAK |

## 3. Walidacja XSD FA(3)

| Test | Wynik |
|------|-------|
| `KSeFMapper.validate_xml_against_xsd(xml)` | **PASS** |

Plik schematu: `app/integrations/ksef/fa3.xsd`

## 4. Ścieżka danych IFG → XML

```
app_settings.seller_bank_account          (DB / env via SettingsService._merge)
        ↓
SettingsService.get_settings()["seller_bank_account"]
        ↓
SettingsService.build_company_snapshot() → snapshot["bank_account"]
        ↓
TransmissionService._refresh_sale_seller_snapshot() → invoice.seller_snapshot
        ↓
FA3Mapper._seller_bank_account_from_snapshot()  (klucze: bank_account, bankAccount, nr_rb, NrRB)
        ↓
FA3Mapper._build_platnosc() → Fa/Platnosc/RachunekBankowy/NrRB
```

PDF sprzedaży korzysta równolegle z tego samego pola ustawień (`resolve_seller_bank_account_for_render` → `seller_bank_account`), nie z XML.

## 5. Faktura bez rachunku

Snapshot sprzedawcy bez kluczy `bank_account` / `bankAccount` / `nr_rb` / `NrRB`:

| Element | Obecny w XML |
|---------|--------------|
| `RachunekBankowy` | **NIE** |

## 6. Testy jednostkowe (stan aktualny)

| Suite | Wynik |
|-------|-------|
| `tests/unit/test_ksef_mapper.py` | 91 passed |
| `test_fa_platnosc_includes_nr_rb_from_seller_snapshot` | PASS |
| `test_fa_platnosc_omits_nr_rb_without_bank_in_snapshot` | PASS |

## 7. Gotowość do wdrożenia

**TAK** — poprawka jest gotowa do wdrożenia (rebuild api/worker na DS723+).

Uwaga: faktury już opublikowane w KSeF przed deployem nie zostaną zaktualizowane; rachunek pojawi się w XML nowych wysyłek.
