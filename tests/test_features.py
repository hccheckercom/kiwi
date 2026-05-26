"""Tests for new Kiwi features: file-level ignore, cross-file guard, dedup, fixer improvements."""
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner.checkers.presence import PresenceChecker, _has_file_level_ignore
from scanner.checkers.absence import AbsenceChecker
from scanner.checkers.cross_check import CrossChecker
from scanner.fixer import apply_fix, _find_anchor, _already_has_fix, FixResult
from scanner.models import Violation


# ============================================================
# FILE-LEVEL @kiwi-ignore (presence checker)
# ============================================================

def test_file_level_ignore_presence():
    """File with @kiwi-ignore LES-445 in header should skip all matches."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\n// @kiwi-ignore LES-445\n$x = get_post_meta($id, 'key', true);\n")

        checker = PresenceChecker()
        pattern_def = {
            "id": "LES-445", "severity": "CRITICAL", "category": "performance",
            "description": "N+1", "pattern": r"get_post_meta\s*\(", "scope": "**/*.php",
        }
        violations = checker.check(pattern_def, [php], tmp)
        assert len(violations) == 0, f"Expected 0 violations, got {len(violations)}"
    finally:
        shutil.rmtree(tmp)


def test_file_level_ignore_wrong_lesson():
    """@kiwi-ignore for different lesson should NOT suppress."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\n// @kiwi-ignore LES-999\n$x = get_post_meta($id, 'key', true);\n")

        checker = PresenceChecker()
        pattern_def = {
            "id": "LES-445", "severity": "CRITICAL", "category": "performance",
            "description": "N+1", "pattern": r"get_post_meta\s*\(", "scope": "**/*.php",
        }
        violations = checker.check(pattern_def, [php], tmp)
        assert len(violations) == 1
    finally:
        shutil.rmtree(tmp)


def test_file_level_ignore_all():
    """@kiwi-ignore all should suppress all lessons."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\n// @kiwi-ignore all\n$x = get_post_meta($id, 'key', true);\n")

        checker = PresenceChecker()
        pattern_def = {
            "id": "LES-445", "severity": "CRITICAL", "category": "performance",
            "description": "N+1", "pattern": r"get_post_meta\s*\(", "scope": "**/*.php",
        }
        violations = checker.check(pattern_def, [php], tmp)
        assert len(violations) == 0
    finally:
        shutil.rmtree(tmp)


def test_file_level_ignore_absence():
    """File-level @kiwi-ignore in absence checker."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "order.php")
        with open(php, "w") as f:
            f.write("<?php\n// @kiwi-ignore LES-002\n$order_id = $_GET['order_id'];\n")

        checker = AbsenceChecker()
        pattern_def = {
            "id": "LES-002", "severity": "CRITICAL", "category": "php-security",
            "description": "Missing ownership check",
            "pattern": r"get_current_user_id", "scope": "**/*.php",
        }
        violations = checker.check(pattern_def, [php], tmp)
        assert len(violations) == 0
    finally:
        shutil.rmtree(tmp)


# ============================================================
# DEDUP MODE
# ============================================================

def test_dedup_per_file():
    """dedup: per_file should report max 1 violation per file."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\n$a = get_post_meta($id, 'k1', true);\n$b = get_post_meta($id, 'k2', true);\n$c = get_post_meta($id, 'k3', true);\n")

        checker = PresenceChecker()
        pattern_def = {
            "id": "LES-445", "severity": "CRITICAL", "category": "performance",
            "description": "N+1", "pattern": r"get_post_meta\s*\(", "scope": "**/*.php",
            "dedup": "per_file",
        }
        violations = checker.check(pattern_def, [php], tmp)
        assert len(violations) == 1, f"Expected 1 deduped violation, got {len(violations)}"
    finally:
        shutil.rmtree(tmp)


def test_no_dedup_reports_all():
    """Without dedup, all matches should be reported."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\n$a = get_post_meta($id, 'k1', true);\n$b = get_post_meta($id, 'k2', true);\n$c = get_post_meta($id, 'k3', true);\n")

        checker = PresenceChecker()
        pattern_def = {
            "id": "LES-445", "severity": "CRITICAL", "category": "performance",
            "description": "N+1", "pattern": r"get_post_meta\s*\(", "scope": "**/*.php",
        }
        violations = checker.check(pattern_def, [php], tmp)
        assert len(violations) == 3
    finally:
        shutil.rmtree(tmp)


# ============================================================
# CROSS-FILE CONTEXT GUARD
# ============================================================

