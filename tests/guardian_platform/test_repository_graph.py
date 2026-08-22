"""Tests for Guardian Platform repository dependency analysis."""
from __future__ import annotations

from pathlib import Path

import pytest

from guardian_platform.core.repository.analyzer import RepositoryAnalyzer
from guardian_platform.core.repository.discovery import (
    extract_doc_references,
    parse_python_imports,
    resolve_import_to_path,
)
from guardian_platform.core.repository.graphs import build_all_graphs
from guardian_platform.core.repository.models import FileStatus, Recommendation, RiskLevel
from guardian_platform.core.repository.protected import ProtectedCategory
from guardian_platform.core.repository.scoring import (
    classify_recommendation,
    classify_risk,
    classify_status,
    impact_chain,
)
from tests.guardian_platform.conftest import run_main


@pytest.fixture
def mini_repo(tmp_path: Path) -> Path:
    (tmp_path / "app" / "services").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "docs").mkdir()

    (tmp_path / "app" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "app" / "services" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "app" / "services" / "core_service.py").write_text(
        "from app.services import helper\n\nclass Core:\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "app" / "services" / "helper.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )
    (tmp_path / "app" / "services" / "orphan.py").write_text(
        "UNUSED = True\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "foo.py").write_text(
        "# orphan script\nprint('x')\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "run_entry.py").write_text(
        "from app.services.core_service import Core\n\nif __name__ == '__main__':\n    Core()\n",
        encoding="utf-8",
    )
    (tmp_path / "tests" / "unit" / "test_core.py").write_text(
        "from app.services.core_service import Core\n\ndef test_core():\n    assert Core\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "note.md").write_text(
        "See `app/services/core_service.py` for details.\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "orphan_doc.md").write_text(
        "No code references here.\n",
        encoding="utf-8",
    )
    return tmp_path


class TestDiscovery:
    def test_resolve_relative_import(self, mini_repo: Path):
        target = mini_repo / "app" / "services" / "core_service.py"
        resolved = resolve_import_to_path(mini_repo, target, "helper", 1)
        assert "app/services/helper.py" in resolved

    def test_parse_imports_and_entry(self, mini_repo: Path):
        imports, is_entry = parse_python_imports(mini_repo, mini_repo / "scripts" / "run_entry.py")
        assert "app/services/core_service.py" in imports
        assert is_entry is True

    def test_extract_doc_references(self):
        refs = extract_doc_references("Use `scripts/foo.py` and app/services/x.py")
        assert "scripts/foo.py" in refs
        assert "app/services/x.py" in refs


class TestGraphs:
    def test_import_graph_and_cycles(self, mini_repo: Path):
        _, import_graph, _, _, _, _, _, _ = build_all_graphs(mini_repo)
        assert "app/services/core_service.py" in import_graph.edges
        assert "app/services/helper.py" in import_graph.edges["app/services/core_service.py"]
        assert "app/services/orphan.py" in import_graph.modules_without_importers

    def test_script_graph(self, mini_repo: Path):
        _, _, script_graph, _, _, _, _, _ = build_all_graphs(mini_repo)
        assert "scripts/run_entry.py" in script_graph.executables
        assert "scripts/foo.py" in script_graph.unused

    def test_test_graph(self, mini_repo: Path):
        _, _, _, test_graph, _, _, _, _ = build_all_graphs(mini_repo)
        assert "app/services/core_service.py" in test_graph.module_to_tests
        assert "tests/unit/test_core.py" in test_graph.test_to_modules

    def test_documentation_graph(self, mini_repo: Path):
        _, _, _, _, doc_graph, _, _, _ = build_all_graphs(mini_repo)
        assert "app/services/core_service.py" in doc_graph.target_to_docs
        assert "docs/orphan_doc.md" in doc_graph.orphan_docs


class TestScoring:
    def test_orphan_script_safe_delete(self, mini_repo: Path):
        analysis = RepositoryAnalyzer(mini_repo).analyze()
        item = analysis.files["scripts/foo.py"]
        assert item.status == FileStatus.ORPHAN
        assert item.risk == RiskLevel.SAFE
        assert item.recommendation == Recommendation.DELETE
        assert item.metrics.doc_refs == 0

    def test_core_service_high_keep(self, mini_repo: Path):
        analysis = RepositoryAnalyzer(mini_repo).analyze()
        item = analysis.files["app/services/core_service.py"]
        assert item.status in {FileStatus.ACTIVE, FileStatus.REFERENCED}
        assert item.metrics.imported_by >= 1
        assert item.metrics.test_refs >= 1
        assert item.metrics.doc_refs >= 1
        assert item.recommendation == Recommendation.KEEP

    def test_impact_chain(self, mini_repo: Path):
        analysis = RepositoryAnalyzer(mini_repo).analyze()
        deps = impact_chain("app/services/helper.py", analysis.import_graph, downstream=True)
        assert "app/services/core_service.py" in deps
        assert "scripts/run_entry.py" in deps or "tests/unit/test_core.py" in deps

    def test_classify_status_metrics(self):
        from guardian_platform.core.repository.models import FileMetrics

        metrics = FileMetrics(imported_by=3, test_refs=2)
        assert classify_status(metrics) == FileStatus.REFERENCED
        assert classify_risk(metrics, FileStatus.REFERENCED, ProtectedCategory.NONE) == RiskLevel.MEDIUM
        assert classify_recommendation(
            FileStatus.REFERENCED, RiskLevel.MEDIUM, metrics, ProtectedCategory.NONE
        ) == Recommendation.REVIEW


