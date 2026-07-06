from __future__ import annotations

import json
from pathlib import Path

from ifg_guardian.core.repo_audit.eol_check import (
    EolVerdict,
    exit_code_for_verdict,
    render_markdown,
    run_eol_check,
)
from ifg_guardian.reporting import default_report_path, write_report


def run_repo_eol_check(
    *,
    output_format: str = "terminal",
    report_path: Path | None = None,
) -> int:
    result = run_eol_check()

    out_path = report_path
    if out_path is None and output_format != "json":
        out_path = default_report_path("EOL_CHECK")

    if out_path is not None:
        write_report(out_path, render_markdown(result))

    if output_format == "json":
        print(json.dumps(result.to_dict(), indent=2))
        return exit_code_for_verdict(result.verdict)

    if output_format == "markdown":
        print(render_markdown(result))
        if out_path:
            print(f"\nReport: {out_path}")
        return exit_code_for_verdict(result.verdict)

    icon = {
        EolVerdict.GO: "✅",
        EolVerdict.GO_WITH_CAUTION: "⚠️",
        EolVerdict.NO_GO: "❌",
    }[result.verdict]

    print(f"\n{icon} repo.eol_check: {result.verdict.value}")
    print(f"  Branch: {result.branch}")
    print(f"  HEAD: {result.head[:12]}…")
    print(f"  Tracked modified: {len(result.files)}")
    print(f"    EOL-only: {len(result.eol_only_files)}")
    print(f"    Logical: {len(result.logical_change_files)}")
    print(f"    Unknown: {len(result.unknown_files)}")
    print(f"\n  {result.recommendation}")

    if result.logical_change_files:
        print("\n  Logical change files:")
        for f in result.logical_change_files[:10]:
            print(f"    - {f.path}")
        if len(result.logical_change_files) > 10:
            print(f"    … and {len(result.logical_change_files) - 10} more")

    if result.eol_only_files and result.verdict == EolVerdict.GO_WITH_CAUTION:
        print("\n  EOL-only files (manual action required):")
        for f in result.eol_only_files[:10]:
            print(f"    - {f.path}")

    if out_path:
        print(f"\nReport: {out_path}")

    return exit_code_for_verdict(result.verdict)
