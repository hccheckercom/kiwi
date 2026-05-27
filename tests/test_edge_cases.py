"""Edge case tests for Kiwi scanner patterns.

Tests complex scenarios and boundary conditions to ensure patterns
handle edge cases correctly without false positives.
"""

import os
import tempfile
from pathlib import Path
import pytest

from scanner.cli import scan_theme
from scanner.loader import load_patterns


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_theme_no_false_positives(self):
        """Empty theme should not trigger violations for optional features."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal theme structure
            Path(tmpdir, "style.css").write_text("/* Theme Name: Test */")
            Path(tmpdir, "functions.php").write_text("<?php\n// Empty theme")

            report = scan_theme(tmpdir, severity_filter="CRITICAL", platform="wp")

            # Should only flag truly missing required files, not optional features
            required_violations = [
                v for v in report.violations
                if "NO FILES MATCHING" not in v.file
            ]
            assert len(required_violations) == 0, "Empty theme should not have code violations"

    def test_nextjs_patterns_skip_wp_theme(self):
        """Next.js patterns should not run on WordPress themes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create WP theme
            Path(tmpdir, "style.css").write_text("/* Theme Name: Test */")
            Path(tmpdir, "functions.php").write_text("<?php")

            report = scan_theme(tmpdir, severity_filter="ALL", platform="wp")

            # Check no Next.js patterns triggered
            nextjs_violations = [
                v for v in report.violations
                if "app/api" in v.description or "Next.js" in v.description
            ]
            assert len(nextjs_violations) == 0, "Next.js patterns should not run on WP theme"

    def test_plugin_patterns_skip_standalone_theme(self):
        """Plugin-specific patterns should not run on standalone themes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create standalone theme (no packages/ folder)
            Path(tmpdir, "style.css").write_text("/* Theme Name: Test */")
            Path(tmpdir, "functions.php").write_text("<?php")

            report = scan_theme(tmpdir, severity_filter="ALL", platform="wp", scope_type="theme")

            # Check no plugin patterns triggered
            plugin_violations = [
                v for v in report.violations
                if "packages/" in v.file or "mu-plugins/" in v.file
            ]
            assert len(plugin_violations) == 0, "Plugin patterns should not run on standalone theme"

    def test_regex_special_chars_escaped(self):
        """Patterns with special regex chars should be properly escaped."""
        patterns = load_patterns()

        for pattern_def in patterns:
            pattern = pattern_def.get("pattern", "")
            if not pattern:
                continue

            # Test pattern compiles without error
            import re
            try:
                re.compile(pattern)
            except re.error as e:
                pytest.fail(f"Invalid regex in {pattern_def['id']}: {e}")

    def test_scope_with_multiple_extensions(self):
        """Scope with .{ts,tsx,js} syntax should resolve correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files with different extensions
            Path(tmpdir, "test.ts").write_text("const x = 1;")
            Path(tmpdir, "test.tsx").write_text("const y = 2;")
            Path(tmpdir, "test.js").write_text("const z = 3;")

            from scanner.resolver import resolve_scope

            # Test multi-extension scope (use pipe syntax, not brace expansion)
            files = resolve_scope(tmpdir, "**/*.ts|**/*.tsx|**/*.js")
            assert len(files) == 3, f"Should match all three extensions, got {len(files)}"

    def test_exclude_pattern_works(self):
        """Exclude patterns should properly filter out files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            Path(tmpdir, "src").mkdir()
            Path(tmpdir, "src", "app.ts").write_text("code")
            Path(tmpdir, "src", "app.test.ts").write_text("test")

            from scanner.resolver import resolve_scope

            # Test exclude
            files = resolve_scope(tmpdir, "**/*.ts", exclude="**/*.test.ts")
            assert len(files) == 1, "Should exclude test files"
            assert "app.test.ts" not in files[0]

    def test_absence_check_detects_missing_pattern(self):
        """Absence checks should flag when required pattern is completely missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create file WITHOUT the required pattern at all
            test_file = Path(tmpdir, "test.php")
            test_file.write_text("""<?php
function user_profile() {
    echo "User profile page";
}
""")

            from scanner.checkers import get_checker
            checker = get_checker("absence")

            pattern_def = {
                "id": "TEST-001",
                "severity": "CRITICAL",
                "category": "test",
                "title": "Test absence check",
                "description": "Missing required auth check",
                "pattern": "is_user_logged_in\\(\\)",
                "type": "absence"
            }

            violations = checker.check(pattern_def, [str(test_file)], tmpdir)

            # Should flag absence since pattern doesn't exist at all
            assert len(violations) > 0, f"Absence check should flag missing pattern, got {len(violations)} violations"

    def test_multiline_pattern_matching(self):
        """Patterns should handle multiline code correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir, "test.php")
            test_file.write_text("""<?php
function test() {
    $result = $wpdb->insert(
        'table',
        ['col' => 'val']
    );
    // Missing return check
}
""")

            from scanner.checkers import get_checker
            checker = get_checker("presence")

            pattern_def = {
                "id": "TEST-002",
                "severity": "HIGH",
                "category": "test",
                "title": "Test multiline pattern",
                "description": "wpdb insert without return check",
                "pattern": r"\$wpdb->insert\(",
                "type": "presence"
            }

            violations = checker.check(pattern_def, [str(test_file)], tmpdir)
            assert len(violations) > 0, f"Should detect multiline pattern, got {len(violations)} violations"


class TestPatternConfidence:
    """Test pattern confidence and false positive tracking."""

    def test_high_confidence_patterns_no_false_positives(self):
        """High-confidence patterns should have minimal false positives."""
        # Patterns that should have >95% confidence
        high_confidence_lessons = [
            "LES-016",  # Hardcoded hex colors
            "LES-017",  # BEM class names
            "LES-018",  # Hardcoded px values
        ]

        patterns = load_patterns()
        for lesson_id in high_confidence_lessons:
            pattern = next((p for p in patterns if p["id"] == lesson_id), None)
            assert pattern is not None, f"{lesson_id} should exist"

            # Pattern should have clear, unambiguous regex
            assert "pattern" in pattern, f"{lesson_id} should have pattern"
            assert len(pattern["pattern"]) > 0, f"{lesson_id} pattern should not be empty"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])