class TestAnalyzer:
    def test_analyze_mini_repo(self, mini_repo: Path):
        analysis = RepositoryAnalyzer(mini_repo).analyze()
        assert len(analysis.files) >= 6
        assert analysis.import_graph is not None
        assert analysis.cli_graph is not None

    def test_get_file_suffix_match(self, mini_repo: Path):
        item = RepositoryAnalyzer(mini_repo).get_file("foo.py")
        assert item is not None
        assert item.path == "scripts/foo.py"


class TestReports:
    def test_write_reports(self, mini_repo: Path, monkeypatch: pytest.MonkeyPatch):
        from guardian_platform.core.repository import report as report_mod

        analysis = RepositoryAnalyzer(mini_repo).analyze()
        graph = report_mod.write_repository_graph_report(mini_repo, analysis)
        orphans = report_mod.write_orphans_report(mini_repo, analysis)
        dead = report_mod.write_dead_code_report(mini_repo, analysis)
        assert graph.exists()
        assert orphans.exists()
        assert dead.exists()
        assert "Repository Dependency Graph" in graph.read_text(encoding="utf-8")
        assert "scripts/foo.py" in dead.read_text(encoding="utf-8")


class TestRepositoryCLI:
    def test_repo_graph_command(self, mini_repo: Path, monkeypatch: pytest.MonkeyPatch):
        from guardian_platform.core.config.models import ProjectConfig

        monkeypatch.setattr(
            "guardian_platform.core.cli.app.load_project_config",
            lambda **kwargs: ProjectConfig(root=mini_repo),
        )
        code, out = run_main(["repo", "graph"])
        assert code == 0
        assert "# Repository Dependency Graph" in out
        assert not (mini_repo / "docs" / "reports" / "repository_graph.md").exists()

    def test_repo_orphan_command(self, mini_repo: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            "guardian_platform.core.config.loader.load_project_config",
            lambda **kwargs: __import__(
                "guardian_platform.core.config.models", fromlist=["ProjectConfig"]
            ).ProjectConfig(root=mini_repo),
        )
        code, out = run_main(["repo", "orphan"])
        assert code == 0
        assert "orphan" in out.lower()

    def test_repo_explain_missing_path(self, repo_root: Path):
        code, out = run_main(["repo", "explain", "does/not/exist.py"])
        assert code == 1

    def test_repo_impact_usage(self):
        code, out = run_main(["repo", "impact"])
        assert code == 2
        assert "Usage" in out

    def test_repo_explain_real_file(self, repo_root: Path, monkeypatch: pytest.MonkeyPatch):
        from guardian_platform.core.config.models import ProjectConfig

        monkeypatch.setattr(
            "guardian_platform.core.cli.app.load_project_config",
            lambda **kwargs: ProjectConfig(root=repo_root),
        )
        code, out = run_main(["repo", "explain", "scripts/guardian.py"])
        assert code == 0
        assert "Risk:" in out
        assert "Recommendation:" in out

    def test_repo_dead_code_explicit_output(self, mini_repo: Path, monkeypatch: pytest.MonkeyPatch):
        from guardian_platform.core.config.models import ProjectConfig

        monkeypatch.setattr(
            "guardian_platform.core.cli.app.load_project_config",
            lambda **kwargs: ProjectConfig(root=mini_repo),
        )
        out_file = mini_repo / "tmp" / "dead_code.md"
        code, out = run_main(["repo", "dead-code", "--output", str(out_file)])
        assert code == 0
        assert out_file.exists()
        assert "# Repository Dead Code Candidates" in out_file.read_text(encoding="utf-8")
        assert "Dead-code report: tmp/dead_code.md" in out
        assert not (mini_repo / "docs" / "reports" / "repository_dead_code.md").exists()

    def test_repo_dependencies_json(self):
        code, out = run_main(["--format", "json", "repo", "dependencies"])
        assert code == 0
        assert '"dependencies"' in out


class TestRegistry:
    def test_repo_commands_registered(self, platform_runtime):
        paths = {c.path for c in platform_runtime.commands.list_commands() if c.profile == "core"}
        assert ("repo", "graph") in paths
        assert ("repo", "dependencies") in paths
        assert ("repo", "orphan") in paths
        assert ("repo", "dead-code") in paths
        assert ("repo", "impact") in paths
        assert ("repo", "explain") in paths

    def test_existing_repo_audit_still_registered(self, platform_runtime):
        spec = platform_runtime.commands.resolve(["repo", "audit"])
        assert spec is not None
