from __future__ import annotations

from pathlib import Path

from guardian_platform.core.repository.models import (
    CLIGraph,
    DocumentationGraph,
    FalsePositivesSummary,
    FileAnalysis,
    FileMetrics,
    FileStatus,
    GuardianGraph,
    ImportGraph,
    Recommendation,
    RiskLevel,
    ScriptGraph,
    TestGraph,
)
from guardian_platform.core.repository.protected import (
    ProtectedCategory,
    classify_protected_artifact,
    is_non_deletable,
    recommendation_for_protected,
)


def _total_refs(metrics: FileMetrics) -> int:
    return (
        metrics.imported_by
        + metrics.cli_refs
        + metrics.workflow_refs
        + metrics.test_refs
        + metrics.doc_refs
    )


def _read_source(root: Path, path: str) -> str:
    full = root / path
    if not full.is_file():
        return ""
    try:
        return full.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _has_console_scripts(source: str) -> bool:
    return "console_scripts" in source


def classify_status(metrics: FileMetrics, *, path: str = "") -> FileStatus:
    if metrics.is_test_file:
        if metrics.imported_by > 0 or metrics.test_refs > 0 or metrics.doc_refs > 0:
            return FileStatus.REFERENCED
        return FileStatus.ORPHAN
    if metrics.cli_refs > 0:
        return FileStatus.ACTIVE
    if metrics.imported_by > 0 or metrics.test_refs > 0 or metrics.doc_refs > 0 or metrics.workflow_refs > 0:
        return FileStatus.REFERENCED
    if metrics.is_entry_point:
        return FileStatus.ENTRYPOINT
    if _total_refs(metrics) == 0:
        return FileStatus.ORPHAN
    return FileStatus.UNKNOWN


def classify_risk(metrics: FileMetrics, status: FileStatus, category: ProtectedCategory) -> RiskLevel:
    if category != ProtectedCategory.NONE or status in {
        FileStatus.PROTECTED,
        FileStatus.ENTRYPOINT,
        FileStatus.FRAMEWORK,
    }:
        if status == FileStatus.ENTRYPOINT or category == ProtectedCategory.CONFIGURATION:
            return RiskLevel.HIGH
        if category in {ProtectedCategory.ALEMBIC, ProtectedCategory.DOCUMENTATION}:
            return RiskLevel.LOW
        return RiskLevel.MEDIUM

    if status == FileStatus.ACTIVE:
        if metrics.imported_by >= 5 or metrics.test_refs >= 5:
            return RiskLevel.HIGH
        return RiskLevel.MEDIUM
    if metrics.imported_by >= 10 or metrics.test_refs >= 5 or metrics.cli_refs >= 2:
        return RiskLevel.HIGH
    if metrics.imported_by >= 3 or metrics.test_refs >= 2 or metrics.workflow_refs >= 1 or metrics.cli_refs >= 1:
        return RiskLevel.MEDIUM
    if metrics.imported_by >= 1 or metrics.test_refs >= 1 or metrics.doc_refs >= 1:
        return RiskLevel.LOW
    if status == FileStatus.ORPHAN:
        return RiskLevel.SAFE
    return RiskLevel.LOW


def classify_recommendation(
    status: FileStatus,
    risk: RiskLevel,
    metrics: FileMetrics,
    category: ProtectedCategory,
) -> Recommendation:
    if is_non_deletable(status, category):
        return recommendation_for_protected(status, category)

    if status == FileStatus.ACTIVE or risk == RiskLevel.HIGH:
        return Recommendation.KEEP
    if status == FileStatus.UNKNOWN or risk == RiskLevel.MEDIUM:
        return Recommendation.REVIEW
    if status == FileStatus.ORPHAN and risk == RiskLevel.SAFE:
        if metrics.doc_refs > 0 and metrics.imported_by == 0 and metrics.test_refs == 0:
            return Recommendation.ARCHIVE
        if _total_refs(metrics) == 0:
            return Recommendation.DELETE
        return Recommendation.ARCHIVE
    if status == FileStatus.REFERENCED:
        return Recommendation.KEEP
    return Recommendation.REVIEW


