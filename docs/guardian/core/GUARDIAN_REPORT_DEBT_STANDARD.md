# Guardian — standard raportowania (Debt + decyzje ChatGPT)

**Status:** CANONICAL  
**ID:** GWO-GUARDIAN-STANDARD  
**Data:** 2026-07-09

---

## Cel

Raporty Guardiana i GWO dokumentują nie tylko wykonane zadanie, ale też **świadomie odłożone obserwacje rozwojowe** — bez tworzenia sztucznego backlogu implementacyjnego.

---

## Gdzie stosować

| Kontekst | Plik / mechanizm |
|----------|------------------|
| Workflow Guardian (`ifg.doctor`, `ifg.deploy.run`, …) | `finish_markdown(..., debt=...)` w `scripts/ifg_guardian/**/report.py` |
| Guardian Platform | `scripts/guardian_platform/**/report.py`, `writers.py` |
| Raporty GWO (Cursor / agent) | `.cursor/rules/rules_09_reporting.mdc` |

---

## Kolejność sekcji

1. Treść raportu (status, wyniki, testy)
2. **E. Następny krok** (raporty GWO) lub **Next Step** (release evaluate)
3. **Opcjonalne sekcje Debt** (tylko gdy są wpisy)
4. **Obowiązkowo:** `## Decyzje dla ChatGPT`
5. `## Wygenerowane raporty` (dla raportów GWO) / metadata końcowa (workflow)

---

## Decyzje dla ChatGPT (standard deterministyczny)

Guardian handoff **nie zgaduje** decyzji z treści raportu.  
Agregowane są wyłącznie wpisy jawnie podane przez autora w sekcji:

`## Decyzje dla ChatGPT`

Zasady:
- sekcja obowiązkowa dla nowych raportów GWO,
- umieszczana bezpośrednio przed `## Wygenerowane raporty`,
- zawiera wyłącznie pytania/decyzje do oceny ChatGPT,
- jeśli brak decyzji: wpis `Brak.`.

Przykład:

```markdown
## Decyzje dla ChatGPT

- Czy zaakceptować proponowaną architekturę?
- Czy wdrożyć zmianę na produkcję?
```

---

## Dozwolone kategorie

- `## UX Debt`
- `## Technical Debt`
- `## Architecture Debt`
- `## Performance Debt`

**Nie tworzyć pustych sekcji.**

---

## Format wpisu

```markdown
## UX Debt

#### HIGH

Pokazywać "Dzisiaj", "Wczoraj" zamiast wyłącznie daty.

Ułatwia operatorowi szybką orientację czasową.

Szybsze rozpoznanie świeżości procesu bez czytania kalendarza.

Nie wykonano w tym GWO, ponieważ wykracza poza ustalony zakres.
```

Pola programistyczne (`DebtItem`):

| Pole | Znaczenie |
|------|-----------|
| `category` | ux / technical / architecture / performance |
| `priority` | LOW / MEDIUM / HIGH |
| `title` | Krótki tytuł |
| `description` | Opis + uzasadnienie |
| `value` | Przewidywana wartość |
| `deferred_reason` | Dlaczego nie w tym GWO |

---

## API (Python)

```python
from ifg_guardian.core.reporting.debt import DebtItem, DebtCategory, DebtPriority, ReportDebt, finish_markdown

debt = ReportDebt(items=[
    DebtItem(
        category=DebtCategory.TECHNICAL,
        priority=DebtPriority.HIGH,
        title="Agregować process_status po stronie backendu.",
        description="Frontend nie powinien wyliczać końcowego statusu procesu.",
        value="Jedna semantyka statusu dla UI i API.",
    ),
])

markdown = finish_markdown(lines, debt=debt)
```

Alternatywnie: `state.debt` lub `transaction.audit["debt"]` jako lista słowników.

---

## Zasady

- Debt **nie oznacza błędu**.
- Brak wartościowych obserwacji → **pomiń sekcję**.
- Nie modyfikować historycznych raportów `.md`.

---

## Powiązane

- Implementacja: `scripts/ifg_guardian/core/reporting/debt.py`
- Testy: `tests/unit/test_guardian_report_debt.py`
- Raport wdrożenia: `docs/reports/2026-07-09_GUARDIAN_REPORT_DEBT_STANDARD.md`
