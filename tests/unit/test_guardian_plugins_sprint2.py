"""Unit tests for Guardian Plugin architecture (Sprint 2)."""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.plugins.base import GuardianPlugin
from ifg_guardian.core.plugins.bootstrap import create_runtime
from ifg_guardian.core.plugins.context import GuardianConfig, GuardianLogger, PluginContext
from ifg_guardian.core.plugins.loader import PluginLoader
from ifg_guardian.core.plugins.registry import PluginRegistry
from ifg_guardian.core.workflow.definition import WorkflowDefinition
from ifg_guardian.core.workflow.workflow_registry import WorkflowRegistry
from ifg_guardian.modules.plugins import run_plugin_list
from ifg_guardian.plugins.core.plugin import CorePlugin
from ifg_guardian.plugins.ifg.plugin import IFGPlugin


class DummyPlugin(GuardianPlugin):
    def __init__(self, *, name: str = "dummy", version: str = "0.1.0", workflows=None) -> None:
        self._name = name
        self._version = version
        self._workflows = workflows or []
        self.initialized = False
        self.shutdown_called = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    def workflows(self) -> list[WorkflowDefinition]:
        return list(self._workflows)

    def initialize(self, ctx: PluginContext) -> None:
        self.initialized = True
        assert ctx.registry is not None
        assert ctx.logger is not None

    def shutdown(self) -> None:
        self.shutdown_called = True


@pytest.fixture
def config(tmp_path: Path) -> GuardianConfig:
    return GuardianConfig(root=tmp_path)


class TestPluginRegistry:
    def test_register_list_get(self, config: GuardianConfig):
        registry = PluginRegistry()
        plugin = DummyPlugin(name="dummy")
        registry.register(plugin)

        assert registry.get("dummy") is plugin
        assert len(registry.list()) == 1

    def test_unregister_calls_shutdown(self, config: GuardianConfig):
        registry = PluginRegistry()
        plugin = DummyPlugin(name="dummy")
        registry.register(plugin)
        registry.unregister("dummy")

        assert plugin.shutdown_called
        with pytest.raises(KeyError):
            registry.get("dummy")

    def test_duplicate_register_raises(self):
        registry = PluginRegistry()
        registry.register(DummyPlugin(name="dup"))
        with pytest.raises(ValueError, match="already registered"):
            registry.register(DummyPlugin(name="dup"))

    def test_resolve_workflow(self):
        registry = PluginRegistry()
        wf = WorkflowDefinition(id="dummy.test", label="test", plugin="dummy")
        registry.register(DummyPlugin(name="dummy", workflows=[wf]))

        resolved = registry.resolve_workflow("dummy.test")
        assert resolved is not None
        assert resolved.id == "dummy.test"
        assert registry.resolve_workflow("missing") is None


class TestWorkflowRegistry:
    def test_indexes_plugin_workflows(self):
        wf_registry = WorkflowRegistry()
        plugin = DummyPlugin(
            name="dummy",
            workflows=[
                WorkflowDefinition(id="a", label="A"),
                WorkflowDefinition(id="b", label="B"),
            ],
        )
        wf_registry.index_plugin(plugin)

        assert wf_registry.get("a") is not None
        assert wf_registry.get("a").plugin == "dummy"
        assert wf_registry.count_for_plugin("dummy") == 2
        assert wf_registry.list_ids() == ["a", "b"]

    def test_duplicate_workflow_id_raises(self):
        wf_registry = WorkflowRegistry()
        wf = WorkflowDefinition(id="dup", label="dup")
        wf_registry.index_plugin(DummyPlugin(name="p1", workflows=[wf]))
        with pytest.raises(ValueError, match="duplicate workflow"):
            wf_registry.index_plugin(DummyPlugin(name="p2", workflows=[wf]))


class TestPluginLoader:
    def test_load_static_plugins(self, config: GuardianConfig):
        registry = PluginRegistry()
        loader = PluginLoader(registry, config)
        loader.load_static_plugins()

        names = {p.name for p in registry.list()}
        assert names == {"core", "ifg"}
        assert registry.resolve_workflow("core.ping") is not None
        assert registry.resolve_workflow("ifg.doctor") is not None
        assert registry.workflow_registry.count_for_plugin("ifg") == 3


class TestCorePlugin:
    def test_metadata(self):
        plugin = CorePlugin()
        assert plugin.name == "core"
        assert plugin.version == "1.0.0"

    def test_workflows_contains_ping_and_repo_audit(self):
        plugin = CorePlugin()
        ids = [wf.id for wf in plugin.workflows()]
        assert ids == ["core.ping", "core.repo.audit"]
        assert plugin.workflows()[0].plugin == "core"
        assert len(plugin.workflows()[1].stages) == 9


class TestIFGPlugin:
    def test_metadata(self):
        plugin = IFGPlugin()
        assert plugin.name == "ifg"
        assert plugin.version == "1.0.0"

    def test_workflows_contains_all_ifg_workflows(self):
        ids = [wf.id for wf in IFGPlugin().workflows()]
        assert ids == ["ifg.doctor", "ifg.release.plan", "ifg.deploy.run"]
        assert IFGPlugin().workflows()[1].depends_on == ["ifg.doctor"]
        deploy = IFGPlugin().workflows()[2]
        assert deploy.depends_on == ["ifg.release.plan"]
        assert deploy.mutating is True


class TestWorkflowDiscovery:
    def test_create_runtime_discovers_core_ping(self):
        runtime = create_runtime()
        try:
            wf = runtime.resolve_workflow("core.ping")
            assert wf is not None
            assert wf.plugin == "core"
            assert len(wf.stages) == 3
        finally:
            runtime.shutdown()

    def test_core_engine_has_no_hardcoded_workflows(self):
        import ifg_guardian.core.workflow.engine as engine_mod

        source = Path(engine_mod.__file__).read_text(encoding="utf-8")
        assert "core.ping" not in source
        assert "CORE_PING" not in source


class TestPluginListCLI:
    def test_guardian_plugin_list_output(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = run_plugin_list()
        output = buf.getvalue()

        assert code == 0
        assert "Core" in output
        assert "IFG" in output
        assert "version: 1.0.0" in output
        assert "workflows: 2" in output
        assert "workflows: 3" in output
