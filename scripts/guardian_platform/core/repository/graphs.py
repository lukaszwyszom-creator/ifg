from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from guardian_platform.core.repository.discovery import (
    extract_doc_references,
    is_python,
    is_shell_script,
    iter_doc_files,
    iter_repo_files,
    map_handlers_from_profiles,
    normalize_path,
    parse_python_imports,
    scan_workflow_constants,
)
from guardian_platform.core.repository.models import (
    CLIGraph,
    DocumentationGraph,
    GuardianGraph,
    ImportGraph,
    ScriptGraph,
    TestGraph,
)


def _detect_import_cycles(edges: dict[str, set[str]]) -> list[list[str]]:
    cycles: list[list[str]] = []
    visited: set[str] = set()
    stack: set[str] = set()
    path: list[str] = []

    def dfs(node: str) -> None:
        if node in stack:
            start = path.index(node)
            cycle = path[start:] + [node]
            if cycle not in cycles:
                cycles.append(cycle)
            return
        if node in visited:
            return
        visited.add(node)
        stack.add(node)
        path.append(node)
        for nxt in edges.get(node, ()):
            dfs(nxt)
        path.pop()
        stack.remove(node)

    for node in edges:
        dfs(node)
    return cycles


def build_import_graph(root: Path, py_files: list[Path]) -> tuple[ImportGraph, dict[str, bool]]:
    edges: dict[str, set[str]] = defaultdict(set)
    reverse: dict[str, set[str]] = defaultdict(set)
    entry_points: dict[str, bool] = {}

    for path in py_files:
        rel = normalize_path(root, path)
        imports, is_entry = parse_python_imports(root, path)
        entry_points[rel] = is_entry
        for target in imports:
            edges[rel].add(target)
            reverse[target].add(rel)

    all_nodes = {normalize_path(root, p) for p in py_files}
    without_importers = sorted(n for n in all_nodes if not reverse.get(n) and not entry_points.get(n))

    graph = ImportGraph(
        edges={k: set(v) for k, v in edges.items()},
        reverse_edges={k: set(v) for k, v in reverse.items()},
        cycles=_detect_import_cycles({k: set(v) for k, v in edges.items()}),
        modules_without_importers=without_importers,
    )
    return graph, entry_points


def build_script_graph(root: Path, repo_files: list[Path], reverse_edges: dict[str, set[str]]) -> ScriptGraph:
    executables: list[str] = []
    helpers: list[str] = []
    unused: list[str] = []

    for path in repo_files:
        rel = normalize_path(root, path)
        if not rel.startswith("scripts/"):
            continue
        if path.name == "__init__.py":
            continue
        if is_shell_script(path):
            if path.parent == root / "scripts":
                executables.append(rel)
            continue
        if not is_python(path):
            continue
        _, is_entry = parse_python_imports(root, path)
        importers = reverse_edges.get(rel, set())
        if is_entry:
            executables.append(rel)
        elif importers:
            helpers.append(rel)
        else:
            unused.append(rel)

    return ScriptGraph(
        executables=sorted(executables),
        helpers=sorted(helpers),
        unused=sorted(unused),
    )


def build_test_graph(root: Path, py_files: list[Path]) -> TestGraph:
    test_to_modules: dict[str, list[str]] = {}
    module_to_tests: dict[str, list[str]] = defaultdict(list)
    tested_modules: set[str] = set()
    orphan_tests: list[str] = []

    app_and_scripts = {
        normalize_path(root, p)
        for p in py_files
        if normalize_path(root, p).startswith(("app/", "scripts/"))
    }

    for path in py_files:
        rel = normalize_path(root, path)
        if not rel.startswith("tests/") or path.name == "conftest.py":
            continue
        if not path.name.startswith("test_"):
            continue
        imports, _ = parse_python_imports(root, path)
        targets = [t for t in imports if t.startswith(("app/", "scripts/"))]
        test_to_modules[rel] = targets
        if not targets:
            orphan_tests.append(rel)
        for target in targets:
            module_to_tests[target].append(rel)
            tested_modules.add(target)

    modules_without_tests = sorted(m for m in app_and_scripts if m not in tested_modules)
    return TestGraph(
        test_to_modules=test_to_modules,
        module_to_tests={k: sorted(v) for k, v in module_to_tests.items()},
        modules_without_tests=modules_without_tests,
        orphan_tests=sorted(orphan_tests),
    )


def build_documentation_graph(root: Path) -> DocumentationGraph:
    doc_to_targets: dict[str, list[str]] = {}
    target_to_docs: dict[str, list[str]] = defaultdict(list)

    for doc in iter_doc_files(root):
        rel = normalize_path(root, doc)
        refs = extract_doc_references(doc.read_text(encoding="utf-8", errors="replace"))
        doc_to_targets[rel] = refs
        for ref in refs:
            target_to_docs[ref].append(rel)

    referenced_docs = {d for refs in doc_to_targets.values() for d in refs if d.endswith(".md")}
    all_docs = set(doc_to_targets)
    orphan_docs = sorted(d for d in all_docs if d not in referenced_docs and not doc_to_targets.get(d))

    return DocumentationGraph(
        doc_to_targets=doc_to_targets,
        target_to_docs={k: sorted(v) for k, v in target_to_docs.items()},
        orphan_docs=orphan_docs,
    )


def build_cli_graph(root: Path) -> CLIGraph:
    command_to_modules: dict[str, list[str]] = {}
    module_to_commands: dict[str, list[str]] = defaultdict(list)
    handlers = map_handlers_from_profiles(root)

    for command, module_path in handlers.items():
        command_to_modules[command] = [module_path]
        module_to_commands[module_path].append(command)

    return CLIGraph(
        command_to_modules=command_to_modules,
        module_to_commands={k: sorted(v) for k, v in module_to_commands.items()},
    )


def build_guardian_graph(root: Path) -> GuardianGraph:
    workflow_to_modules: dict[str, list[str]] = {}
    module_to_workflows: dict[str, list[str]] = defaultdict(list)
    command_to_handlers = map_handlers_from_profiles(root)

    for workflow_id, source in scan_workflow_constants(root):
        workflow_to_modules[workflow_id] = [source]
        module_to_workflows[source].append(workflow_id)

    return GuardianGraph(
        workflow_to_modules=workflow_to_modules,
        module_to_workflows={k: sorted(v) for k, v in module_to_workflows.items()},
        command_to_handlers=command_to_handlers,
    )


def build_all_graphs(root: Path) -> tuple[list[Path], ImportGraph, ScriptGraph, TestGraph, DocumentationGraph, CLIGraph, GuardianGraph, dict[str, bool]]:
    repo_files = iter_repo_files(root)
    py_files = [p for p in repo_files if is_python(p)]
    import_graph, entry_points = build_import_graph(root, py_files)
    script_graph = build_script_graph(root, repo_files, import_graph.reverse_edges)
    test_graph = build_test_graph(root, py_files)
    doc_graph = build_documentation_graph(root)
    cli_graph = build_cli_graph(root)
    guardian_graph = build_guardian_graph(root)
    return repo_files, import_graph, script_graph, test_graph, doc_graph, cli_graph, guardian_graph, entry_points
