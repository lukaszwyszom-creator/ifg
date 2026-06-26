from __future__ import annotations

from ifg_guardian.core.plugins.bootstrap import create_runtime


def _plugin_display_name(name: str) -> str:
    if name == "ifg":
        return "IFG"
    return name.capitalize()


def run_plugin_list() -> int:
    runtime = create_runtime()
    try:
        print("Guardian Plugins")
        print("=" * 40)
        plugins = sorted(runtime.plugin_registry.list(), key=lambda p: p.name)
        for plugin in plugins:
            count = runtime.plugin_registry.workflow_registry.count_for_plugin(plugin.name)
            print(_plugin_display_name(plugin.name))
            print(f"  version: {plugin.version}")
            print(f"  workflows: {count}")
            print()
        return 0
    finally:
        runtime.shutdown()
