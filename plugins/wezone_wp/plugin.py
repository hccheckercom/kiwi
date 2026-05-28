"""Wezone WordPress plugin — implements KiwiPlugin interface.

Wraps existing 740 lessons, 11 checkers, and WP-specific logic.
"""

import os
import sys
from pathlib import Path

_PLUGIN_DIR = Path(__file__).parent
_KIWI_DIR = _PLUGIN_DIR.parent.parent

if str(_KIWI_DIR) not in sys.path:
    sys.path.insert(0, str(_KIWI_DIR))

from core.plugin_base import KiwiPlugin, PluginManifest
from core.checker_base import BaseChecker


class WezonWPPlugin(KiwiPlugin):

    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="wezone-wp",
            version="3.0.0",
            languages=["php", "js", "css"],
            frameworks=["wordpress", "tailwind", "wezone-commer"],
            platforms=["wp"],
            scope_types=["theme", "plugin"],
            lessons_dir=str(_KIWI_DIR / "lessons"),
            description="Wezone WordPress — 740 pre-built lessons for PHP/WP/Tailwind",
        )

    def get_checkers(self) -> dict:
        from scanner.checkers import REGISTRY
        return REGISTRY

    def get_quality_rules(self) -> list:
        return [
            {"pattern": r"wc_get_product", "message": "Use wz_get_product instead", "severity": "CRITICAL"},
            {"pattern": r"WC\(\)", "message": "Use wz_* functions instead", "severity": "CRITICAL"},
            {"pattern": r"\$product->", "message": "Use $product['key'] accessor", "severity": "CRITICAL"},
            {"pattern": r"__\w+--\w+", "message": "No BEM classes — use Tailwind", "severity": "CRITICAL"},
            {"pattern": r"wezone_is_active", "check": "absence", "message": "Missing wezone_is_active() guard", "severity": "CRITICAL"},
        ]

    def get_context_map(self) -> dict:
        from agent.context import _TASK_CATEGORY_MAP
        return _TASK_CATEGORY_MAP

    def get_drafters(self) -> list:
        try:
            from agent.reasoning.code_drafter import generate_skeleton
            return [generate_skeleton]
        except ImportError:
            return []

    def get_excluded_dirs(self) -> set:
        return {"node_modules", ".git", "vendor", ".claude", "__pycache__", ".next", "dist", "build", ".turbo", "out"}

    def get_excluded_files(self) -> set:
        return {
            "src/main.css", "src/output.css", "assets/css/main.css",
            "dist/style.css", "build/style.css", "style.min.css",
        }

    def detect_project(self, path: str) -> float:
        """Detect Wezone WP project with confidence scoring."""
        p = Path(path)
        confidence = 0.0

        # WP theme signals
        if (p / "functions.php").is_file():
            confidence += 0.3
        if (p / "style.css").is_file():
            confidence += 0.2

        # Wezone-specific signals
        if (p / "Plugin.php").is_file():
            confidence += 0.2
        if (p / "inc" / "store-config.php").is_file():
            confidence += 0.3

        # Monorepo / mu-plugins detection
        if (p / "mu-plugins").is_dir():
            confidence += 0.3
        if (p / "shared").is_dir():
            confidence += 0.2

        # WP plugin structure (subdirs with Plugin.php)
        if any(p.glob("*/Plugin.php")) or any(p.glob("mu-plugins/*/Plugin.php")):
            confidence += 0.2

        # composer.json with wordpress references
        composer = p / "composer.json"
        if composer.is_file():
            try:
                content = composer.read_text(encoding="utf-8", errors="ignore")
                if "wordpress" in content.lower() or "wpackagist" in content.lower():
                    confidence += 0.2
            except OSError:
                pass

        # Check for wz_ functions in PHP files (theme or plugin)
        if confidence >= 0.3:
            php_files = list(p.glob("*.php"))[:5] or list(p.glob("shared/src/*.php"))[:5]
            for php_file in php_files:
                try:
                    content = php_file.read_text(encoding="utf-8", errors="ignore")
                    if "wz_" in content or "wezone" in content.lower():
                        confidence += 0.2
                        break
                except OSError:
                    pass

        # themes/ subfolder detection (parent project)
        if (p / "themes").is_dir():
            confidence += 0.1

        return min(confidence, 1.0)


Plugin = WezonWPPlugin