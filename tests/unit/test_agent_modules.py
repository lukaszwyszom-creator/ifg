"""Testy jednostkowe modułów agent/runner, agent/rules_loader, agent/prompts i agent/git_guard."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from agent.git_guard import (
    DiffReport,
    _merge_changed_files,
    build_diff_report,
)
from agent.prompts import build_diagnostic_prompt
from agent.runner import (
    MAX_OUTPUT_CHARS,
    CommandResult,
    TestError as RunnerTestError,
    deduplicate_test_errors,
    parse_pytest_output,
    run_command,
    summarize_error_types,
)
from agent.rules_loader import RulesBundle, load_rules

_PY = sys.executable  # ścieżka do aktywnego interpretera Python


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------

class TestRunCommand:
    def test_successful_command_returns_zero_returncode(self):
        result = run_command([_PY, "-c", "print('ok')"])
        assert isinstance(result, CommandResult)
        assert result.returncode == 0
        assert "ok" in result.stdout
        assert result.timed_out is False

    def test_failing_command_returns_nonzero_returncode(self):
        result = run_command([_PY, "-c", "raise SystemExit(1)"])
        assert result.returncode == 1
        assert result.timed_out is False

    def test_timeout_sets_timed_out_flag(self):
        result = run_command(
            [_PY, "-c", "import time; time.sleep(10)"],
            timeout_seconds=1,
        )
        assert result.timed_out is True
        assert result.returncode == -1

    def test_missing_executable_does_not_raise(self):
        result = run_command(["_no_such_binary_xyz_"])
        assert result.returncode == -1
        assert result.stderr != ""

    def test_long_stdout_is_truncated(self):
        # generuj output wyraźnie powyżej limitu
        big = "x" * (MAX_OUTPUT_CHARS + 5000)
        result = run_command([_PY, "-c", f"print({big!r})"])
        assert len(result.stdout) <= MAX_OUTPUT_CHARS + len("\n... [output truncated]") + 5
        assert "[output truncated]" in result.stdout

    def test_stdout_within_limit_is_not_truncated(self):
        result = run_command([_PY, "-c", "print('hello')"])
        assert "[output truncated]" not in result.stdout


class TestParsePytestOutput:
    def test_parses_sample_failed_and_error_lines(self):
        output = """FAILED tests/unit/test_alpha.py::test_one - AssertionError: expected 1 == 2