def test_cross_file_guard_template_part():
    """Template-part with get_post_meta should be suppressed if caller has update_meta_cache."""
    tmp = tempfile.mkdtemp()
    try:
        tp_dir = os.path.join(tmp, "template-parts")
        os.makedirs(tp_dir)
        card = os.path.join(tp_dir, "card.php")
        with open(card, "w") as f:
            f.write("<?php\n$price = get_post_meta($id, '_price', true);\n")

        page = os.path.join(tmp, "page-shop.php")
        with open(page, "w") as f:
            f.write("<?php\n$ids = wp_list_pluck($q->posts, 'ID');\nupdate_meta_cache('post', $ids);\nwhile ($q->have_posts()) { $q->the_post();\nget_template_part('template-parts/card');\n}\n")

        checker = PresenceChecker()
        pattern_def = {
            "id": "LES-445", "severity": "CRITICAL", "category": "performance",
            "description": "N+1", "pattern": r"get_post_meta\s*\(", "scope": "**/*.php",
            "context_guard": {
                "pattern": r"update_meta_cache|have_posts\s*\(",
                "lines_before": 300, "lines_after": 0,
                "cross_file": True,
            },
        }
        violations = checker.check(pattern_def, [card], tmp)
        assert len(violations) == 0, f"Expected 0 (caller has cache), got {len(violations)}"
    finally:
        shutil.rmtree(tmp)


def test_cross_file_guard_no_caller_cache():
    """Template-part should flag if NO caller has update_meta_cache."""
    tmp = tempfile.mkdtemp()
    try:
        tp_dir = os.path.join(tmp, "template-parts")
        os.makedirs(tp_dir)
        card = os.path.join(tp_dir, "card.php")
        with open(card, "w") as f:
            f.write("<?php\n$price = get_post_meta($id, '_price', true);\n")

        page = os.path.join(tmp, "page-shop.php")
        with open(page, "w") as f:
            f.write("<?php\nwhile ($q->have_posts()) { $q->the_post();\nget_template_part('template-parts/card');\n}\n")

        checker = PresenceChecker()
        pattern_def = {
            "id": "LES-445", "severity": "CRITICAL", "category": "performance",
            "description": "N+1", "pattern": r"get_post_meta\s*\(", "scope": "**/*.php",
            "context_guard": {
                "pattern": r"update_meta_cache",
                "lines_before": 300, "lines_after": 0,
                "cross_file": True,
            },
        }
        violations = checker.check(pattern_def, [card], tmp)
        assert len(violations) == 1, f"Expected 1 (no cache), got {len(violations)}"
    finally:
        shutil.rmtree(tmp)


# ============================================================
# CONTEXT GUARD (same-file)
# ============================================================

