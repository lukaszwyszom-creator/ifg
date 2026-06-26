from __future__ import annotations

from ifg_guardian.core.plugins.base import GuardianPlugin
from ifg_guardian.core.plugins.context import GuardianConfig, GuardianLogger, PluginContext
from ifg_guardian.core.plugins.registry import PluginRegistry
from ifg_guardian.plugins.core.plugin import CorePlugin
from ifg_guardian.plugins.ifg.plugin import IFGPlugin


class PluginLoader:
    """Static plugin loader — no dynamic discovery in Sprint 2."""

    _STATIC_PLUGINS: tuple[type[GuardianPlugin], ...] = (CorePlugin, IFGPlugin)

    def __init__(self, registry: PluginRegistry, config: GuardianConfig) -> None:
        self._registry = registry
        self._config = config
        self._logger = GuardianLogger("guardian.plugins")

    def load_static_plugins(self) -> None:
        plugins = [cls() for cls in self._STATIC_PLUGINS]
        for plugin in plugins:
            self._registry.register(plugin)

        ctx = PluginContext(
            config=self._config,
            logger=self._logger,
            registry=self._registry,
            metadata={"loader": "static"},
        )
        for plugin in self._registry.list():
            plugin.initialize(ctx)
