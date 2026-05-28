"""Kiwi Core — language-agnostic reasoning engine."""

from .plugin_base import KiwiPlugin, PluginManifest
from .checker_base import BaseChecker
from .drafter_base import BaseDrafter
from .quality_base import BaseQualityRule
from .plugin_loader import load_plugins, detect_project
from .plugin_registry import discover_plugins, register_plugin

__all__ = [
    "KiwiPlugin",
    "PluginManifest",
    "BaseChecker",
    "BaseDrafter",
    "BaseQualityRule",
    "load_plugins",
    "detect_project",
    "discover_plugins",
    "register_plugin",
]
