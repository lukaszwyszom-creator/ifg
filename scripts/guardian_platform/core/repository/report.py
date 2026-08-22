from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from guardian_platform.core.repository.models import (
    FileAnalysis,
    FileStatus,
    Recommendation,
    RepositoryAnalysis,
)
from guardian_platform.core.repository.protected import ProtectedCategory, is_non_deletable


class ReportExistsError(Exception):
    """Raised when writing would overwrite an existing report without --force."""


def _reports_dir(root: Path) -> Path:
    return root / "docs" / "reports"


def _resolve_output_path(root: Path, output_path: Path) -> Path:
    return output_path if output_path.is_absolute() else (root / output_path)


def write_markdown_report(
    root: Path,
    content: str,
    output_path: Path,
    *,
    force: bool = False,
) -> Path:
    out = _resolve_output_path(root, output_path)
    if out.exists() and not force:
        try:
            rel = out.relative_to(root)
        except ValueError:
            rel = out
        raise ReportExistsError(
            f"Report already exists: {rel} (use --force to overwrite)"
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(out)
    return out


def _render_file_block(item: FileAnalysis) -> list[str]:
    m = item.metrics
    lines = [
        f"### `{item.path}`",
        "",
        f"**Status:** {item.status.value} · **Risk:** {item.risk.value} · **Recommendation:** {item.recommendation.value}",
        "",
    ]
    if item.protected_category and item.protected_category != ProtectedCategory.NONE.value:
        lines.append(f"**Protected category:** {item.protected_category}")
        lines.append("")
    lines.extend([
        "| Metric | Count |",
        "|--------|------:|",
        f"| Imports | {m.imports_out} |",
        f"| Imported by | {m.imported_by} |",
        f"| CLI | {m.cli_refs} |",
        f"| Workflow | {m.workflow_refs} |",
        f"| Tests | {m.test_refs} |",
        f"| Docs | {m.doc_refs} |",
        "",
    ])
    if item.cli_commands:
        lines.append(f"- CLI commands: {', '.join(item.cli_commands)}")
    if item.workflow_ids:
        lines.append(f"- Workflows: {', '.join(item.workflow_ids)}")
    if item.imported_by_paths[:5]:
        lines.append(f"- Imported by (sample): {', '.join(item.imported_by_paths[:5])}")
    if item.notes:
        lines.append(f"- Notes: {'; '.join(item.notes)}")
    lines.append("")
    return lines


def render_repository_graph_markdown(analysis: RepositoryAnalysis) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    fp = analysis.false_positives_prevented

    lines = [
        "# Repository Dependency Graph",
        "",
        f"**Generated:** {now}  ",
        f"**Root:** `{analysis.root}`  ",
        f"**Scanned files:** {len(analysis.scanned_paths)}  ",
        f"**Tracked nodes:** {len(analysis.files)}  ",
        "",
        "## Summary",
        "",
        f"- Import edges: {sum(len(v) for v in analysis.import_graph.edges.values())}",
        f"- Import cycles: {len(analysis.import_graph.cycles)}",
        f"- Modules without importers: {len(analysis.import_graph.modules_without_importers)}",
        f"- Executable scripts: {len(analysis.script_graph.executables)}",
        f"- Unused scripts: {len(analysis.script_graph.unused)}",
        f"- Modules without tests: {len(analysis.test_graph.modules_without_tests)}",
        f"- Orphan docs: {len(analysis.documentation_graph.orphan_docs)}",
        f"- CLI commands mapped: {len(analysis.cli_graph.command_to_modules)}",
        f"- Workflows mapped: {len(analysis.guardian_graph.workflow_to_modules)}",
        "",
        "## False positives prevented",
        "",
        f"- Protected (__init__.py): {fp.protected}",
        f"- Entrypoints: {fp.entrypoints}",
        f"- Alembic: {fp.alembic}",
        f"- Docs: {fp.docs}",
        f"- Config: {fp.config}",
        f"- Framework: {fp.framework}",
        f"- **Total:** {fp.total}",
        "",
    ]

    if analysis.import_graph.cycles[:10]:
        lines.extend(["## Import cycles (sample)", ""])
        for cycle in analysis.import_graph.cycles[:10]:
            lines.append(f"- {' → '.join(cycle)}")
        lines.append("")

    lines.extend(["## CLI command map", ""])
    for command, modules in sorted(analysis.cli_graph.command_to_modules.items()):
        lines.append(f"- `{command}` → `{', '.join(modules)}`")
    lines.append("")

    lines.extend(["## Guardian workflows", ""])
    for workflow, modules in sorted(analysis.guardian_graph.workflow_to_modules.items()):
        lines.append(f"- `{workflow}` → `{', '.join(modules)}`")
    lines.append("")

    return "\n".join(lines)


def render_orphans_markdown(analysis: RepositoryAnalysis) -> str:
    orphans = [f for f in analysis.files.values() if f.status == FileStatus.ORPHAN]
    orphans.sort(key=lambda x: x.path)

    lines = [
        "# Repository Orphans",
        "",
        f"**Count:** {len(orphans)}",
        "",
    ]
    for item in orphans:
        lines.extend(_render_file_block(item))
    return "\n".join(lines)


def render_dead_code_markdown(analysis: RepositoryAnalysis) -> str:
    dead = [
        f
        for f in analysis.files.values()
        if f.recommendation in {Recommendation.DELETE, Recommendation.ARCHIVE}
        and f.risk.value == "SAFE"
        and not is_non_deletable(
            f.status,
            ProtectedCategory(f.protected_category)
            if f.protected_category in ProtectedCategory._value2member_map_
            else ProtectedCategory.NONE,
        )
    ]
    dead.sort(key=lambda x: x.path)

    lines = [
        "# Repository Dead Code Candidates",
        "",
        f"**Count:** {len(dead)}",
        "",
        "Candidates with **SAFE** risk and **DELETE** or **ARCHIVE** recommendation.",
        "",
    ]
    for item in dead:
        lines.extend(_render_file_block(item))
    return "\n".join(lines)


def write_repository_graph_report(root: Path, analysis: RepositoryAnalysis) -> Path:
    out = _reports_dir(root) / "repository_graph.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_repository_graph_markdown(analysis), encoding="utf-8")
    return out


def write_orphans_report(root: Path, analysis: RepositoryAnalysis) -> Path:
    out = _reports_dir(root) / "repository_orphans.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_orphans_markdown(analysis), encoding="utf-8")
    return out


def write_dead_code_report(root: Path, analysis: RepositoryAnalysis) -> Path:
    out = _reports_dir(root) / "repository_dead_code.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_dead_code_markdown(analysis), encoding="utf-8")
    return out


def render_explain_terminal(item: FileAnalysis) -> str:
    m = item.metrics
    lines = [
        item.path,
        "",
        "Imports:",
        str(m.imports_out),
        "",
        "Imported by:",
        str(m.imported_by),
        "",
        "CLI:",
        str(m.cli_refs),
        "",
        "Workflow:",
        str(m.workflow_refs),
        "",
        "Tests:",
        str(m.test_refs),
        "",
        "Docs:",
        str(m.doc_refs),
        "",
        "Risk:",
        item.risk.value,
        "",
        "Recommendation:",
        item.recommendation.value,
    ]
    if item.imported_by_paths:
        lines.extend(["", "Imported by paths:", *item.imported_by_paths[:20]])
    if item.cli_commands:
        lines.extend(["", "CLI commands:", *item.cli_commands])
    if item.workflow_ids:
        lines.extend(["", "Workflows:", *item.workflow_ids])
    if item.test_paths:
        lines.extend(["", "Tests:", *item.test_paths[:20]])
    if item.doc_paths:
        lines.extend(["", "Docs:", *item.doc_paths[:20]])
    return "\n".join(lines)


def analysis_to_payload(analysis: RepositoryAnalysis, *, title: str, section_key: str, items: list[str]) -> dict:
    return {
        "title": title,
        "sections": {
            "root": analysis.root,
            "tracked_nodes": len(analysis.files),
            section_key: items,
        },
    }