ERROR tests/unit/test_beta.py::test_two - ImportError: cannot import name 'x'
"""
        errors = parse_pytest_output(output)
        assert errors == [
            RunnerTestError(
                test_name="tests/unit/test_alpha.py::test_one",
                error_type="assertion",
                message="AssertionError: expected 1 == 2",
            ),
            RunnerTestError(
                test_name="tests/unit/test_beta.py::test_two",
                error_type="import",
                message="ImportError: cannot import name 'x'",
            ),
        ]

    def test_classifies_assertion_error(self):
        output = "FAILED tests/unit/test_alpha.py::test_one - AssertionError: boom"
        errors = parse_pytest_output(output)
        assert errors[0].error_type == "assertion"

    def test_classifies_import_error(self):
        output = "ERROR tests/unit/test_beta.py::test_two - ModuleNotFoundError: No module named 'agent.x'"
        errors = parse_pytest_output(output)
        assert errors[0].error_type == "import"

    def test_fallbacks_to_other(self):
        output = "FAILED tests/unit/test_gamma.py::test_three - RuntimeError: unexpected"
        errors = parse_pytest_output(output)
        assert errors[0].error_type == "other"


class TestErrorPostProcessing:
    def test_deduplicate_keeps_first_order_and_removes_identical_errors(self):
        errors = [
            RunnerTestError("tests/unit/test_a.py::test_one", "assertion", "AssertionError: boom"),
            RunnerTestError("tests/unit/test_a.py::test_one", "assertion", "AssertionError: boom"),
            RunnerTestError("tests/unit/test_b.py::test_two", "import", "ImportError: missing x"),
            RunnerTestError("tests/unit/test_a.py::test_one", "assertion", "AssertionError: boom"),
        ]
        deduplicated = deduplicate_test_errors(errors)
        assert deduplicated == [
            RunnerTestError("tests/unit/test_a.py::test_one", "assertion", "AssertionError: boom"),
            RunnerTestError("tests/unit/test_b.py::test_two", "import", "ImportError: missing x"),
        ]

    def test_summary_counts_error_types(self):
        summary = summarize_error_types(
            [
                RunnerTestError("tests/unit/test_a.py::test_one", "assertion", "AssertionError: boom"),
                RunnerTestError("tests/unit/test_b.py::test_two", "assertion", "AssertionError: nope"),
                RunnerTestError("tests/unit/test_c.py::test_three", "domain", "Invalid transition"),
            ]
        )
        assert summary == {"assertion": 2, "domain": 1}


# ---------------------------------------------------------------------------
# rules_loader
# ---------------------------------------------------------------------------

class TestLoadRules:
    def test_missing_root_returns_empty_bundle(self):
        bundle = load_rules(root_dir="/tmp/_brak_takiego_katalogu_xyz_12345")
        assert isinstance(bundle, RulesBundle)
        assert bundle.files == []
        assert bundle.content == ""

    def test_no_matching_files_returns_empty_bundle(self):
        with tempfile.TemporaryDirectory() as d:
            # plik .txt – nie powinien być wczytany
            open(os.path.join(d, "notes.txt"), "w").close()
            bundle = load_rules(root_dir=d)
        assert bundle.files == []
        assert bundle.content == ""

    def test_finds_rules_star_md_in_root(self):
        with tempfile.TemporaryDirectory() as d:
            for name, text in [("rules_01_foo.md", "treść A"), ("rules_02_bar.md", "treść B")]:
                Path(d, name).write_text(text, encoding="utf-8")
            bundle = load_rules(root_dir=d)
        assert len(bundle.files) == 2
        assert "treść A" in bundle.content
        assert "treść B" in bundle.content
        # posortowane po ścieżce tekstowej
        assert bundle.files[0] < bundle.files[1]

    def test_finds_md_in_rules_subdir(self):
        with tempfile.TemporaryDirectory() as d:
            subdir = Path(d, "rules")
            subdir.mkdir()
            (subdir / "custom.md").write_text("treść custom", encoding="utf-8")
            bundle = load_rules(root_dir=d, rules_subdir="rules")
        assert any("custom.md" in f for f in bundle.files)
        assert "treść custom" in bundle.content

    def test_combines_root_and_subdir(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "rules_99_root.md").write_text("root content", encoding="utf-8")
            subdir = Path(d, "rules")
            subdir.mkdir()
            (subdir / "extra.md").write_text("sub content", encoding="utf-8")
            bundle = load_rules(root_dir=d)
        assert len(bundle.files) == 2
        assert "root content" in bundle.content
        assert "sub content" in bundle.content

    def test_missing_subdir_does_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "rules_01.md").write_text("tylko root", encoding="utf-8")
            # rules/ nie istnieje – nie powinno crashować
            bundle = load_rules(root_dir=d, rules_subdir="rules")
        assert len(bundle.files) == 1
        assert "tylko root" in bundle.content


# ---------------------------------------------------------------------------
# git_guard
# ---------------------------------------------------------------------------

class TestGitGuard:
    def test_blocks_domain_path(self):
        report = build_diff_report(
            changed_files=["app/domain/invoice.py"],
            total_lines=12,
            untracked_files=[],
        )
        assert isinstance(report, DiffReport)
        assert report.blocked is True
        assert any("blocked path: app/domain/invoice.py" == reason for reason in report.reasons)

    def test_blocks_too_many_files(self):
        report = build_diff_report(
            changed_files=[
                "agent/ifg_agent.py",
                "agent/git_guard.py",
                "tests/unit/test_agent_modules.py",
                "README.md",
            ],
            total_lines=40,
            untracked_files=[],
        )
        assert report.blocked is True
        assert any("too many changed files: 4 > 3" == reason for reason in report.reasons)

    def test_blocks_too_many_lines(self):
        report = build_diff_report(
            changed_files=["agent/ifg_agent.py"],
            total_lines=301,
            untracked_files=[],
        )
        assert report.blocked is True
        assert any("too many changed lines: 301 > 300" == reason for reason in report.reasons)

    def test_blocks_untracked_file_outside_agent(self):
        report = build_diff_report(
            changed_files=["README.md"],
            total_lines=10,
            untracked_files=["README.md"],
        )
        assert report.blocked is True
        assert any("untracked file outside agent/: README.md" == reason for reason in report.reasons)

    def test_untracked_file_in_agent_does_not_block_by_itself(self):
        report = build_diff_report(
            changed_files=["agent/new_helper.py"],
            total_lines=10,
            untracked_files=["agent/new_helper.py"],
        )
        assert report.blocked is False
        assert report.reasons == []

    def test_changed_files_merge_diff_and_untracked_without_duplicates(self):
        changed_files = _merge_changed_files(
            ["agent/ifg_agent.py", "tests/unit/test_agent_modules.py"],
            ["agent/ifg_agent.py", "agent/git_guard.py"],
        )
        assert changed_files == [
            "agent/git_guard.py",
            "agent/ifg_agent.py",
            "tests/unit/test_agent_modules.py",
        ]

    def test_allows_small_agent_only_diff(self):
        report = build_diff_report(
            changed_files=["agent/git_guard.py", "agent/ifg_agent.py"],
            total_lines=80,
            untracked_files=["agent/git_guard.py"],
        )
        assert report.blocked is False
        assert report.reasons == []


class TestPrompts:
    def test_build_prompt_uses_summary_and_classified_errors(self):
        prompt = build_diagnostic_prompt(
            task="Napraw test",
            test_result=CommandResult(
                command=["pytest"],
                returncode=1,
                stdout="FAILED raw stdout should not appear",
                stderr="AssertionError raw stderr should not appear",
            ),
            rules_bundle=RulesBundle(files=[], content=""),
            test_errors=[
                RunnerTestError(
                    test_name="tests/unit/test_alpha.py::test_one",
                    error_type="assertion",
                    message="AssertionError: expected 1 == 2",
                )
            ],
            error_summary={"assertion": 1},
            diff_report=DiffReport(
                changed_files=["agent/ifg_agent.py"],
                total_files=1,
                total_lines=12,
                blocked=False,
                reasons=[],
            ),
        )
        assert "TEST ERROR SUMMARY:" in prompt
        assert "assertion: 1" in prompt
        assert "tests/unit/test_alpha.py::test_one | assertion | AssertionError: expected 1 == 2" in prompt
        assert "STDOUT:" not in prompt
        assert "STDERR:" not in prompt

    def test_build_prompt_contains_diff_guard_blocked_and_reasons(self):
        prompt = build_diagnostic_prompt(
            task="Napraw test",
            test_result=CommandResult(
                command=["pytest"],
                returncode=1,
                stdout="",
                stderr="",
            ),
            rules_bundle=RulesBundle(files=["rules_01.md"], content="Zasada A"),
            test_errors=[
                RunnerTestError(
                    test_name="tests/unit/test_alpha.py::test_one",
                    error_type="domain",
                    message="Invalid transition",
                )
            ],
            error_summary={"domain": 1},
            diff_report=DiffReport(
                changed_files=["app/domain/invoice.py"],
                total_files=1,
                total_lines=20,
                blocked=True,
                reasons=["blocked path: app/domain/invoice.py"],
            ),
        )
        assert "DIFF GUARD:" in prompt
        assert "blocked: True" in prompt
        assert "- blocked path: app/domain/invoice.py" in prompt

    def test_build_prompt_contains_repair_constraints(self):
        prompt = build_diagnostic_prompt(
            task="Napraw test",
            test_result=CommandResult(
                command=["pytest"],
                returncode=1,
                stdout="",
                stderr="",
            ),
            rules_bundle=RulesBundle(files=["rules_01.md"], content="Zasada A"),
            test_errors=[],
            error_summary={},
            diff_report=DiffReport(
                changed_files=[],
                total_files=0,
                total_lines=0,
                blocked=False,
                reasons=[],
            ),
        )
        assert "OGRANICZENIA NAPRAWY:" in prompt
        assert "nie zmieniaj app/domain/ bez wyraźnej zgody" in prompt
        assert "maksymalnie 3 pliki" in prompt
        assert "nie dodawaj nowych plików poza agent/ bez zgody" in prompt

    def test_build_prompt_handles_missing_rules(self):
        prompt = build_diagnostic_prompt(
            task="Napraw test",
            test_result=CommandResult(
                command=["pytest"],
                returncode=0,
                stdout="",
                stderr="",
            ),
            rules_bundle=RulesBundle(files=[], content=""),
            test_errors=[],
            error_summary={},
            diff_report=DiffReport(
                changed_files=[],
                total_files=0,
                total_lines=0,
                blocked=False,
                reasons=[],
            ),
        )
        assert "Brak wczytanych rulesów z repo." in prompt

    def test_build_prompt_handles_missing_errors(self):
        prompt = build_diagnostic_prompt(
            task="Napraw test",
            test_result=CommandResult(
                command=["pytest"],
                returncode=0,
                stdout="",
                stderr="",
            ),
            rules_bundle=RulesBundle(files=["rules_01.md"], content="Zasada A"),
            test_errors=[],
            error_summary={},
            diff_report=DiffReport(
                changed_files=[],
                total_files=0,
                total_lines=0,
                blocked=False,
                reasons=[],
            ),
        )
        assert "Brak sklasyfikowanych błędów pytest." in prompt

