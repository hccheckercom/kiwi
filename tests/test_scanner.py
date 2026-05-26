"""Comprehensive unit tests for Kiwi Scanner v2 - 102 tests."""
import json
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner.loader import load_patterns, _parse_frontmatter, _matches_platform, _matches_scope_type
from scanner.resolver import resolve_scope, rewrite_scope_for_theme, _is_globally_excluded
from scanner.checkers.presence import PresenceChecker
from scanner.checkers.absence import AbsenceChecker
from scanner.checkers.bom import BomChecker
from scanner.checkers.cross_check import CrossChecker
from scanner.checkers import get_checker
from scanner.reporters import get_reporter
from scanner.reporters.text import TextReporter
from scanner.reporters.json import JsonReporter
from scanner.models import Violation, Report


# ============================================================
# MODULE 1: Loader (12 tests)
# ============================================================

def test_parse_frontmatter_basic():
    content = "---\nid: LES-001\nseverity: CRITICAL\ncategory: php-security\ntitle: 'Test'\ntags: [theme]\nscan:\n  type: \"presence\"\n  pattern: 'is_user_logged_in'\n  scope: \"**/*.php\"\n---\n\nBody"
    fm = _parse_frontmatter(content)
    assert fm["id"] == "LES-001"
    assert fm["severity"] == "CRITICAL"
    assert fm["scan"]["type"] == "presence"
    assert fm["scan"]["pattern"] == "is_user_logged_in"
    print("  PASS: test_parse_frontmatter_basic")


def test_parse_frontmatter_no_delimiters():
    fm = _parse_frontmatter("No frontmatter here, just text.")
    assert fm == {}
    print("  PASS: test_parse_frontmatter_no_delimiters")


def test_parse_frontmatter_single_quoted_regex():
    content = "---\nid: LES-209\nseverity: HIGH\nscan:\n  type: \"presence\"\n  pattern: '<img[^>]*\\s*>'\n  scope: \"**/*.tsx\"\n---\n"
    fm = _parse_frontmatter(content)
    assert fm is not None and "scan" in fm
    assert "\\s" in fm["scan"]["pattern"]
    print("  PASS: test_parse_frontmatter_single_quoted_regex")


def test_parse_frontmatter_invalid_yaml():
    content = "---\nid: [invalid\n  yaml: {{broken\n---\n"
    fm = _parse_frontmatter(content)
    assert fm == {}
    print("  PASS: test_parse_frontmatter_invalid_yaml")


def test_load_patterns_basic():
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, "test-cat"))
        with open(os.path.join(tmp, "test-cat", "TEST-001.md"), "w", encoding="utf-8") as f:
            f.write("---\nid: TEST-001\nseverity: HIGH\ncategory: test-cat\ntitle: 'Test'\nscan:\n  type: \"presence\"\n  pattern: 'bad_func'\n  scope: \"**/*.php\"\n---\nBody\n")
        patterns = load_patterns(lessons_dir=tmp)
        assert len(patterns) == 1
        assert patterns[0]["id"] == "TEST-001"
        assert patterns[0]["pattern"] == "bad_func"
    finally:
        shutil.rmtree(tmp)
    print("  PASS: test_load_patterns_basic")


def test_load_patterns_skips_block_type():
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, "cat"))
        with open(os.path.join(tmp, "cat", "BLOCK.md"), "w", encoding="utf-8") as f:
            f.write("---\nid: BLOCK-1\nseverity: HIGH\nscan:\n  type: \"block\"\n  pattern: 'x'\n---\n")
        patterns = load_patterns(lessons_dir=tmp)
        assert len(patterns) == 0
    finally:
        shutil.rmtree(tmp)
    print("  PASS: test_load_patterns_skips_block_type")


def test_load_patterns_skips_pattern_type():
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, "cat"))
        with open(os.path.join(tmp, "cat", "PAT.md"), "w", encoding="utf-8") as f:
            f.write("---\nid: PAT-1\nseverity: HIGH\nscan:\n  type: \"pattern\"\n  pattern: 'x'\n---\n")
        patterns = load_patterns(lessons_dir=tmp)
        assert len(patterns) == 0
    finally:
        shutil.rmtree(tmp)
    print("  PASS: test_load_patterns_skips_pattern_type")


def test_load_patterns_skips_manual_type():
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, "cat"))
        with open(os.path.join(tmp, "cat", "MAN.md"), "w", encoding="utf-8") as f:
            f.write("---\nid: MAN-1\nseverity: HIGH\nscan:\n  type: \"manual\"\n  pattern: 'x'\n---\n")
        patterns = load_patterns(lessons_dir=tmp)
        assert len(patterns) == 0
    finally:
        shutil.rmtree(tmp)
    print("  PASS: test_load_patterns_skips_manual_type")


