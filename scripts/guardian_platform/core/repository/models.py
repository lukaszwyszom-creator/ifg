from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FileStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REFERENCED = "REFERENCED"
    ORPHAN = "ORPHAN"
    ENTRYPOINT = "ENTRYPOINT"
    PROTECTED = "PROTECTED"
    FRAMEWORK = "FRAMEWORK"
    UNKNOWN = "UNKNOWN"


class RiskLevel(str, Enum):
    SAFE = "SAFE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Recommendation(str, Enum):
    KEEP = "KEEP"
    REVIEW = "REVIEW"
    ARCHIVE = "ARCHIVE"
    DELETE = "DELETE"


@dataclass
class FileMetrics:
    imports_out: int = 0
    imported_by: int = 0
    cli_refs: int = 0
    workflow_refs: int = 0
    test_refs: int = 0
    doc_refs: int = 0
    is_entry_point: bool = False
    is_test_file: bool = False
    is_doc_file: bool = False
    is_script_executable: bool = False


@dataclass
class FileAnalysis:
    path: str
    status: FileStatus
    risk: RiskLevel
    recommendation: Recommendation
    metrics: FileMetrics
    protected_category: str = "NONE"
    imported_by_paths: list[str] = field(default_factory=list)
    import_paths: list[str] = field(default_factory=list)
    cli_commands: list[str] = field(default_factory=list)
    workflow_ids: list[str] = field(default_factory=list)
    test_paths: list[str] = field(default_factory=list)
    doc_paths: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class ImportGraph:
    edges: dict[str, set[str]] = field(default_factory=dict)
    reverse_edges: dict[str, set[str]] = field(default_factory=dict)
    cycles: list[list[str]] = field(default_factory=list)
    modules_without_importers: list[str] = field(default_factory=list)


@dataclass
class ScriptGraph:
    executables: list[str] = field(default_factory=list)
    helpers: list[str] = field(default_factory=list)
    unused: list[str] = field(default_factory=list)


@dataclass
class TestGraph:
    test_to_modules: dict[str, list[str]] = field(default_factory=dict)
    module_to_tests: dict[str, list[str]] = field(default_factory=dict)
    modules_without_tests: list[str] = field(default_factory=list)
    orphan_tests: list[str] = field(default_factory=list)


@dataclass
class DocumentationGraph:
    doc_to_targets: dict[str, list[str]] = field(default_factory=dict)
    target_to_docs: dict[str, list[str]] = field(default_factory=dict)
    orphan_docs: list[str] = field(default_factory=list)


@dataclass
class CLIGraph:
    command_to_modules: dict[str, list[str]] = field(default_factory=dict)
    module_to_commands: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class GuardianGraph:
    workflow_to_modules: dict[str, list[str]] = field(default_factory=dict)
    module_to_workflows: dict[str, list[str]] = field(default_factory=dict)
    command_to_handlers: dict[str, str] = field(default_factory=dict)


@dataclass
class FalsePositivesSummary:
    protected: int = 0
    entrypoints: int = 0
    alembic: int = 0
    docs: int = 0
    config: int = 0
    framework: int = 0
    total: int = 0


@dataclass
class RepositoryAnalysis:
    root: str
    files: dict[str, FileAnalysis]
    import_graph: ImportGraph
    script_graph: ScriptGraph
    test_graph: TestGraph
    documentation_graph: DocumentationGraph
    cli_graph: CLIGraph
    guardian_graph: GuardianGraph
    false_positives_prevented: FalsePositivesSummary = field(default_factory=FalsePositivesSummary)
    scanned_paths: list[str] = field(default_factory=list)