def score_file(
    path: str,
    *,
    root: Path,
    import_graph: ImportGraph,
    script_graph: ScriptGraph,
    test_graph: TestGraph,
    doc_graph: DocumentationGraph,
    cli_graph: CLIGraph,
    guardian_graph: GuardianGraph,
    entry_points: dict[str, bool],
) -> FileAnalysis:
    imported_by = sorted(import_graph.reverse_edges.get(path, set()))
    import_paths = sorted(import_graph.edges.get(path, set()))
    cli_commands = sorted(cli_graph.module_to_commands.get(path, []))
    workflow_ids = sorted(guardian_graph.module_to_workflows.get(path, []))
    test_paths = sorted(test_graph.module_to_tests.get(path, []))
    doc_paths = sorted(doc_graph.target_to_docs.get(path, []))

    source = _read_source(root, path) if path.endswith(".py") or path.endswith(".toml") else ""
    is_entry = entry_points.get(path, False) or path in script_graph.executables

    metrics = FileMetrics(
        imports_out=len(import_paths),
        imported_by=len(imported_by),
        cli_refs=len(cli_commands),
        workflow_refs=len(workflow_ids),
        test_refs=len(test_paths),
        doc_refs=len(doc_paths),
        is_entry_point=is_entry,
        is_test_file=path.startswith("tests/") and path.endswith(".py"),
        is_doc_file=path.startswith("docs/") or path.startswith("README"),
        is_script_executable=path in script_graph.executables,
    )

    protected_status, category, protected_reason = classify_protected_artifact(
        path,
        source=source,
        is_entry_point=is_entry,
        has_console_scripts=_has_console_scripts(source),
    )

    if protected_status is not None:
        status = protected_status
    else:
        status = classify_status(metrics, path=path)

    risk = classify_risk(metrics, status, category)
    recommendation = classify_recommendation(status, risk, metrics, category)

    notes: list[str] = []
    if protected_reason:
        notes.append(protected_reason)
    if path in script_graph.unused and status == FileStatus.ORPHAN:
        notes.append("script with no importers and no __main__ entry")
    if path in test_graph.orphan_tests and category == ProtectedCategory.NONE:
        notes.append("test file imports no app/scripts modules")
    if path in doc_graph.orphan_docs and category == ProtectedCategory.DOCUMENTATION:
        notes.append("documentation — excluded from dead-code analysis")

    return FileAnalysis(
        path=path,
        status=status,
        risk=risk,
        recommendation=recommendation,
        metrics=metrics,
        protected_category=category.value,
        imported_by_paths=imported_by,
        import_paths=import_paths,
        cli_commands=cli_commands,
        workflow_ids=workflow_ids,
        test_paths=test_paths,
        doc_paths=doc_paths,
        notes=notes,
    )


def build_file_analyses(
    root: Path,
    paths: list[str],
    import_graph: ImportGraph,
    script_graph: ScriptGraph,
    test_graph: TestGraph,
    doc_graph: DocumentationGraph,
    cli_graph: CLIGraph,
    guardian_graph: GuardianGraph,
    entry_points: dict[str, bool],
) -> dict[str, FileAnalysis]:
    analyses: dict[str, FileAnalysis] = {}
    for path in paths:
        analyses[path] = score_file(
            path,
            root=root,
            import_graph=import_graph,
            script_graph=script_graph,
            test_graph=test_graph,
            doc_graph=doc_graph,
            cli_graph=cli_graph,
            guardian_graph=guardian_graph,
            entry_points=entry_points,
        )
    return analyses


def build_false_positives_summary(files: dict[str, FileAnalysis]) -> FalsePositivesSummary:
    summary = FalsePositivesSummary()
    for item in files.values():
        cat = item.protected_category
        if cat == ProtectedCategory.PACKAGE_INIT:
            summary.protected += 1
        elif cat == ProtectedCategory.ENTRYPOINT or item.status == FileStatus.ENTRYPOINT:
            summary.entrypoints += 1
        elif cat == ProtectedCategory.ALEMBIC:
            summary.alembic += 1
        elif cat == ProtectedCategory.DOCUMENTATION:
            summary.docs += 1
        elif cat == ProtectedCategory.CONFIGURATION:
            summary.config += 1
        elif cat == ProtectedCategory.FRAMEWORK or item.status == FileStatus.FRAMEWORK:
            summary.framework += 1
    summary.total = (
        summary.protected
        + summary.entrypoints
        + summary.alembic
        + summary.docs
        + summary.config
        + summary.framework
    )
    return summary


def count_would_be_false_positives(files: dict[str, FileAnalysis]) -> int:
    """Files that would incorrectly receive DELETE under naive orphan rules."""
    count = 0
    for item in files.values():
        if item.recommendation == Recommendation.DELETE:
            continue
        naive_orphan = (
            item.metrics.imported_by == 0
            and item.metrics.cli_refs == 0
            and item.metrics.workflow_refs == 0
            and item.metrics.test_refs == 0
            and not item.metrics.is_entry_point
        )
        if naive_orphan and is_non_deletable(item.status, item.protected_category):
            count += 1
    return count


def impact_chain(path: str, import_graph: ImportGraph, *, downstream: bool = True) -> set[str]:
    visited: set[str] = set()
    frontier = {path}

    while frontier:
        current = frontier.pop()
        if current in visited:
            continue
        visited.add(current)
        if downstream:
            related = import_graph.reverse_edges.get(current, set())
        else:
            related = import_graph.edges.get(current, set())
        frontier.update(related - visited)
    visited.discard(path)
    return visited
