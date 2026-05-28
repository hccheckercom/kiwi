"""C0 QA — comprehensive verification script."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def run_qa():
    results = []

    print("=== C0 QA: COMPREHENSIVE VERIFICATION ===")
    print()

    # 1. All imports
    print("1. IMPORT CHECK")
    try:
        from lsp import __version__
        from lsp.config import LspConfig
        from lsp.bridge import KiwiBridge, _file_matches_scope
        from lsp.server import create_server, _uri_to_path, main
        from lsp.capabilities.diagnostics import violations_to_diagnostics, SEVERITY_MAP
        from lsp.capabilities.hover import create_hover
        from lsp.capabilities.code_actions import create_code_actions
        print("   ALL IMPORTS: PASS")
        results.append(("IMPORTS", True))
    except Exception as e:
        print(f"   IMPORT FAIL: {e}")
        results.append(("IMPORTS", False))

    # 2. Server creation
    print()
    print("2. SERVER CREATION")
    try:
        s = create_server()
        assert s.name == "kiwi-lsp"
        assert s.version == "1.0.0"
        assert s.config.severity_filter == "ALL"
        assert s.config.scan_on_open is True
        print(f"   Name: {s.name}, Version: {s.version}")
        print("   SERVER CREATION: PASS")
        results.append(("SERVER", True))
    except Exception as e:
        print(f"   SERVER FAIL: {e}")
        results.append(("SERVER", False))

    # 3. Bridge scan with real lessons
    print()
    print("3. BRIDGE SCAN (real lessons)")
    try:
        lessons_dir = str(Path(__file__).parent / "lessons")
        bridge = KiwiBridge(LspConfig(lessons_dir=lessons_dir))

        php_content = '<?php\n$x = $_GET["id"];\n$wpdb->query("SELECT * FROM t WHERE id=$x");\n'
        violations = bridge.scan_file("test.php", php_content)
        print(f"   PHP violations found: {len(violations)}")
        for v in violations[:3]:
            print(f"     [{v.severity}] {v.lesson_id}: {v.description[:50]}")

        js_content = 'const x = document.innerHTML = userInput;\nalert(eval(data));\n'
        violations_js = bridge.scan_file("test.js", js_content)
        print(f"   JS violations found: {len(violations_js)}")

        css_content = '.header { color: #333; font-size: 14px; }\n'
        violations_css = bridge.scan_file("test.css", css_content)
        print(f"   CSS violations found: {len(violations_css)}")
        print("   BRIDGE SCAN: PASS")
        results.append(("BRIDGE_SCAN", True))
    except Exception as e:
        print(f"   BRIDGE SCAN FAIL: {e}")
        import traceback; traceback.print_exc()
        results.append(("BRIDGE_SCAN", False))

    # 4. Diagnostics conversion
    print()
    print("4. DIAGNOSTICS CONVERSION")
    try:
        from scanner.models import Violation
        test_violations = [
            Violation(lesson_id="LES-001", severity="CRITICAL", category="security",
                     description="SQL injection", file="test.php", line=5, match_text="query"),
            Violation(lesson_id="LES-002", severity="HIGH", category="perf",
                     description="N+1 query", file="test.php", line=10, match_text=""),
        ]
        diags = violations_to_diagnostics(test_violations)
        assert len(diags) == 2
        assert diags[0].source == "kiwi"
        assert diags[0].code == "LES-001"
        assert diags[0].range.start.line == 4  # 0-indexed
        assert diags[1].range.start.line == 9
        print(f"   Converted {len(diags)} diagnostics correctly")
        print("   DIAGNOSTICS: PASS")
        results.append(("DIAGNOSTICS", True))
    except Exception as e:
        print(f"   DIAGNOSTICS FAIL: {e}")
        results.append(("DIAGNOSTICS", False))

    # 5. Hover
    print()
    print("5. HOVER INFO")
    try:
        info = {
            "id": "LES-001", "title": "SQL Injection", "severity": "CRITICAL",
            "category": "security", "why": "User input in query",
            "good_code": "$wpdb->prepare(...)", "bad_code": "$wpdb->query($var)",
        }
        hover = create_hover(info)
        assert hover is not None
        assert "LES-001" in hover.contents.value
        assert "SQL Injection" in hover.contents.value
        assert create_hover(None) is None
        print("   HOVER: PASS")
        results.append(("HOVER", True))
    except Exception as e:
        print(f"   HOVER FAIL: {e}")
        results.append(("HOVER", False))

    # 6. URI parsing
    print()
    print("6. URI PARSING")
    try:
        assert _uri_to_path("file:///home/user/test.php") == "/home/user/test.php"
        win_path = _uri_to_path("file:///d:/projects/test.php")
        assert "d:" in win_path.lower()
        space_path = _uri_to_path("file:///d:/path%20with%20spaces/test.php")
        assert "path with spaces" in space_path
        print("   URI PARSING: PASS")
        results.append(("URI_PARSING", True))
    except Exception as e:
        print(f"   URI PARSING FAIL: {e}")
        results.append(("URI_PARSING", False))

    # 7. Severity filter
    print()
    print("7. SEVERITY FILTER")
    try:
        bridge_crit = KiwiBridge(LspConfig(severity_filter="CRITICAL", lessons_dir=lessons_dir))
        v_crit = bridge_crit.scan_file("test.php", php_content)
        bridge_all = KiwiBridge(LspConfig(severity_filter="ALL", lessons_dir=lessons_dir))
        v_all = bridge_all.scan_file("test.php", php_content)
        print(f"   CRITICAL only: {len(v_crit)} violations")
        print(f"   ALL: {len(v_all)} violations")
        assert len(v_crit) <= len(v_all)
        print("   SEVERITY FILTER: PASS")
        results.append(("SEVERITY_FILTER", True))
    except Exception as e:
        print(f"   SEVERITY FILTER FAIL: {e}")
        results.append(("SEVERITY_FILTER", False))

    # 8. Max diagnostics cap
    print()
    print("8. MAX DIAGNOSTICS CAP")
    try:
        bridge_cap = KiwiBridge(LspConfig(max_diagnostics_per_file=2, lessons_dir=lessons_dir))
        v_cap = bridge_cap.scan_file("test.php", php_content)
        assert len(v_cap) <= 2
        print(f"   Capped at 2: got {len(v_cap)} violations")
        print("   MAX CAP: PASS")
        results.append(("MAX_CAP", True))
    except Exception as e:
        print(f"   MAX CAP FAIL: {e}")
        results.append(("MAX_CAP", False))

    # 9. File scope matching
    print()
    print("9. FILE SCOPE MATCHING")
    try:
        assert _file_matches_scope("src/Plugin.php", ["**/*.php"])
        assert _file_matches_scope("src/Plugin.php", ["*.php"])
        assert not _file_matches_scope("src/Plugin.php", ["*.js"])
        assert _file_matches_scope("src/app.js", ["**/*.js"])
        assert _file_matches_scope("test.css", ["*.css"])
        assert not _file_matches_scope("test.css", ["*.php", "*.js"])
        print("   FILE SCOPE: PASS")
        results.append(("FILE_SCOPE", True))
    except Exception as e:
        print(f"   FILE SCOPE FAIL: {e}")
        results.append(("FILE_SCOPE", False))

    # 10. CLI command registration
    print()
    print("10. CLI COMMAND")
    try:
        from cli.main import cli
        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(cli, ["lsp", "--help"])
        assert result.exit_code == 0
        assert "Start Kiwi LSP server" in result.output
        assert "--stdio" in result.output
        assert "--tcp" in result.output
        assert "--severity" in result.output
        print("   CLI COMMAND: PASS")
        results.append(("CLI", True))
    except Exception as e:
        print(f"   CLI FAIL: {e}")
        results.append(("CLI", False))

    # Summary
    print()
    print("=" * 50)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"C0 QA RESULT: {passed}/{total} CHECKS PASS")
    if passed == total:
        print("STATUS: ALL PASS")
    else:
        failed = [name for name, ok in results if not ok]
        print(f"FAILED: {', '.join(failed)}")
    print("=" * 50)
    return passed == total


if __name__ == "__main__":
    success = run_qa()
    sys.exit(0 if success else 1)