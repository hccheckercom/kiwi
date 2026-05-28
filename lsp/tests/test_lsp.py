"""Tests for Kiwi LSP server."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest


class TestLspConfig:
    def test_defaults(self):
        from lsp.config import LspConfig
        cfg = LspConfig()
        assert cfg.severity_filter == "ALL"
        assert cfg.scan_on_open is True
        assert cfg.scan_on_save is True
        assert cfg.scan_on_change is False
        assert cfg.max_diagnostics_per_file == 50

    def test_custom(self):
        from lsp.config import LspConfig
        cfg = LspConfig(severity_filter="CRITICAL", scan_on_change=True)
        assert cfg.severity_filter == "CRITICAL"
        assert cfg.scan_on_change is True


class TestBridge:
    def test_file_matches_scope_php(self):
        from lsp.bridge import _file_matches_scope
        assert _file_matches_scope("src/Plugin.php", ["**/*.php"])
        assert _file_matches_scope("src/Plugin.php", ["*.php"])
        assert not _file_matches_scope("src/Plugin.php", ["*.js"])

    def test_file_matches_scope_wildcard(self):
        from lsp.bridge import _file_matches_scope
        assert _file_matches_scope("src/app.js", ["**/*.js"])
        assert _file_matches_scope("test.css", ["*.css"])

    def test_scan_file_nonexistent(self):
        from lsp.bridge import KiwiBridge
        from lsp.config import LspConfig
        bridge = KiwiBridge(LspConfig())
        result = bridge.scan_file("/nonexistent/file.php")
        assert result == []

    def test_scan_file_with_content(self):
        from lsp.bridge import KiwiBridge
        from lsp.config import LspConfig
        lessons_dir = str(Path(__file__).parent.parent.parent / "lessons")
        bridge = KiwiBridge(LspConfig(lessons_dir=lessons_dir))
        content = '<?php\n$x = $_GET["id"];\n$wpdb->query("SELECT * FROM t WHERE id=$x");\n'
        violations = bridge.scan_file("test.php", content)
        assert isinstance(violations, list)


class TestDiagnostics:
    def test_violations_to_diagnostics(self):
        from lsp.capabilities.diagnostics import violations_to_diagnostics
        from scanner.models import Violation

        violations = [
            Violation(
                lesson_id="LES-001",
                severity="CRITICAL",
                category="security",
                description="SQL injection detected",
                file="test.php",
                line=5,
                match_text='$wpdb->query("SELECT * FROM t WHERE id=$x")',
            ),
            Violation(
                lesson_id="LES-002",
                severity="HIGH",
                category="performance",
                description="N+1 query in loop",
                file="test.php",
                line=10,
                match_text="",
            ),
        ]

        diagnostics = violations_to_diagnostics(violations)
        assert len(diagnostics) == 2
        assert diagnostics[0].source == "kiwi"
        assert diagnostics[0].code == "LES-001"
        assert "CRITICAL" in diagnostics[0].message
        assert diagnostics[0].range.start.line == 4
        assert diagnostics[1].range.start.line == 9

    def test_empty_violations(self):
        from lsp.capabilities.diagnostics import violations_to_diagnostics
        assert violations_to_diagnostics([]) == []


class TestHover:
    def test_create_hover_with_info(self):
        from lsp.capabilities.hover import create_hover
        info = {
            "id": "LES-001",
            "title": "SQL Injection",
            "severity": "CRITICAL",
            "category": "security",
            "why": "User input in query",
            "good_code": "$wpdb->prepare(...)",
            "bad_code": "$wpdb->query($var)",
        }
        hover = create_hover(info)
        assert hover is not None
        assert "LES-001" in hover.contents.value
        assert "SQL Injection" in hover.contents.value
        assert "$wpdb->prepare" in hover.contents.value

    def test_create_hover_none(self):
        from lsp.capabilities.hover import create_hover
        assert create_hover(None) is None


class TestCodeActions:
    def test_create_code_actions_empty(self):
        from lsp.capabilities.code_actions import create_code_actions
        actions = create_code_actions("file:///test.php", [], MagicMock())
        assert actions == []


class TestUriToPath:
    def test_unix_path(self):
        from lsp.server import _uri_to_path
        with patch("sys.platform", "linux"):
            assert _uri_to_path("file:///home/user/test.php") == "/home/user/test.php"

    def test_windows_path(self):
        from lsp.server import _uri_to_path
        with patch("sys.platform", "win32"):
            result = _uri_to_path("file:///d:/projects/test.php")
            assert "d:" in result or "D:" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
