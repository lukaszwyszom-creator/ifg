# FV — kalkulacja pozycji w trybie ceny brutto

**Data:** 2026-06-13  
**Problem:** cena brutto 120,00 × 60 szt., VAT 5% → błędne brutto 7200,27 (przeliczanie przez zaokrąglone netto jednostkowe).

---

## Przyczyna

W trybie brutto system wyliczał `unit_price_net = gross / (1+VAT)`, zaokrąglał, mnożył przez ilość i dopiero wtedy liczył VAT — zamiast traktować **kwotę brutto pozycji** jako źródło prawdy.

---

## Model (po fixie)

### Tryb netto (`price_mode=net`)
- `net_amount = unit_price_net × quantity`
- `vat_amount = net_amount × VAT`
- `gross_amount = net_amount + vat_amount`

### Tryb brutto (`price_mode=gross`)
- `gross_amount = unit_price_gross × quantity` (zaokr. 2 miejsca)
- `net_amount = gross_amount / (1 + VAT)` (zaokr. 2 miejsca)
- `vat_amount = gross_amount - net_amount` (zaokr. 2 miejsca)

Sumy faktury = suma kwot pozycji.

### Przykład regresji
| Pole | Wartość |
|------|---------|
| unit_price_gross | 120.00 |
| quantity | 60 |
| vat_rate | 5% |
| **gross_amount** | **7200.00** |
| **net_amount** | **6857.14** |
| **vat_amount** | **342.86** |

---

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `app/services/invoice_totals.py` | `calculate_line_amounts()`, tryb gross/net w `build_items` |
| `app/schemas/invoice.py` | `price_mode`, `unit_price_gross` w `InvoiceItemInput` |
| `app/integrations/ksef/xml_parser.py` | FA(3) P_9B/P_11A — ten sam kalkulator |
| `app/integrations/ksef/mapper.py` | XML: `P_11`, `P_11Vat`, `P_11A` z kwot pozycji |
| `frontend-react/src/components/invoice/InvoiceForm.jsx` | select Netto/Brutto, kalkulacja pozycji |
| `frontend-react/src/components/invoice/InvoiceForm.module.css` | kolumna „Tryb” |
| `tests/unit/test_invoice_totals.py` | test regresji 120×60×5% |
| `tests/unit/test_ksef_xml_parser.py` | test P_9B gross-first |

---

## Testy

```bash
.venv/bin/pytest tests/unit/test_invoice_totals.py tests/unit/test_ksef_xml_parser.py tests/unit/test_invoice_service.py -q
# 56 passed
```

---

## Zapis do bazy / XML

- **DB:** `invoice_items.net_amount`, `vat_amount`, `gross_amount` z `InvoiceTotalsCalculator.build_items` (zapis przez istniejący mapper).
- **KSeF XML export:** pozycja wysyła `P_11`, `P_11Vat`, `P_11A` z tych samych kwot co w modelu domenowym.
- **KSeF import:** parser FA(3) używa wspólnej funkcji `calculate_line_amounts`.

---

## UI

W formularzu faktury: kolumna **Tryb** → `Netto` / `Brutto`. Przy brutto pole ceny przyjmuje kwotę brutto jednostkową.

*FV Gross Price Calculation Fix — pozycje faktury, tryb ceny brutto.*
