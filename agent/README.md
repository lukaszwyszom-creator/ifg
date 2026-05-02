# IFG Agent v1 – lokalny agent diagnostyczny

## Czym jest

Lokalny szkielet narzędziowy do diagnostyki projektu IFG.  
Agent **nie modyfikuje** kodu aplikacji. Służy wyłącznie do:
- wczytania rulesów z katalogu `rules/` (pliki `.md`),
- uruchomienia testów jednostkowych (`pytest tests/unit -q`),
- zebrania `stdout / stderr / returncode`,
- zbudowania raportu diagnostycznego,
- wygenerowania promptu naprawczego dla człowieka lub Copilota.

## Czego NIE robi (v1)

- Nie pisze ani nie zmienia kodu aplikacji IFG.
- Nie wysyła żadnych danych do OpenAI / Copilot API / Cursor API.
- Nie commituje, nie pushuje, nie tworzy PR.
- Nie uruchamia smoke testów ani testów e2e.
- Nie zawiera żadnej pętli AI-code-writing-loop.

## Struktura

```
agent/
  __init__.py        # marker pakietu
  runner.py          # run_command() → CommandResult
  rules_loader.py    # load_rules()  → RulesBundle
  prompts.py         # build_diagnostic_prompt()
  ifg_agent.py       # CLI (punkt wejścia)
  README.md          # ten plik
```

## Jak uruchomić

Z katalogu głównego projektu (z aktywnym `.venv`):

```bash
python -m agent.ifg_agent "opis zadania do zdiagnozowania"
```

### Przykładowa komenda

```bash
python -m agent.ifg_agent "Napraw błąd walidacji numeru faktury w invoice_number_policy"
```

Agent wydrukuje:
1. listę wczytanych rulesów,
2. wynik `pytest tests/unit -q`,
3. skrót stdout/stderr,
4. sklasyfikowaną listę błędów testów,
5. raport `Diff Guard`,
6. gotowy prompt naprawczy do wklejenia w Copilot Chat.

### Opcjonalny katalog rules/

Jeśli w głównym katalogu projektu istnieje folder `rules/` z plikami `.md`,  
agent wczyta je i dołączy ich treść do promptu diagnostycznego.  
Brak katalogu nie przerywa działania – agent pracuje normalnie.

## Diff Guard (v2.1)

Agent sprawdza lokalny `git diff` oraz untracked files z `git status --short` i raportuje podstawowe ryzyka:
- zmiany w `app/domain/`, `alembic/` i `app/persistence/mappers/`,
- więcej niż 3 zmienione pliki,
- więcej niż 300 linii zmian,
- untracked plik poza `agent/`.

To jest tylko raport diagnostyczny. W tej wersji agent:
- nie przerywa działania na podstawie diff guard,
- nie ocenia semantyki zmian,
- nie dolicza untracked files do `total_lines`,
- nie narzuca workflow git ani nie wykonuje żadnych commitów.

## Test Error Classification (v3)

Agent parsuje wynik `pytest` i buduje prostą listę błędów testów.
Każdy wpis zawiera:
- nazwę testu,
- kategorię błędu,
- krótki fragment komunikatu.

Obecne klasyfikacje heurystyczne:
- `assertion` dla `AssertionError`,
- `import` dla `ImportError` i `ModuleNotFoundError`,
- `type` dla `TypeError`,
- `value` dla `ValueError`,
- `domain` gdy w treści błędu pojawia się `Invalid` albo `Transition`,
- `other` jako fallback.

To jest klasyfikacja tekstowa, nie parser pełnego formatu pytest ani JUnit XML.

v3.1 dodaje deduplikację identycznych błędów oraz krótkie summary kategorii błędów w CLI i w promptcie diagnostycznym.

## v4: Guarded Copilot Fix Prompt

Agent nadal nie pisze kodu i nie aplikuje patchy.
W v4 buduje gotowy, bezpieczny prompt naprawczy dla Copilota, który zawiera:
- opis zadania,
- rulesy IFG z repo,
- summary błędów pytest i listę błędów po deduplikacji,
- wynik Diff Guard,
- twarde ograniczenia zakresu zmian.

Jeśli Diff Guard jest zablokowany, prompt wymusza najpierw wyjaśnienie przyczyny blokady zamiast proponowania kolejnych zmian.

## Plan v2

- **pytest integration** – parsowanie formatu JUnit XML, raport per-test,
- **smoke test runner** – opcjonalne uruchomienie `scripts/smoke_test.sh`,
- **AI client (opcjonalnie)** – przekazanie promptu do Copilot/OpenAI CLI i odebranie sugestii,
- **patch reviewer** – podgląd i zatwierdzenie zmiany przed zastosowaniem.
