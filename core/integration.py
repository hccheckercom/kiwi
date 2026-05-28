"""Integration bridge — connects existing Kiwi modules to the plugin system.

Provides helper functions that existing code (mcp_server, agent/context) can call
to get plugin-aware behavior without rewriting their internals.
"""

import sys
from pathlib import Path

_KIWI_DIR = Path(__file__).parent.parent
if str(_KIWI_DIR) not in sys.path:
    sys.path.insert(0, str(_KIWI_DIR))

_active_plugin = None
_active_path = None


def get_plugin_for_path(path: str):
    """Get the best plugin for a given project path. Cached per path."""
    global _active_plugin, _active_path

    if _active_path == path and _active_plugin is not None:
        return _active_plugin

    from core.plugin_loader import get_primary_plugin
    plugin = get_primary_plugin(path)
    if plugin:
        _active_plugin = plugin
        _active_path = path
    return plugin


def get_checkers_for_path(path: str) -> dict:
    """Get checker registry from the appropriate plugin."""
    plugin = get_plugin_for_path(path)
    if plugin:
        return plugin.get_checkers()
    from scanner.checkers import REGISTRY
    return REGISTRY


def get_context_map_for_path(path: str) -> dict:
    """Get task-to-category map from the appropriate plugin."""
    plugin = get_plugin_for_path(path)
    if plugin:
        return plugin.get_context_map()
    from agent.context import _TASK_CATEGORY_MAP
    return _TASK_CATEGORY_MAP


def get_quality_rules_for_path(path: str) -> list:
    """Get quality rules from the appropriate plugin."""
    plugin = get_plugin_for_path(path)
    if plugin:
        return plugin.get_quality_rules()
    return []


def get_lessons_dir_for_path(path: str) -> str:
    """Get lessons directory from the appropriate plugin."""
    plugin = get_plugin_for_path(path)
    if plugin:
        lessons_path = plugin.get_lessons_path()
        if lessons_path:
            return lessons_path
    return str(_KIWI_DIR / "lessons")


def get_excluded_dirs_for_path(path: str) -> set:
    """Get excluded directories from the appropriate plugin."""
    plugin = get_plugin_for_path(path)
    if plugin:
        return plugin.get_excluded_dirs()
    return {"node_modules", ".git", "vendor", ".claude", "__pycache__"}


def reset_active_plugin():
    """Reset cached plugin (for testing)."""
    global _active_plugin, _active_path
    _active_plugin = None
    _active_path = None
