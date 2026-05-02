"""ifg_agent.py – prosty CLI agenta diagnostycznego IFG v1.

Uruchamianie:
    python -m agent.ifg_agent "opis zadania"

Agent:
  1. Wczytuje rulesy: rules_*.md z roota + opcjonalnie rules/*.md.
  2. Uruchamia pytest tests/unit -q.
  3. Drukuje raport diagnostyczny.
  4. Drukuje prompt dla człowieka / Copilota.
  5. Kończy z kodem 0 (sukces) lub 1 (fail / timeout / błąd).

Agent NIE modyfikuje żadnych plików aplikacji IFG.
"""
from __future__ import annotations

import sys

from agent.git_guard import check_git_diff
from agent.prompts import build_diagnostic_prompt
from agent.rules_loader import load_rules
from agent.runner import (
    deduplicate_test_errors,
    parse_pytest_output,
    run_command,
    summarize_error_types,
)


_PYTEST_COMMAND = [sys.executable, "-m", "pytest", "tests/unit", "-q"]
_TIMEOUT = 120


def _print_separator(char: str = "─", width: int = 60) -> None:
    print(char * width)


def _print_diff_guard(diff_report) -> None:
    print("=== DIFF GUARD ===")
    print(f"files: {diff_report.total_files}")
    print(f"lines: {diff_report.total_lines}")
    print(f"blocked: {diff_report.blocked}")
    print("reasons:")
    if diff_report.reasons:
        for reason in diff_report.reasons:
            print(f"- {reason}")
    else:
        print("- none")


def _print_test_errors(test_errors) -> None:
    print("=== TEST ERRORS ===")
    if test_errors:
        for error in test_errors:
            print(f"- {error.test_name} | {error.error_type} | {error.message}")
    else:
        print("- none")


def _print_test_error_summary(error_summary) -> None:
    print("=== TEST ERROR SUMMARY ===")
    if error_summary:
        for error_type, count in error_summary.items():
            print(f"{error_type}: {count}")
    else:
        print("none: 0")


def _print_report(task: str, result, rules_bundle, diff_report, test_errors, error_summary) -> None:
    _print_separator("═")
    print("IFG AGENT v1 – RAPORT DIAGNOSTYCZNY")
    _print_separator("═")

    print(f"\nZADANIE:\n  {task}\n")

    status = (
        "⏱  TIMEOUT"
        if result.timed_out
        else ("✅ PASS" if result.returncode == 0 else "❌ FAIL")
    )
    print(f"STATUS TESTÓW:     {status}")
    print(f"RETURN CODE:       {result.returncode}")

    _print_separator()
    print("WCZYTANE RULESY:")
    if rules_bundle.files:
        for f in rules_bundle.files:
            print(f"  • {f}")
    else:
        print("  (brak – nie znaleziono plików rules_*.md ani rules/*.md)")

    _print_separator()
    print("STDOUT PYTEST (skrót):")
    stdout_lines = result.stdout.strip().splitlines()
    for line in stdout_lines[-30:]:
        print(f"  {line}")
    if not stdout_lines:
        print("  (brak)")

    if result.stderr.strip():
        _print_separator()
        print("STDERR (skrót):")
        for line in result.stderr.strip().splitlines()[-15:]:
            print(f"  {line}")

    _print_separator()
    _print_test_error_summary(error_summary)

    _print_separator()
    _print_test_errors(test_errors)

    _print_separator()
    _print_diff_guard(diff_report)

    _print_separator()
    print("=== COPILOT FIX PROMPT ===")
    print()
    prompt = build_diagnostic_prompt(
        task,
        result,
        rules_bundle,
        test_errors,
        error_summary,
        diff_report,
    )
    print(prompt)
    _print_separator("═")


def main() -> int:
    if len(sys.argv) < 2:
        print('Użycie: python -m agent.ifg_agent "opis zadania"', file=sys.stderr)
        return 1

    task = " ".join(sys.argv[1:])

    print("[agent] Wczytuję rulesy…")
    rules_bundle = load_rules()
    print(f"[agent] Wczytano {len(rules_bundle.files)} plik(ów) rulesów.")

    print(f"[agent] Uruchamiam: {' '.join(_PYTEST_COMMAND)} (timeout={_TIMEOUT}s)…")
    result = run_command(_PYTEST_COMMAND, timeout_seconds=_TIMEOUT)
    parsed_errors = parse_pytest_output("\n".join(part for part in [result.stdout, result.stderr] if part))
    test_errors = deduplicate_test_errors(parsed_errors)
    error_summary = summarize_error_types(test_errors)
    diff_report = check_git_diff()

    _print_report(task, result, rules_bundle, diff_report, test_errors, error_summary)

    return 0 if (result.returncode == 0 and not result.timed_out) else 1


if __name__ == "__main__":
    sys.exit(main())