def test_load_patterns_skips_scan_block_true():
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, "cat"))
        with open(os.path.join(tmp, "cat", "BLK.md"), "w", encoding="utf-8") as f:
            f.write("---\nid: BLK-1\nseverity: HIGH\nscan:\n  block: true\n  pattern: 'x'\n---\n")
        patterns = load_patterns(lessons_dir=tmp)
        assert len(patterns) == 0
    finally:
        shutil.rmtree(tmp)
    print("  PASS: test_load_patterns_skips_scan_block_true")


def test_matches_platform_wp():
    assert _matches_platform({"platform": "wp"}, "any", "wp") is True
    assert _matches_platform({"platform": "nextjs"}, "any", "wp") is False
    assert _matches_platform({"platform": "both"}, "any", "wp") is True
    assert _matches_platform({}, "php-security", "wp") is True
    assert _matches_platform({}, "ads-compliance", "wp") is True
    assert _matches_platform({}, "feature-suggest", "wp") is True
    assert _matches_platform({}, "nextjs-react", "wp") is False
    assert _matches_platform({"tags": ["theme"]}, "any", "wp") is True
    assert _matches_platform({"tags": ["webstore"]}, "any", "wp") is False
    print("  PASS: test_matches_platform_wp")


def test_matches_platform_nextjs():
    assert _matches_platform({"platform": "nextjs"}, "any", "nextjs") is True
    assert _matches_platform({"platform": "wp"}, "any", "nextjs") is False
    assert _matches_platform({}, "nextjs-react", "nextjs") is True
    assert _matches_platform({}, "supabase", "nextjs") is True
    assert _matches_platform({}, "php-security", "nextjs") is False
    assert _matches_platform({"tags": ["webstore"]}, "any", "nextjs") is True
    assert _matches_platform({"tags": ["theme"]}, "any", "nextjs") is False
    print("  PASS: test_matches_platform_nextjs")


def test_matches_platform_both_tag():
    assert _matches_platform({"tags": ["webstore", "both"]}, "ads-compliance", "wp") is True
    assert _matches_platform({"tags": ["webstore", "both"]}, "ads-compliance", "nextjs") is True
    assert _matches_platform({"tags": ["both"]}, "unknown", "wp") is True
    assert _matches_platform({"tags": ["both"]}, "unknown", "nextjs") is True
    print("  PASS: test_matches_platform_both_tag")


# ============================================================
# MODULE 2: Resolver (14 tests)
# ============================================================

def test_resolve_scope_single_glob():
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, "inc"))
        os.makedirs(os.path.join(tmp, "inc", "sub"))
        open(os.path.join(tmp, "functions.php"), "w").close()
        open(os.path.join(tmp, "inc", "setup.php"), "w").close()
        open(os.path.join(tmp, "inc", "sub", "deep.php"), "w").close()
        files = resolve_scope(tmp, "**/*.php")
        assert len(files) == 3, f"Expected 3, got {len(files)}"
    finally:
        shutil.rmtree(tmp)
    print("  PASS: test_resolve_scope_single_glob")


def test_resolve_scope_pipe_separator():
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, "inc"))
        open(os.path.join(tmp, "header.php"), "w").close()
        open(os.path.join(tmp, "inc", "seo.php"), "w").close()
        files = resolve_scope(tmp, "header.php|inc/seo.php")
        assert len(files) == 2, f"Expected 2, got {len(files)}"
    finally:
        shutil.rmtree(tmp)
    print("  PASS: test_resolve_scope_pipe_separator")


def test_resolve_scope_comma_not_separator():
    tmp = tempfile.mkdtemp()
    try:
        open(os.path.join(tmp, "a.php"), "w").close()
        open(os.path.join(tmp, "b.php"), "w").close()
        files = resolve_scope(tmp, "a.php,b.php")
        assert len(files) == 0, f"Comma should not split, got {len(files)} files"
    finally:
        shutil.rmtree(tmp)
    print("  PASS: test_resolve_scope_comma_not_separator")


def test_resolve_scope_exact_file():
    tmp = tempfile.mkdtemp()
    try:
        open(os.path.join(tmp, "functions.php"), "w").close()
        open(os.path.join(tmp, "style.css"), "w").close()
        files = resolve_scope(tmp, "functions.php")
        assert len(files) == 1
        assert "functions.php" in files[0]
    finally:
        shutil.rmtree(tmp)
    print("  PASS: test_resolve_scope_exact_file")


