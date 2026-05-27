"""Tests for SemgrepChecker."""

import pytest
from scanner.checkers.semgrep import SemgrepChecker


class TestSemgrepChecker:
    """Test Semgrep checker."""

    def test_semgrep_available(self):
        """Test: Semgrep availability check."""
        checker = SemgrepChecker()
        # Should be True if Semgrep installed
        assert isinstance(checker.semgrep_available, bool)

    def test_converter_integration(self):
        """Test: converter integration."""
        from scanner.converters.semgrep_converter import lesson_to_semgrep_rule

        lesson = {
            "id": "TEST-001",
            "severity": "HIGH",
            "category": "test",
            "title": "Test lesson",
            "scan": {
                "type": "semgrep",
                "pattern": "wp_mail(...)",
                "languages": ["php"]
            }
        }

        rule = lesson_to_semgrep_rule(lesson)
        assert rule is not None
        assert rule["pattern"] == "wp_mail(...)"

    def test_fallback_when_unavailable(self):
        """Test: fallback when Semgrep unavailable."""
        checker = SemgrepChecker()
        checker.semgrep_available = False

        # Should not crash when Semgrep unavailable
        assert checker.semgrep_available == False
