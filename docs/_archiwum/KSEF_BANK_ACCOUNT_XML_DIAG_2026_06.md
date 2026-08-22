# KSeF FA(3) — rachunek bankowy w XML (diagnoza 2026-06-26)

## Problem

Kontrahenci pobierający faktury sprzedaży z KSeF nie widzą numeru rachunku bankowego sprzedawcy, mimo że PDF IFG pokazuje konto z ustawień firmy.

## Diagnoza

### Generator XML

- Plik: `app/integrations/ksef/mapper.py` (`FA3Mapper.invoice_to_xml`)
- Sekcja płatności: `_build_platnosc()` — przed poprawką zawierała tylko `TerminPlatnosci` i `FormaPlatnosci`, **bez** `RachunekBankowy`.

### Źródło rachunku w IFG

| Warstwa | Źródło |
|---------|--------|
| Ustawienia | `app_settings.seller_bank_account` / `SettingsService.get_settings()` |
| PDF sprzedaży | `resolve_seller_bank_account_for_render()` → ustawienia firmy |
| Snapshot sprzedawcy | `SettingsService.build_company_snapshot()` — **przed poprawką bez rachunku** |
| Odświeżenie przed wysyłką KSeF | `TransmissionService._refresh_sale_seller_snapshot()` nadpisuje `seller_snapshot` z `build_company_snapshot()` |

### Weryfikacja lokalna (przed fix)

Wygenerowano XML dla faktury z `seller_snapshot.bank_account = "12345678901234567890123456"`:

- Wynik: **`NrRB` / `RachunekBankowy` nie występują w XML** (`False` przy grep).
- Przyczyna: mapper ignorował rachunek niezależnie od snapshotu.

### Schemat FA(3)

Element zgodny ze schemą:

```xml
<Fa>
  <Platnosc>
    ...
    <RachunekBankowy>
      <NrRB>12345678901234567890123456</NrRB>
    </RachunekBankowy>
  </Platnosc>
</Fa>
```

- XSD: `fa3.xsd` → `Platnosc/RachunekBankowy` (`minOccurs="0"`, `maxOccurs="100"`)
- Typ `TNrRB`: string 10–34 znaków (26 cyfr PL OK)

## Poprawka

1. **`app/integrations/ksef/mapper.py`**
   - `_seller_bank_account_from_snapshot()` — klucze: `bank_account`, `bankAccount`, `nr_rb`, `NrRB`
   - `_build_platnosc()` — emituje `RachunekBankowy/NrRB` gdy rachunek jest w snapshot

2. **`app/services/settings_service.py`**
   - `build_company_snapshot()` — dodaje `bank_account` z `seller_bank_account`, aby wysyłka KSeF (refresh snapshot) przenosiła rachunek do XML

## Testy

| Test | Wynik |
|------|-------|
| `test_fa_platnosc_includes_nr_rb_from_seller_snapshot` | PASS + walidacja XSD |
| `test_fa_platnosc_omits_nr_rb_without_bank_in_snapshot` | PASS |
| `tests/unit/test_ksef_mapper.py` (całość) | PASS |
| `tests/unit/test_pdf_service.py` | PASS (9 testów, brak regresji PDF) |

## Deploy

- **Wymagany:** rebuild **api/worker** na DS723+ (tylko backend)
- **Nie wymagany:** `npm run build` (brak zmian frontend)
- **Uwaga:** faktury już wysłane do KSeF **bez** rachunku w XML nie zmienią się retroaktywnie; nowe wysyłki / korekty po deploy będą zawierać `NrRB`.

## Podsumowanie

| Pytanie | Odpowiedź |
|---------|-----------|
| Czy konto było w XML przed fix? | **Nie** |
| Czy konto jest w XML po fix? | **Tak** — `Fa/Platnosc/RachunekBankowy/NrRB` |
| Zgodność ze schemą FA(3)? | **Tak** |
