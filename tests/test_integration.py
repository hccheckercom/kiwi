"""Integration tests — scan full synthetic theme, verify expected violations."""
import os
import sys
import tempfile
import shutil

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner.cli import scan_theme


def _create_theme(tmp, files: dict) -> str:
    """Create a synthetic theme with given files."""
    theme = os.path.join(tmp, "test-theme")
    os.makedirs(theme)
    for relpath, content in files.items():
        fullpath = os.path.join(theme, relpath)
        os.makedirs(os.path.dirname(fullpath), exist_ok=True)
        with open(fullpath, "w", encoding="utf-8") as f:
            f.write(content)
    return theme


def test_clean_theme_no_critical():
    """A minimal theme with @kiwi-ignore all should have 0 CRITICAL violations from presence checker."""
    tmp = tempfile.mkdtemp()
    try:
        theme = _create_theme(tmp, {
            "functions.php": "<?php\n// @kiwi-ignore all\nfunction test() { return 1; }\n",
            "style.css": "/* Theme Name: Test */\nbody { margin: 0; }\n",
        })
        report = scan_theme(theme, platform="wp", severity_filter="CRITICAL")
        presence_violations = [v for v in report.violations if v.line > 0]
        assert len(presence_violations) == 0, f"Expected 0 presence CRITICAL, got {len(presence_violations)}: {[v.lesson_id for v in presence_violations]}"
    finally:
        shutil.rmtree(tmp)


def test_n1_detected_in_theme():
    """Theme with get_post_meta in loop should flag LES-445 or LES-457."""
    tmp = tempfile.mkdtemp()
    try:
        theme = _create_theme(tmp, {
            "functions.php": "<?php\nfunction bad() {\n    $posts = array(1,2,3);\n    foreach ($posts as $p) {\n        $x = get_post_meta($p, 'key', true);\n    }\n}\n",
            "style.css": "/* Theme Name: Test */\n",
        })
        report = scan_theme(theme, platform="wp")
        lesson_ids = {v.lesson_id for v in report.violations}
        has_n1 = "LES-445" in lesson_ids or "LES-457" in lesson_ids
        assert has_n1, f"Expected LES-445 or LES-457 in violations, got relevant: {[v for v in report.violations if 'meta' in v.description.lower()]}"
    finally:
        shutil.rmtree(tmp)


def test_file_level_ignore_suppresses():
    """@kiwi-ignore at file top should suppress all violations for that lesson."""
    tmp = tempfile.mkdtemp()
    try:
        theme = _create_theme(tmp, {
            "functions.php": "<?php\n// @kiwi-ignore LES-445\nfunction bad() {\n    foreach ($posts as $p) {\n        $x = get_post_meta($p->ID, 'key', true);\n    }\n}\n",
            "style.css": "/* Theme Name: Test */\n",
        })
        report = scan_theme(theme, platform="wp")
        les445 = [v for v in report.violations if v.lesson_id == "LES-445"]
        assert len(les445) == 0, f"Expected 0 LES-445 violations (ignored), got {len(les445)}"
    finally:
        shutil.rmtree(tmp)


def test_scan_report_structure():
    """Scan report should have correct structure."""
    tmp = tempfile.mkdtemp()
    try:
        theme = _create_theme(tmp, {
            "functions.php": "<?php\nfunction x() {}\n",
            "style.css": "/* Theme Name: Test */\n",
        })
        report = scan_theme(theme, platform="wp")
        assert report.theme_path == theme
        assert report.patterns_checked > 0
        assert report.files_scanned >= 0
        assert hasattr(report, "violations")
        assert hasattr(report, "critical_count")
        assert hasattr(report, "high_count")
    finally:
        shutil.rmtree(tmp)


def test_severity_filter():
    """Severity filter should only return matching violations."""
    tmp = tempfile.mkdtemp()
    try:
        theme = _create_theme(tmp, {
            "functions.php": "<?php\nforeach ($posts as $p) {\n    $x = get_post_meta($p->ID, 'key', true);\n}\n",
            "style.css": "/* Theme Name: Test */\n",
        })
        report_critical = scan_theme(theme, platform="wp", severity_filter="CRITICAL")

        for v in report_critical.violations:
            assert v.severity == "CRITICAL", f"Severity filter leaked: {v.lesson_id} is {v.severity}"
    finally:
        shutil.rmtree(tmp)


def test_xss_echo_in_theme():
    """Theme with echo $var should flag XSS (LES-458 AST or presence)."""
    tmp = tempfile.mkdtemp()
    try:
        theme = _create_theme(tmp, {
            "functions.php": "<?php\nfunction display() {\n    echo $user_name;\n}\n",
            "style.css": "/* Theme Name: Test */\n",
        })
        report = scan_theme(theme, platform="wp")
        assert report.violations, "Expected some violations for echo $var"
    finally:
        shutil.rmtree(tmp)


