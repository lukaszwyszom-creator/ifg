# KSeF — naprawa mapowania `sale_date` w parserze FA(3)

Data: 2026-06-10

---

## Problem

Import faktur zakupowych z KSeF kończył się błędem:

```
ValueError: Invalid isoformat string: 'Warszawa'
```

w `ksef_session_service.sync_received_invoices` przy `date.fromisoformat(parsed["sale_date"])`.

Sync KSeF działał poprawnie (`ksef_returned=50`, `created=21`, `errors=29`).

---

## Przyczyna

W `app/integrations/ksef/xml_parser.py` funkcja `_extract_basic_fields` błędnie mapowała:

| Pole FA(3) | Znaczenie (oficjalne) | Błędne użycie IFG |
|------------|----------------------|-------------------|
| `P_1` | Data wystawienia | ✅ `issue_date` |
| `P_1M` | **Miejscowość wystawienia** | ❌ używane jako `sale_date` |
| `P_6` | Data dostawy / wykonania usługi | ❌ pomijane |

Stąd `sale_date="Warszawa"`, `"Bydgoszcz"`, `"Iława"`.

---

## Zmiana

```python
# przed
sale_date_txt = _txt(_find(fa_el, "fa:P_1M")) or issue_date_txt

# po
sale_date_txt = _txt(_find(fa_el, "fa:P_6")) or issue_date_txt
```

Fallback: brak `P_6` → `issue_date` (`P_1`).

---

## Pliki

- `app/integrations/ksef/xml_parser.py` — `_extract_basic_fields`
- `tests/unit/test_ksef_xml_parser.py` — `test_parse_fa3_xml_sale_date_uses_p6_not_p1m_place_of_issue`

Bez zmian: sync KSeF, sprzedaż, `ksef_session_service` (poza naprawionymi danymi wejściowymi).

---

## Test

```bash
.venv/bin/python -m pytest tests/unit/test_ksef_xml_parser.py -q
```

---

## Ryzyko wdrożenia

| Aspekt | Ocena |
|--------|-------|
| Zakres | **Niskie** — jedna linia mapowania + test |
| Sprzedaż | **Brak wpływu** |
| Faktury z `P_6` = data dostawy | **Poprawione** |
| Faktury bez `P_6` | Fallback do `P_1` (jak wcześniej przy braku P_1M) |
| Deploy | Wymaga **rebuild backendu** na DS723+ |

**Ogólne ryzyko: niskie.** Oczekiwany efekt: spadek `errors` w sync zakupów, wzrost `created`.
