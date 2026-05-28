"""Generic plugin — universal lessons + auto-learn engine for any codebase."""

import sys
from pathlib import Path

_PLUGIN_DIR = Path(__file__).parent
_KIWI_DIR = _PLUGIN_DIR.parent.parent

if str(_KIWI_DIR) not in sys.path:
    sys.path.insert(0, str(_KIWI_DIR))

from core.plugin_base import KiwiPlugin, PluginManifest


class GenericPlugin(KiwiPlugin):

    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="generic",
            version="2.0.0",
            languages=["php", "js", "ts", "python", "css", "go", "rust", "ruby"],
            frameworks=[],
            platforms=["wp", "nextjs", "python", "go", "rust", "any"],
            scope_types=["theme", "plugin", "app"],
            lessons_dir=str(_PLUGIN_DIR / "lessons"),
            description="Universal code quality — 379 lessons + auto-learn engine",
        )

    def get_checkers(self) -> dict:
        from scanner.checkers import REGISTRY
        return {k: v for k, v in REGISTRY.items()
                if k in ("presence", "absence", "cross-check", "bom-check")}

    def get_quality_rules(self) -> list:
        return []

    def get_context_map(self) -> dict:
        return {}

    def get_drafters(self) -> list:
        from .auto_detector import detect
        from .convention_learner import learn
        from .drafter import SkeletonDrafter

        return [SkeletonDrafter]

    def detect_project(self, path: str) -> float:
        from .auto_detector import detect

        profile = detect(path)

        if profile.has_wordpress_signals():
            return 0.05

        score = 0.1
        if profile.languages:
            score += 0.2
        if profile.frameworks:
            score += 0.2
        if profile.package_manager:
            score += 0.1
        if profile.test_framework:
            score += 0.1
        if profile.build_tool:
            score += 0.1

        return min(score, 0.8)

    def analyze_project(self, path: str) -> dict:
        """Full project analysis: detect + learn conventions + mine patterns."""
        from .auto_detector import detect
        from .convention_learner import learn
        from .pattern_miner import mine

        profile = detect(path)
        conventions = learn(path)
        patterns = mine(path)

        return {
            "profile": profile,
            "conventions": conventions,
            "patterns": patterns,
        }

    def run_generic_checks(self, path: str) -> list:
        """Run all generic checkers on a project."""
        from .convention_learner import learn
        from .checkers import run_all_checks

        conventions = learn(path)
        return run_all_checks(path, conventions)


Plugin = GenericPlugin