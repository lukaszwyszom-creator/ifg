"""runner.py – uruchamia polecenie powłoki, zbiera wynik.

Nie modyfikuje żadnego kodu aplikacji IFG.
"""
from __future__ import annotations

import subprocess
from collections import OrderedDict
from dataclasses import dataclass

MAX_OUTPUT_CHARS: int = 20_000
_TRUNCATED_MARKER: str = "\n... [output truncated]"


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + _TRUNCATED_MARKER


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


@dataclass
class TestError:
    test_name: str
    error_type: str
    message: str


def _classify_error(block: str) -> str:
    if "AssertionError" in block:
        return "assertion"
    if "ImportError" in block or "ModuleNotFoundError" in block:
        return "import"
    if "TypeError" in block:
        return "type"
    if "ValueError" in block:
        return "value"
    if "Invalid" in block or "Transition" in block:
        return "domain"
    return "other"


def parse_pytest_output(output: str) -> list[TestError]:
    errors: list[TestError] = []
    lines = output.splitlines()

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith(("FAILED ", "ERROR ")):
            continue

        remainder = stripped.split(" ", 1)[1] if " " in stripped else ""
        test_name, separator, message = remainder.partition(" - ")
        block_lines = [stripped]

        lookahead_index = index + 1
        while lookahead_index < len(lines):
            candidate = lines[lookahead_index].strip()
            if not candidate:
                break
            if candidate.startswith(("FAILED ", "ERROR ", "PASSED ")):
                break
            if candidate.startswith(("short test summary info", "===", "---")):
                break
            block_lines.append(candidate)
            lookahead_index += 1

        block_text = "\n".join(block_lines)
        short_message = message.strip() if separator else stripped
        if not short_message:
            short_message = stripped

        errors.append(
            TestError(
                test_name=test_name.strip() or "unknown",
                error_type=_classify_error(block_text),
                message=short_message[:200],
            )
        )

    return errors


def deduplicate_test_errors(errors: list[TestError]) -> list[TestError]:
    deduplicated: list[TestError] = []
    seen: set[tuple[str, str, str]] = set()

    for error in errors:
        key = (error.test_name, error.error_type, error.message)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(error)

    return deduplicated


def summarize_error_types(errors: list[TestError]) -> dict[str, int]:
    summary: OrderedDict[str, int] = OrderedDict()
    for error in errors:
        summary[error.error_type] = summary.get(error.error_type, 0) + 1
    return dict(summary)


def run_command(command: list[str], timeout_seconds: int = 120) -> CommandResult:
    """Uruchom polecenie i zwróć CommandResult.

    stdout/stderr przycięte do MAX_OUTPUT_CHARS.
    Obsługuje timeout bez rzucania wyjątku – timed_out=True w wyniku.
    """
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return CommandResult(
            command=command,
            returncode=proc.returncode,
            stdout=_truncate(proc.stdout or ""),
            stderr=_truncate(proc.stderr or ""),
        )
    except subprocess.TimeoutExpired as exc:
        raw_out = exc.stdout or b""
        raw_err = exc.stderr or b""
        return CommandResult(
            command=command,
            returncode=-1,
            stdout=_truncate(
                raw_out.decode("utf-8", errors="replace")
                if isinstance(raw_out, bytes) else raw_out
            ),
            stderr=_truncate(
                raw_err.decode("utf-8", errors="replace")
                if isinstance(raw_err, bytes) else raw_err
            ),
            timed_out=True,
        )
    except FileNotFoundError:
        return CommandResult(
            command=command,
            returncode=-1,
            stdout="",
            stderr=f"Nie znaleziono polecenia: {command[0]}",
        )
