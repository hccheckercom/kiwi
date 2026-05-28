"""Tests for core plugin system — zero regression validation."""

import os
import sys
import pytest
from pathlib import Path

KIWI_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(KIWI_DIR))


@pytest.fixture(autouse=True)
def reset():
    from core.plugin_registry import reset_registry
    from core.integration import reset_active_plugin
    reset_registry()
    reset_active_plugin()
    yield


class TestCoreImports:
    def test_all_exports(self):
        from core import (KiwiPlugin, PluginManifest, BaseChecker,
                          BaseDrafter, BaseQualityRule, load_plugins,
                          detect_project, discover_plugins, register_plugin)
        assert KiwiPlugin is not None
        assert PluginManifest is not None

    def test_scanner_models_reexport(self):
        from core.scanner.models import Violation, Report
        from scanner.models import Violation as V2, Report as R2
        assert Violation is V2
        assert Report is R2


class TestPluginDiscovery:
    def test_discovers_wezone_wp(self):
        from core.plugin_registry import discover_plugins
        plugins = discover_plugins()
        assert len(plugins) == 1
        assert plugins[0].get_manifest().name == "wezone-wp"

    def test_manifest_fields(self):
        from core.plugin_registry import discover_plugins
        plugin = discover_plugins()[0]
        m = plugin.get_manifest()
        assert m.version == "3.0.0"
        assert "php" in m.languages
        assert "wordpress" in m.frameworks
        assert "wp" in m.platforms
        assert m.lessons_dir != ""

    def test_register_custom_plugin(self):
        from core.plugin_registry import discover_plugins, register_plugin
        from core.plugin_base import KiwiPlugin, PluginManifest

        class FakePlugin(KiwiPlugin):
            def get_manifest(self):
                return PluginManifest(name="fake", version="0.1")
            def get_checkers(self):
                return {}
            def get_quality_rules(self):
                return []
            def get_context_map(self):
                return {}

        # Discover first to load disk plugins, then register custom
        discover_plugins()
        register_plugin(FakePlugin())
        plugins = discover_plugins()
        assert len(plugins) == 2
        names = [p.get_manifest().name for p in plugins]
        assert "fake" in names


class TestPluginDetection:
    def test_detects_monorepo(self):
        from core.plugin_loader import detect_project
        results = detect_project(r"D:\projects\wezone\wezone-plugins")
        assert len(results) > 0
        assert results[0][1] >= 0.5

    def test_detects_theme(self):
        from core.plugin_loader import detect_project
        results = detect_project(r"D:\projects\wezone\themes\sfvn")
        assert len(results) > 0
        assert results[0][1] >= 0.5

    def test_primary_plugin(self):
        from core.plugin_loader import get_primary_plugin
        p = get_primary_plugin(r"D:\projects\wezone\wezone-plugins")
        assert p is not None
        assert p.get_manifest().name == "wezone-wp"

    def test_unknown_path_returns_empty(self):
        from core.plugin_loader import detect_project
        results = detect_project(r"C:\Windows\System32")
        assert len(results) == 0 or results[0][1] < 0.3


class TestPluginInterface:
    def test_checkers(self):
        from core.plugin_loader import get_primary_plugin
        p = get_primary_plugin(r"D:\projects\wezone\wezone-plugins")
        checkers = p.get_checkers()
        assert "presence" in checkers
        assert "absence" in checkers
        assert hasattr(checkers["presence"], "check")

    def test_quality_rules(self):
        from core.plugin_loader import get_primary_plugin
        p = get_primary_plugin(r"D:\projects\wezone\wezone-plugins")
        rules = p.get_quality_rules()
        assert len(rules) >= 5
        assert any("wc_get_product" in r.get("pattern", "") for r in rules)

    def test_context_map(self):
        from core.plugin_loader import get_primary_plugin
        p = get_primary_plugin(r"D:\projects\wezone\wezone-plugins")
        ctx = p.get_context_map()
        assert "checkout" in ctx
        assert "php-security" in ctx["checkout"]

    def test_excluded_dirs(self):
        from core.plugin_loader import get_primary_plugin
        p = get_primary_plugin(r"D:\projects\wezone\wezone-plugins")
        excludes = p.get_excluded_dirs()
        assert "node_modules" in excludes
        assert ".git" in excludes


class TestScanEngine:
    def test_scan_theme(self):
        from core.plugin_loader import get_primary_plugin
        from core.scanner.engine import scan
        p = get_primary_plugin(r"D:\projects\wezone\themes\sfvn")
        report = scan(
            r"D:\projects\wezone\themes\sfvn",
            plugin=p,
            severity_filter="CRITICAL",
            max_per_lesson=2,
        )
        assert report.patterns_checked > 0
        assert report.files_scanned > 0

    def test_scan_without_plugin_fallback(self):
        from core.scanner.engine import scan
        report = scan(
            r"D:\projects\wezone\themes\sfvn",
            plugin=None,
            severity_filter="CRITICAL",
            max_per_lesson=2,
        )
        # Without plugin, checkers dict is empty so no violations
        assert report.patterns_checked > 0


class TestIntegrationBridge:
    def test_get_plugin_for_path(self):
        from core.integration import get_plugin_for_path
        p = get_plugin_for_path(r"D:\projects\wezone\wezone-plugins")
        assert p.get_manifest().name == "wezone-wp"

    def test_get_checkers_for_path(self):
        from core.integration import get_checkers_for_path
        checkers = get_checkers_for_path(r"D:\projects\wezone\wezone-plugins")
        assert "presence" in checkers

    def test_get_context_map_for_path(self):
        from core.integration import get_context_map_for_path
        ctx = get_context_map_for_path(r"D:\projects\wezone\wezone-plugins")
        assert len(ctx) > 50

    def test_get_lessons_dir(self):
        from core.integration import get_lessons_dir_for_path
        d = get_lessons_dir_for_path(r"D:\projects\wezone\wezone-plugins")
        assert Path(d).exists()
        assert "lessons" in d


class TestBackwardCompat:
    def test_old_scanner_imports(self):
        from scanner.models import Violation, Report
        from scanner.loader import load_patterns
        from scanner.checkers import get_checker, REGISTRY
        assert Violation is not None
        assert len(load_patterns()) > 0
        assert get_checker("presence") is not None

    def test_old_agent_context_import(self):
        from agent.context import _TASK_CATEGORY_MAP, build_context
        assert "checkout" in _TASK_CATEGORY_MAP
        assert callable(build_context)
