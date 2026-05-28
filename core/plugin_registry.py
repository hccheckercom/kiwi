"""Plugin discovery — find and instantiate available Kiwi plugins."""

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .plugin_base import KiwiPlugin

_registered_plugins: list = []
_discovered: bool = False
_plugins_dir = Path(__file__).parent.parent / "plugins"


def discover_plugins() -> list:
    """Scan plugins/ directory for installed plugins."""
    global _discovered

    if not _discovered:
        _discover_from_disk()
        _discovered = True

    return _registered_plugins


def _discover_from_disk() -> None:
    """Internal: scan plugins/ folder and instantiate plugin classes."""
    if not _plugins_dir.exists():
        return

    for plugin_dir in sorted(_plugins_dir.iterdir()):
        if not plugin_dir.is_dir():
            continue
        if plugin_dir.name.startswith(("_", ".")):
            continue

        plugin_file = plugin_dir / "plugin.py"
        if not plugin_file.exists():
            continue

        try:
            pkg_name = f"kiwi_plugins.{plugin_dir.name}"
            mod_name = f"{pkg_name}.plugin"

            # Ensure parent packages exist for relative imports
            if "kiwi_plugins" not in sys.modules:
                import types
                kiwi_pkg = types.ModuleType("kiwi_plugins")
                kiwi_pkg.__path__ = [str(_plugins_dir)]
                kiwi_pkg.__package__ = "kiwi_plugins"
                sys.modules["kiwi_plugins"] = kiwi_pkg

            if pkg_name not in sys.modules:
                import types
                sub_pkg = types.ModuleType(pkg_name)
                sub_pkg.__path__ = [str(plugin_dir)]
                sub_pkg.__package__ = pkg_name
                sys.modules[pkg_name] = sub_pkg

            spec = importlib.util.spec_from_file_location(
                mod_name,
                str(plugin_file),
                submodule_search_locations=[],
            )
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            module.__package__ = pkg_name
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)

            plugin_class = getattr(module, "Plugin", None)
            if plugin_class is None:
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type)
                            and hasattr(attr, "get_manifest")
                            and attr_name != "KiwiPlugin"):
                        plugin_class = attr
                        break

            if plugin_class:
                instance = plugin_class()
                if instance not in _registered_plugins:
                    _registered_plugins.append(instance)
        except Exception:
            continue


def register_plugin(plugin) -> None:
    """Manually register a plugin instance."""
    if plugin not in _registered_plugins:
        _registered_plugins.append(plugin)


def reset_registry() -> None:
    """Clear registry (for testing)."""
    global _discovered
    _registered_plugins.clear()
    _discovered = False