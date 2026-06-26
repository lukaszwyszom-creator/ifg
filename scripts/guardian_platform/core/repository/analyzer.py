from __future__ import annotations

from pathlib import Path

from guardian_platform.core.repository.discovery import iter_doc_files, iter_repo_files, normalize_path
from guardian_platform.core.repository.graphs import build_all_graphs
from guardian_platform.core.repository.models import RepositoryAnalysis
from guardian_platform.core.repository.protected import iter_root_config_paths
from guardian_platform.core.repository.scoring import build_false_positives_summary, build_file_analyses


class RepositoryAnalyzer:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def analyze(self) -> RepositoryAnalysis:
        (
            repo_files,
            import_graph,
            script_graph,
            test_graph,
            doc_graph,
            cli_graph,
            guardian_graph,
            entry_points,
        ) = build_all_graphs(self.root)

        tracked_paths = sorted(
            {normalize_path(self.root, p) for p in repo_files if p.suffix == ".py"}
            | {normalize_path(self.root, p) for p in iter_doc_files(self.root)}
            | set(iter_root_config_paths(self.root))
        )

        files = build_file_analyses(
            self.root,
            tracked_paths,
            import_graph,
            script_graph,
            test_graph,
            doc_graph,
            cli_graph,
            guardian_graph,
            entry_points,
        )

        false_positives = build_false_positives_summary(files)

        return RepositoryAnalysis(
            root=str(self.root),
            files=files,
            import_graph=import_graph,
            script_graph=script_graph,
            test_graph=test_graph,
            documentation_graph=doc_graph,
            cli_graph=cli_graph,
            guardian_graph=guardian_graph,
            false_positives_prevented=false_positives,
            scanned_paths=sorted({normalize_path(self.root, p) for p in repo_files}),
        )

    def get_file(self, path: str) -> FileAnalysis | None:
        analysis = self.analyze()
        normalized = path.replace("\\", "/").lstrip("./")
        if normalized in analysis.files:
            return analysis.files[normalized]
        for key, value in analysis.files.items():
            if key.endswith(normalized):
                return value
        return None
