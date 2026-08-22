# Fix: KSeF odrzuca FV sprzedaży — invalid child `P_11A` in `FaWiersz`

**Data:** 2026-05-22  
**Kontekst produkcji:** 10/12 FV sprzedaży `rejected` / `failed_permanent` z błędem schematu FA(3).

## Przyczyna

Generator FA(3) w `app/integrations/ksef/mapper.py` (`FA3Mapper.invoice_to_xml`) dla każdej pozycji emitował **jednocześnie**:

- `P_11` — wartość netto pozycji (standardowa sprzedaż opodatkowana)
- opcjonalnie `P_11Vat`
- **`P_11A`** — wartość brutto (tryb art. 106e ust. 7 i 8)
- `P_12` — stawka VAT

Według XSD FA(3) (`fa3.xsd`) pola `P_11` i `P_11A` są **alternatywą**, nie parą do użycia razem. Po `P_11` (lub `P_11Vat`) następny dozwolony element to `P_12`, nie `P_11A`.

Dla zwykłej krajowej FV VAT poprawna sekwencja w `FaWiersz`:

```
P_7 → P_8A → P_8B → P_9A → P_11 → P_12
```

(`P_11Vat` opcjonalnie tylko w przypadkach art. 106e ust. 10 — obecnie emitowane przy `vat_total > 0`; KSeF akceptuje ten wariant w testach XSD.)

## Zmiana

Usunięto linię:

```python
_el(row, "P_11A", _fmt(item.gross_total))
```

`P_11A` **nie jest emitowane** dla standardowej sprzedaży netto + stawka VAT. Tryb brutto (art. 106e ust. 7/8) nie jest obecnie używany przez IFG przy wystawianiu — gdyby był potrzebny w przyszłości, wymagałby osobnej gałęzi z `P_9B` + `P_11A` **zamiast** `P_9A` + `P_11`.

## Test regresyjny

`tests/unit/test_ksef_mapper.py::TestInvoiceItems::test_standard_vat_5_line_has_p11_p12_without_p11a`

- FV VAT 5% generuje `FaWiersz` z `P_11=200.00`, `P_12=5`
- brak elementu `P_11A`
- `P_11` przed `P_12`
- walidacja XSD FA(3) przechodzi

## Wynik testów

```text
pytest tests/unit/test_ksef_mapper.py \
       tests/unit/test_ksef_hardening.py \
       tests/unit/test_ksef_workflow_e2e.py -q

134 passed
```

## Zmienione pliki

- `app/integrations/ksef/mapper.py`
- `tests/unit/test_ksef_mapper.py`

Parser zakupów (`xml_parser.py`) — **bez zmian** (czyta `P_11A` z XML od dostawców).

## Po deployu — ponowienie wysyłki

**Tak — wymagane ręczne ponowienie** dla 10 odrzuconych FV sprzedaży:

1. Status faktur (`rejected` / `failed_permanent`) **nie jest zmieniany** przez ten fix.
2. Po deploy backendu z poprawionym generatorem XML użytkownik powinien **ponownie wysłać** każdą odrzuconą FV do KSeF (retry / nowa transmisja z UI).
3. Nowy XML będzie zgodny ze schematem; KSeF powinien zaakceptować faktury, o ile pozostałe dane są poprawne.

Nie wykonano masowej zmiany statusów ani danych produkcyjnych.