def test_context_guard_same_file():
    """get_post_meta should be suppressed if have_posts() is in same file above."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "single.php")
        with open(php, "w") as f:
            f.write("<?php\nwhile (have_posts()) :\nthe_post();\n$price = get_post_meta($id, '_price', true);\nendwhile;\n")

        checker = PresenceChecker()
        pattern_def = {
            "id": "LES-445", "severity": "CRITICAL", "category": "performance",
            "description": "N+1", "pattern": r"get_post_meta\s*\(", "scope": "**/*.php",
            "context_guard": {
                "pattern": r"have_posts\s*\(",
                "lines_before": 300, "lines_after": 0,
            },
        }
        violations = checker.check(pattern_def, [php], tmp)
        assert len(violations) == 0
    finally:
        shutil.rmtree(tmp)


# ============================================================
# FIXER: _find_anchor
# ============================================================

def test_find_anchor_near_target():
    lines = [
        "<?php\n", "function test() {\n", "    foreach ($items as $item) {\n",
        "        $x = get_post_meta($item, 'key', true);\n", "    }\n", "}\n",
    ]
    idx = _find_anchor(lines, r"foreach|for\s*\(", target_line=4)
    assert idx == 2, f"Expected line 2 (foreach), got {idx}"


def test_find_anchor_expanding_window():
    """Anchor far from target should still be found via expanding windows."""
    lines = ["<?php\n"] * 30
    lines[0] = "foreach ($items as $item) {\n"
    lines[25] = "    $x = get_post_meta($id, 'key', true);\n"

    idx = _find_anchor(lines, r"foreach", target_line=26)
    assert idx == 0, f"Expected 0 (far foreach), got {idx}"


def test_find_anchor_not_found():
    lines = ["<?php\n", "$x = 1;\n", "$y = 2;\n"]
    idx = _find_anchor(lines, r"foreach|for\s*\(", target_line=2)
    assert idx is None


# ============================================================
# FIXER: _already_has_fix
# ============================================================

def test_already_has_fix_true():
    lines = [
        "<?php\n", "$ids = wp_list_pluck($posts, 'ID');\n",
        "update_meta_cache('post', $ids);\n",
        "foreach ($posts as $p) {\n",
    ]
    code = "update_meta_cache('post', $ids);"
    assert _already_has_fix(lines, 3, code) is True


def test_already_has_fix_false():
    lines = ["<?php\n", "foreach ($posts as $p) {\n", "    echo $p;\n", "}\n"]
    code = "update_meta_cache('post', $ids);"
    assert _already_has_fix(lines, 1, code) is False


# ============================================================
# FIXER: apply_fix replace
# ============================================================

def test_apply_fix_replace_dry_run():
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\n$x = old_function();\n")

        v = Violation("LES-001", "CRITICAL", "test", "desc", php, 2)
        fix_config = {"type": "replace", "search": "old_function", "replace": "new_function"}
        result = apply_fix(v, fix_config, dry_run=True)

        assert result.success is True
        assert result.fix_type == "replace"
        # File should not be modified in dry_run
        with open(php) as f:
            assert "old_function" in f.read()
    finally:
        shutil.rmtree(tmp)


def test_apply_fix_replace_apply():
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\n$x = old_function();\n")

        v = Violation("LES-001", "CRITICAL", "test", "desc", php, 2)
        fix_config = {"type": "replace", "search": "old_function", "replace": "new_function"}
        result = apply_fix(v, fix_config, dry_run=False)

        assert result.success is True
        with open(php) as f:
            content = f.read()
        assert "new_function" in content
        assert "old_function" not in content
    finally:
        shutil.rmtree(tmp)


def test_apply_fix_file_not_found():
    v = Violation("LES-001", "CRITICAL", "test", "desc", "/nonexistent/file.php", 1)
    fix_config = {"type": "replace", "search": "x", "replace": "y"}
    result = apply_fix(v, fix_config, dry_run=True)
    assert result.success is False
    assert "not found" in result.error.lower()


# ============================================================
# FIXER: apply_fix template
# ============================================================

def test_apply_fix_template_before():
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\nforeach ($items as $item) {\n    echo $item;\n}\n")

        v = Violation("LES-445", "CRITICAL", "performance", "N+1", php, 3)
        fix_config = {
            "type": "template", "position": "before",
            "anchor": r"foreach",
            "code": "update_meta_cache('post', $ids);",
            "indent": "auto",
        }
        result = apply_fix(v, fix_config, dry_run=False)
        assert result.success is True

        with open(php) as f:
            content = f.read()
        assert "update_meta_cache" in content
        lines = content.splitlines()
        foreach_idx = next(i for i, l in enumerate(lines) if "foreach" in l)
        cache_idx = next(i for i, l in enumerate(lines) if "update_meta_cache" in l)
        assert cache_idx < foreach_idx, "Cache should be before foreach"
    finally:
        shutil.rmtree(tmp)


# ============================================================
# LINE-LEVEL @kiwi-ignore
# ============================================================

def test_line_level_ignore():
    """Line-level @kiwi-ignore should suppress only that line, not if file-level catches it first."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            # Put ignore comment on line 12 (past first 10 lines, so file-level ignore won't trigger)
            lines = ["<?php\n"] + [f"// line {i}\n" for i in range(2, 12)]
            lines.append("$a = get_post_meta($id, 'k1', true); // @kiwi-ignore LES-445\n")
            lines.append("$b = get_post_meta($id, 'k2', true);\n")
            f.writelines(lines)

        checker = PresenceChecker()
        pattern_def = {
            "id": "LES-445", "severity": "CRITICAL", "category": "performance",
            "description": "N+1", "pattern": r"get_post_meta\s*\(", "scope": "**/*.php",
        }
        violations = checker.check(pattern_def, [php], tmp)
        assert len(violations) == 1, f"Expected 1 (line 13 only), got {len(violations)}"
        assert violations[0].line == 13
    finally:
        shutil.rmtree(tmp)


# ============================================================
# CROSS-CHECK CHECKER: file-level ignore
# ============================================================

def test_cross_check_file_level_ignore():
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "order.php")
        with open(php, "w") as f:
            f.write("<?php\n// @kiwi-ignore LES-016\n$order_id = isset($_GET['order_id']) ? (int) $_GET['order_id'] : 0;\n")

        checker = CrossChecker()
        pattern_def = {
            "id": "LES-016", "severity": "CRITICAL", "category": "php-security",
            "description": "IDOR check",
            "pattern": r"\$_GET\['order_id'\]",
            "scope": "**/*.php",
            "cross_check": r"user_id.*get_current_user_id|get_current_user_id.*user_id",
        }
        violations = checker.check(pattern_def, [php], tmp)
        assert len(violations) == 0
    finally:
        shutil.rmtree(tmp)