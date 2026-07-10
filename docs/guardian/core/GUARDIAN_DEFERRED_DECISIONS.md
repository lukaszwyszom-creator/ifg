# Guardian Deferred Decisions (GDD)

**Status:** CANONICAL  
**ID:** GWO-GUARDIAN-GDD  
**Data:** 2026-07-09

---

## Czym jest GDD

**Guardian Deferred Decisions (GDD)** to trwały rejestr **świadomie odłożonych decyzji** architektonicznych, UX, technicznych i organizacyjnych.

GDD odpowiada na pytanie:

> „Co wiemy, że trzeba kiedyś rozstrzygnąć — ale świadomie nie robimy tego teraz?”

GDD **nie blokuje release**, ale **nie pozwala zapomnieć** o odłożonych tematach.

---

## Czym GDD różni się od GWO

| Aspekt | GWO | GDD |
|--------|-----|-----|
| Cel | Wykonać konkretne zadanie w iteracji | Zapamiętać odłożoną decyzję |
| Status końcowy | DONE w ramach sprintu | OPEN do czasu świadomego zamknięcia |
| Zakres | Implementacja / review / deploy | Decyzja, nie implementacja |
| Artefakt | Raport w `docs/reports/` | Wpis w `docs/guardian/deferred_decisions.json` |
| Kto zamyka | Autor GWO po wykonaniu | Operator / architekt po podjęciu decyzji |

GWO realizuje pracę.  
GDD pamięta, **dlaczego** coś zostało odłożone i **kiedy** wrócić do tematu.

---

## Czym GDD różni się od Debt w raportach

Sekcje Debt w raportach GWO (`## UX Debt`, `## Technical Debt`, …) dokumentują obserwacje **w kontekście jednego zadania**.

GDD jest **centralnym rejestrem** między iteracjami.  
Wpisy Debt warto promować do GDD, gdy decyzja:

- wykracza poza bieżący GWO,
- wymaga oceny architektonicznej,
- ma wrócić w określonym momencie (np. przy skali, nowym module, kolejnym release).

---

## Kiedy używać GDD

Używaj GDD, gdy:

- świadomie odkładasz decyzję architektoniczną,
- wiesz, że temat wróci, ale nie teraz,
- review wykazało ryzyko / dług, który nie blokuje bieżącego release,
- potrzebujesz śledzić „kiedy wrócić” do tematu,
- chcesz uniknąć utraty kontekstu między sesjami Cursor / ChatGPT.

Przykłady:

- „Backendowe filtrowanie — dopiero przy >500 rekordach”
- „Rozbić `transmissionUtils.js` przy kolejnym większym GWO Monitora”
- „Ustalić workflow promowania Debt → GDD”

---

## Kiedy NIE używać GDD

Nie używaj GDD dla:

- **backlogu funkcjonalności** („dodać eksport PDF”),
- **listy bugów** („naprawić błąd 500”),
- zadań do wykonania w bieżącym GWO,
- drobnych poprawek kosmetycznych bez decyzji architektonicznej,
- rzeczy, które powinny blokować release (to idzie do GWO / NO-GO, nie do GDD).

---

## Format przechowywania

**Wybrany format:** JSON w `docs/guardian/deferred_decisions.json`

**Uzasadnienie:**

| Format | Zalety | Wady dla GDD |
|--------|--------|--------------|
| Markdown | Czytelny dla ludzi | Trudny w filtrowaniu, ID, statusach |
| YAML | Czytelny, strukturalny | Mniej naturalny dla inkrementalnych update CLI |
| JSON | Prosty CRUD, walidacja, diff w git | Mniej czytelny bez `review` |
| `.state/*.json` | Szybki dla runtime | Ryzyko utraty poza repo |

JSON w `docs/guardian/` jest:

- **wersjonowany w git** (nie ginie między sesjami),
- **łatwy do odczytu/zapisu** przez Guardian CLI,
- **spójny** z innymi artefaktami Guardiana (`handoff.json` jako runtime state, GDD jako canonical registry),
- **renderowalny** do Markdown przez `guardian deferred review`.

---

## Model danych

Każdy wpis zawiera:

| Pole | Opis |
|------|------|
| `id` | `GDD-0001`, `GDD-0002`, … |
| `project` | np. `IFG` |
| `module` | Moduł / obszar |
| `type` | Architecture / UX / Performance / Refactor / Technical Debt / Process / Other |
| `priority` | Low / Medium / High |
| `status` | OPEN / DONE / CANCELLED |
| `defer_reason` | Dlaczego odłożono |
| `description` | Opis decyzji |
| `review_when` | Kiedy wrócić do tematu |
| `source` | GWO, raport, review |
| `created_at` | Data utworzenia (ISO) |
| `closed_at` | Data zamknięcia (opcjonalnie) |

---

## CLI

```bash
# Dodaj wpis
guardian deferred add \
  --module "KSeF Monitor" \
  --type Performance \
  --priority Low \
  --reason "Nie blokuje release Monitora" \
  --description "Backendowe filtrowanie przy dużej skali" \
  --review-when "Gdy >500 rekordów na stronę" \
  --source "GWO-IFG-0059"

# Lista otwartych
guardian deferred list
guardian deferred list --project IFG --status OPEN --json

# Szczegóły
guardian deferred show GDD-0003

# Zamknięcie
guardian deferred done GDD-0003
guardian deferred cancel GDD-0003

# Review (generuje raport otwartych GDD)
guardian deferred review
guardian deferred review --project IFG --markdown
```

Lokalnie (repo):

```bash
PYTHONPATH=scripts python3 -m ifg_guardian.cli deferred list
```

---

## Review

`guardian deferred review`:

- zbiera wszystkie wpisy `OPEN` (opcjonalnie filtrowane po projekcie),
- sortuje wg priorytetu,
- generuje raport Markdown: `docs/guardian/GDD_REVIEW_YYYY-MM-DD.md`,
- wypisuje skrót w terminalu.

Review należy uruchamiać przed zamknięciem większej iteracji lub przed planowaniem kolejnego release.

---

## Powiązane dokumenty

- `docs/guardian/core/GUARDIAN_REPORT_DEBT_STANDARD.md` — Debt w raportach GWO
- `docs/guardian/deferred_decisions.json` — rejestr GDD
- `.cursor/rules/rules_09_reporting.mdc` — format raportów agenta