def test_resolve_scope_directory():
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, "inc"))
        open(os.path.join(tmp, "inc", "a.php"), "w").close()
        open(os.path.join(tmp, "inc", "b.php"), "w").close()
        files = resolve_scope(tmp, "inc")
        assert len(files) == 2
    finally:
        shutil.rmtree(tmp)
    print("  PASS: test_resolve_scope_directory")


def test_resolve_scope_excludes_node_modules():
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, "node_modules", "pkg"))
        os.makedirs(os.path.join(tmp, "src"))
        open(os.path.join(tmp, "node_modules", "pkg", "index.js"), "w").close()
        open(os.path.join(tmp, "src", "app.js"), "w").close()
        files = resolve_scope(tmp, "**/*.js")
        rel = [os.path.relpath(f, tmp).replace("\\", "/") for f in files]
        assert "src/app.js" in rel
        assert not any("node_modules" in f for f in rel)
    finally:
        shutil.rmtree(tmp)
    print("  PASS: test_resolve_scope_excludes_node_modules")


def test_resolve_scope_excludes_disabled_prefix():
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, ".disabled-old"))
        os.makedirs(os.path.join(tmp, "active"))
        open(os.path.join(tmp, ".disabled-old", "old.php"), "w").close()
        open(os.path.join(tmp, "active", "new.php"), "w").close()
        files = resolve_scope(tmp, "**/*.php")
        rel = [os.path.relpath(f, tmp).replace("\\", "/") for f in files]
        assert "active/new.php" in rel
        assert not any(".disabled-" in f for f in rel)
    finally:
        shutil.rmtree(tmp)
    print("  PASS: test_resolve_scope_excludes_disabled_prefix")


def test_resolve_scope_exclude_pattern():
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, "inc"))
        open(os.path.join(tmp, "inc", "setup.php"), "w").close()
        open(os.path.join(tmp, "inc", "wz-shims.php"), "w").close()
        files = resolve_scope(tmp, "inc/*.php", exclude="inc/wz-shims.php")
        assert len(files) == 1
        assert "setup.php" in files[0]
    finally:
        shutil.rmtree(tmp)
    print("  PASS: test_resolve_scope_exclude_pattern")


def test_resolve_scope_empty():
    tmp = tempfile.mkdtemp()
    try:
        files = resolve_scope(tmp, "")
        assert files == []
    finally:
        shutil.rmtree(tmp)
    print("  PASS: test_resolve_scope_empty")


def test_resolve_scope_theme_root():
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, "inc"))
        open(os.path.join(tmp, "functions.php"), "w").close()
        open(os.path.join(tmp, "style.css"), "w").close()
        open(os.path.join(tmp, "inc", "deep.php"), "w").close()
        files = resolve_scope(tmp, "theme root")
        rel = [os.path.basename(f) for f in files]
        assert "functions.php" in rel
        assert "style.css" in rel
        assert "deep.php" not in rel
    finally:
        shutil.rmtree(tmp)
    print("  PASS: test_resolve_scope_theme_root")


def test_resolve_scope_nonexistent_dir():
    tmp = tempfile.mkdtemp()
    try:
        files = resolve_scope(tmp, "nonexistent/**/*.php")
        assert files == []
    finally:
        shutil.rmtree(tmp)
    print("  PASS: test_resolve_scope_nonexistent_dir")


def test_rewrite_scope_for_theme():
    assert rewrite_scope_for_theme("themes/*/functions.php") == "functions.php"
    assert rewrite_scope_for_theme("themes/**/style.css") == "style.css"
    result = rewrite_scope_for_theme("themes/*/inc/*.php|themes/*/assets/*.css")
    assert "inc/*.php" in result
    assert "assets/*.css" in result
    assert "themes/" not in result
    print("  PASS: test_rewrite_scope_for_theme")


def test_rewrite_scope_deduplicates():
    result = rewrite_scope_for_theme("themes/*/functions.php|themes/**/functions.php")
    parts = result.split("|")
    assert len(parts) == 1, f"Expected dedup to 1 part, got {len(parts)}: {parts}"
    assert parts[0] == "functions.php"
    print("  PASS: test_rewrite_scope_deduplicates")


def test_is_globally_excluded():
    assert _is_globally_excluded("/tmp/theme/node_modules/x.js", "/tmp/theme") is True
    assert _is_globally_excluded("/tmp/theme/.git/config", "/tmp/theme") is True
    assert _is_globally_excluded("/tmp/theme/vendor/lib.php", "/tmp/theme") is True
    assert _is_globally_excluded("/tmp/theme/.disabled-old/x.php", "/tmp/theme") is True
    assert _is_globally_excluded("/tmp/theme/src/app.js", "/tmp/theme") is False
    assert _is_globally_excluded("/tmp/theme/inc/setup.php", "/tmp/theme") is False
    print("  PASS: test_is_globally_excluded")
