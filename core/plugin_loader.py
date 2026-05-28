"""Plugin loader — detect project type and load appropriate plugins."""

import os
from pathlib import Path

from .plugin_registry import discover_plugins


def detect_project(path: str) -> list:
    """Return [(plugin_instance, confidence)] sorted by confidence desc."""
    plugins = discover_plugins()
    results = []

    for plugin in plugins:
        confidence = plugin.detect_project(path)
        if confidence > 0.0:
            results.append((plugin, confidence))

    return sorted(results, key=lambda x: x[1], reverse=True)


def load_plugins(path: str) -> list:
    """Auto-detect and load appropriate plugins for project path.

    Returns list of plugin instances sorted by relevance.
    Falls back to all available plugins if none match with high confidence.
    """
    detected = detect_project(path)

    if detected and detected[0][1] >= 0.5:
        return [p for p, _ in detected]

    # Fallback: return all plugins (generic behavior)
    return discover_plugins() or []


def get_primary_plugin(path: str):
    """Get the single best-matching plugin for a project. Returns None if no match."""
    detected = detect_project(path)
    if detected and detected[0][1] >= 0.3:
        return detected[0][0]
    return None