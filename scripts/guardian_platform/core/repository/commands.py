from __future__ import annotations

from pathlib import Path

from guardian_platform.core.reporting.writers import render_report
from guardian_platform.core.repository.analyzer import RepositoryAnalyzer
from guardian_platform.core.repository.report import (
    analysis_to_payload,
    render_explain_terminal,
    write_dead_code_report,
    write_orphans_report,
    write_repository_graph_report,
)
from guardian_platform.core.repository.scoring import impact_chain
from guardian_platform.core.runtime.context import CommandContext


def _analyzer(ctx: CommandContext) -> RepositoryAnalyzer:
    return RepositoryAnalyzer(ctx.root)


def _remainder_path(ctx: CommandContext) -> str | None:
    rem = ctx.extra.get("remainder") or []
    if not rem:
        return None
    return rem[0].replace("\\", "/")


def run_repo_graph(ctx: CommandContext) -> int:
    analysis = _analyzer(ctx).analyze()
    report_path = write_repository_graph_report(ctx.root, analysis)
    fp = analysis.false_positives_prevented
    payload = {
        "title": "Repository Graph",
        "sections": {
            "report": str(report_path.relative_to(ctx.root)),
            "tracked_nodes": len(analysis.files),
            "import_edges": sum(len(v) for v in analysis.import_graph.edges.values()),
            "import_cycles": len(analysis.import_graph.cycles),
            "cli_commands": len(analysis.cli_graph.command_to_modules),
            "workflows": len(analysis.guardian_graph.workflow_to_modules),
            "orphan_modules": len(analysis.import_graph.modules_without_importers),
            "false_positives_prevented": {
                "protected": fp.protected,
                "entrypoints": fp.entrypoints,
                "alembic": fp.alembic,
                "docs": fp.docs,
                "config": fp.config,
                "framework": fp.framework,
                "total": fp.total,
            },
        },
    }
    print(render_report(payload, ctx.output_format))
    return 0


def run_repo_dependencies(ctx: CommandContext) -> int:
    analysis = _analyzer(ctx).analyze()
    lines: list[str] = []
    for path in sorted(analysis.files):
        item = analysis.files[path]
        if item.metrics.imports_out or item.metrics.imported_by:
            lines.append(
                f"{path}: imports={item.metrics.imports_out} imported_by={item.metrics.imported_by}"
            )
    payload = analysis_to_payload(analysis, title="Repository Dependencies", section_key="dependencies", items=lines[:200])
    if len(lines) > 200:
        payload["sections"]["note"] = f"Showing 200 of {len(lines)} dependency rows"
    print(render_report(payload, ctx.output_format))
    return 0


def run_repo_orphan(ctx: CommandContext) -> int:
    analysis = _analyzer(ctx).analyze()
    report_path = write_orphans_report(ctx.root, analysis)
    orphans = sorted(p for p, f in analysis.files.items() if f.status.value == "ORPHAN")
    fp = analysis.false_positives_prevented
    payload = {
        "title": "Repository Orphans",
        "sections": {
            "report": str(report_path.relative_to(ctx.root)),
            "count": len(orphans),
            "orphans": orphans[:100],
            "false_positives_prevented": fp.total,
        },
    }
    if len(orphans) > 100:
        payload["sections"]["note"] = f"Showing 100 of {len(orphans)} orphans; see report"
    print(render_report(payload, ctx.output_format))
    return 0


def run_repo_dead_code(ctx: CommandContext) -> int:
    analysis = _analyzer(ctx).analyze()
    report_path = write_dead_code_report(ctx.root, analysis)
    dead = sorted(
        p
        for p, f in analysis.files.items()
        if f.recommendation.value in {"DELETE", "ARCHIVE"} and f.risk.value == "SAFE"
    )
    payload = {
        "title": "Repository Dead Code",
        "sections": {
            "report": str(report_path.relative_to(ctx.root)),
            "count": len(dead),
            "candidates": dead[:100],
        },
    }
    print(render_report(payload, ctx.output_format))
    return 0


def run_repo_impact(ctx: CommandContext) -> int:
    target = _remainder_path(ctx)
    if not target:
        print("Usage: repo impact <path>")
        return 2

    analyzer = _analyzer(ctx)
    analysis = analyzer.analyze()
    normalized = target.replace("\\", "/").lstrip("./")
    if normalized not in analysis.files:
        match = next((k for k in analysis.files if k.endswith(normalized)), None)
        if not match:
            print(f"Path not found in analysis: {target}")
            return 1
        normalized = match

    dependents = sorted(impact_chain(normalized, analysis.import_graph, downstream=True))
    dependencies = sorted(impact_chain(normalized, analysis.import_graph, downstream=False))
    item = analysis.files[normalized]

    payload = {
        "title": f"Repository Impact — {normalized}",
        "sections": {
            "status": item.status.value,
            "risk": item.risk.value,
            "recommendation": item.recommendation.value,
            "dependents": dependents[:50],
            "dependencies": dependencies[:50],
            "dependents_count": len(dependents),
            "dependencies_count": len(dependencies),
        },
    }
    print(render_report(payload, ctx.output_format))
    return 0


def run_repo_explain(ctx: CommandContext) -> int:
    target = _remainder_path(ctx)
    if not target:
        print("Usage: repo explain <path>")
        return 2

    item = _analyzer(ctx).get_file(target)
    if item is None:
        print(f"Path not found in analysis: {target}")
        return 1

    if ctx.output_format == "json":
        payload = {
            "title": f"Explain {item.path}",
            "sections": {
                "path": item.path,
                "status": item.status.value,
                "risk": item.risk.value,
                "recommendation": item.recommendation.value,
                "metrics": {
                    "imports": item.metrics.imports_out,
                    "imported_by": item.metrics.imported_by,
                    "cli": item.metrics.cli_refs,
                    "workflow": item.metrics.workflow_refs,
                    "tests": item.metrics.test_refs,
                    "docs": item.metrics.doc_refs,
                },
                "imported_by_paths": item.imported_by_paths,
                "cli_commands": item.cli_commands,
                "workflow_ids": item.workflow_ids,
                "test_paths": item.test_paths,
                "doc_paths": item.doc_paths,
            },
        }
        print(render_report(payload, ctx.output_format))
    else:
        print(render_explain_terminal(item))
    return 0
