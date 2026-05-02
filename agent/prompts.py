"""prompts.py – buduje prompt diagnostyczny dla człowieka lub Copilota.

Prompt wymusza reguły architektury IFG.
Nie modyfikuje żadnego kodu aplikacji IFG.
"""
from __future__ import annotations

from agent.git_guard import DiffReport
from agent.rules_loader import RulesBundle
from agent.runner import CommandResult, TestError


_ARCHITECTURE_CONSTRAINTS = """\
Bezwzględne zasady architektury IFG, których MUSISZ przestrzegać:
1. Logika biznesowa tylko w warstwie services/ lub domain/. Nie w routerach.
2. Router: przyjmuje request → wywołuje serwis → zwraca response. Nic więcej.
3. Warstwa domain/ nie importuje ORM, SQLAlchemy ani FastAPI.
4. Mapper jest jedynym mostem ORM ↔ domain. Nie omijaj mappera.
5. Wszystkie kwoty finansowe przez Decimal z ROUND_HALF_UP. Zakaz float.
6. Status DRAFT nie istnieje w runtime. Pierwszy status: READY_FOR_SUBMISSION.
7. Zmieniaj TYLKO pliki powiązane z zadaniem. Zakaz przypadkowego refaktoru.
8. Minimalny diff – zmieniaj najmniej kodu potrzebnego do naprawy.
9. Nie zmieniaj historycznych migracji alembic.
10. Nie modyfikuj kodu niezwiązanego z obecnym zadaniem.\
"""

_REPAIR_CONSTRAINTS = """\
- nie zmieniaj app/domain/ bez wyraźnej zgody
- nie zmieniaj alembic/ bez wyraźnej zgody
- nie zmieniaj app/persistence/mappers/ bez wyraźnej zgody
- minimalny diff
- maksymalnie 3 pliki
- nie dodawaj nowych plików poza agent/ bez zgody
- jeśli Diff Guard ma blocked=True, najpierw wyjaśnij dlaczego, nie rób kolejnych zmian\
"""


def build_diagnostic_prompt(
    task: str,
    test_result: CommandResult,
    rules_bundle: RulesBundle,
    test_errors: list[TestError],
    error_summary: dict[str, int],
    diff_report: DiffReport,
) -> str:
    """Zbuduj prompt diagnostyczny po polsku.

    Prompt używa statusu testów i sklasyfikowanej listy błędów zamiast pełnego stdout/stderr.
    """
    status_line = (
        "⏱ TIMEOUT – testy przekroczyły limit czasu."
        if test_result.timed_out
        else f"{'✅ PASS' if test_result.returncode == 0 else '❌ FAIL'} (returncode={test_result.returncode})"
    )

    rules_section = (
        f"Wczytane pliki rulesów ({len(rules_bundle.files)}):\n"
        + "\n".join(f"  - {f}" for f in rules_bundle.files)
        + (f"\n\nTreść rulesów:\n{rules_bundle.content}" if rules_bundle.content else "")
        if rules_bundle.files
        else "Brak wczytanych rulesów z repo."
    )

    errors_section = (
        "\n".join(
            f"- {error.test_name} | {error.error_type} | {error.message}"
            for error in test_errors
        )
        if test_errors
        else "Brak sklasyfikowanych błędów pytest."
    )

    summary_section = (
        "\n".join(f"{error_type}: {count}" for error_type, count in error_summary.items())
        if error_summary
        else "(brak kategorii błędów)"
    )

    diff_guard_lines = [
        f"files: {diff_report.total_files}",
        f"lines: {diff_report.total_lines}",
        f"blocked: {diff_report.blocked}",
        "reasons:",
    ]
    if diff_report.reasons:
        diff_guard_lines.extend(f"- {reason}" for reason in diff_report.reasons)
    else:
        diff_guard_lines.append("- none")
    diff_guard_section = "\n".join(diff_guard_lines)

    return f"""\
=== COPILOT FIX PROMPT ===

ZADANIE:
{task}

RULES IFG:
{rules_section}

WYNIK TESTÓW:
{status_line}

TEST ERROR SUMMARY:
{summary_section}

TEST ERRORS:
{errors_section}

DIFF GUARD:
{diff_guard_section}

OGRANICZENIA NAPRAWY:
{_REPAIR_CONSTRAINTS}

RULES IFG - OGRANICZENIA ARCHITEKTONICZNE:
{_ARCHITECTURE_CONSTRAINTS}

RAPORT KOŃCOWY:
Przygotuj odpowiedź zawierającą:
- przyczyna
- skutek
- zmienione pliki
- wynik testów
- ryzyka
- następny krok

Na podstawie powyższego opisu przygotuj bezpieczną, minimalną propozycję naprawy dla Copilota.
- Wskaż dokładnie plik i linię do zmiany.
- Nie rób refaktoru poza zakresem zadania.
- Upewnij się, że zmiana przejdzie pytest tests/unit -q.
- Jeśli Diff Guard ma blocked=True, najpierw opisz powód blokady zamiast proponować dalsze zmiany.
=== KONIEC PROMPTU ===\
"""