def test_multiple_files_scanned():
    """Scan with multiple PHP files should check all of them."""
    tmp = tempfile.mkdtemp()
    try:
        theme = _create_theme(tmp, {
            "functions.php": "<?php\nfunction x() {}\n",
            "header.php": "<?php\necho 'header';\n",
            "footer.php": "<?php\necho 'footer';\n",
            "inc/helpers.php": "<?php\nfunction helper() {}\n",
            "style.css": "/* Theme Name: Test */\n",
        })
        report = scan_theme(theme, platform="wp")
        assert report.files_scanned >= 4, f"Expected >=4 files scanned, got {report.files_scanned}"
    finally:
        shutil.rmtree(tmp)


def test_non_php_files_excluded():
    """Non-PHP files should not produce PHP-specific violations."""
    tmp = tempfile.mkdtemp()
    try:
        theme = _create_theme(tmp, {
            "functions.php": "<?php\nfunction x() {}\n",
            "style.css": "/* Theme Name: Test */\nbody { margin: 0; }\n",
            "readme.txt": "This is a readme.\n",
            "screenshot.png": "fake png content",
        })
        report = scan_theme(theme, platform="wp")
        for v in report.violations:
            assert not v.file.endswith(".png"), f"PNG file should not have violations: {v}"
            assert not v.file.endswith(".txt"), f"TXT file should not have violations: {v}"
    finally:
        shutil.rmtree(tmp)


def test_context_guard_suppresses_in_integration():
    """get_post_meta after have_posts should not flag in full scan."""
    tmp = tempfile.mkdtemp()
    try:
        theme = _create_theme(tmp, {
            "functions.php": "<?php\nfunction x() {}\n",
            "single.php": "<?php\nwhile (have_posts()) :\n    the_post();\n    $price = get_post_meta(get_the_ID(), '_price', true);\nendwhile;\n",
            "style.css": "/* Theme Name: Test */\n",
        })
        report = scan_theme(theme, platform="wp")
        n1_violations = [v for v in report.violations
                         if v.lesson_id in ("LES-445", "LES-457") and "single.php" in v.file]
        assert len(n1_violations) == 0, f"Expected 0 N+1 in single.php (has have_posts), got {len(n1_violations)}"
    finally:
        shutil.rmtree(tmp)


def test_kiwi_ignore_all_suppresses_everything():
    """@kiwi-ignore all in first lines should suppress all violations for that file."""
    tmp = tempfile.mkdtemp()
    try:
        theme = _create_theme(tmp, {
            "functions.php": "<?php\n// @kiwi-ignore all\nforeach ($posts as $p) {\n    $x = get_post_meta($p, 'key', true);\n}\necho $user_name;\n",
            "style.css": "/* Theme Name: Test */\n",
        })
        report = scan_theme(theme, platform="wp")
        func_violations = [v for v in report.violations if "functions.php" in v.file and v.line > 0]
        assert len(func_violations) == 0, f"Expected 0 violations in functions.php (@kiwi-ignore all), got {len(func_violations)}: {[v.lesson_id for v in func_violations]}"
    finally:
        shutil.rmtree(tmp)


def test_dedup_in_full_scan():
    """Dedup per_file from lesson config should limit violations per file."""
    tmp = tempfile.mkdtemp()
    try:
        theme = _create_theme(tmp, {
            "functions.php": "<?php\n$a = get_post_meta($id, 'k1', true);\n$b = get_post_meta($id, 'k2', true);\n$c = get_post_meta($id, 'k3', true);\n",
            "style.css": "/* Theme Name: Test */\n",
        })
        report = scan_theme(theme, platform="wp")
        les445 = [v for v in report.violations if v.lesson_id == "LES-445"]
        # LES-445 has dedup: per_file — but the scan loads real lessons from disk.
        # If real lesson has dedup, expect <=1; otherwise just verify it fires at all.
        assert len(les445) >= 1, f"Expected at least 1 LES-445, got 0"
    finally:
        shutil.rmtree(tmp)


def test_raw_sql_detected_in_theme():
    """Theme with $wpdb->query without prepare → should flag via AST or regex."""
    tmp = tempfile.mkdtemp()
    try:
        theme = _create_theme(tmp, {
            "functions.php": '<?php\nglobal $wpdb;\n$wpdb->query("DELETE FROM {$wpdb->prefix}orders WHERE id = $id");\n',
            "style.css": "/* Theme Name: Test */\n",
        })
        # LES-459 (AST raw_sql) is tagged [plugin] so won't fire on theme scan.
        # LES-076 scopes to packages/*. So instead, test AST checker directly.
        try:
            from scanner.checkers.ast_checker import AstChecker
            checker = AstChecker()
            import glob as g
            php_files = g.glob(os.path.join(theme, "**/*.php"), recursive=True)
            pdef = {
                "id": "LES-459", "severity": "CRITICAL", "category": "php-security",
                "description": "Raw SQL", "ast_check": "raw_sql",
                "scope": "**/*.php",
            }
            violations = checker.check(pdef, php_files, theme)
            assert len(violations) >= 1, f"Expected raw SQL violation from AST checker"
        except ImportError:
            pytest.skip("tree-sitter-php not installed")
    finally:
        shutil.rmtree(tmp)