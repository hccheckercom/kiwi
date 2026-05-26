"""Tests for AST checker (tree-sitter PHP)."""
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from scanner.checkers.ast_checker import AstChecker
    HAS_AST = True
except ImportError:
    HAS_AST = False

import pytest
from scanner.models import Violation


pytestmark = pytest.mark.skipif(not HAS_AST, reason="tree-sitter-php not installed")


# ============================================================
# N+1 detection
# ============================================================

def _make_pattern():
    return {
        "id": "LES-457", "severity": "CRITICAL", "category": "performance",
        "description": "N+1 in loop", "ast_check": "n_plus_one",
        "ast_function": "get_post_meta", "ast_guard": "update_meta_cache",
        "scope": "**/*.php",
    }


def test_ast_n1_in_foreach():
    """get_post_meta inside foreach without cache → violation."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\nforeach ($items as $item) {\n    $x = get_post_meta($item, 'key', true);\n}\n")

        checker = AstChecker()
        violations = checker.check(_make_pattern(), [php], tmp)
        assert len(violations) == 1
        assert "AST: confirmed in loop" in violations[0].description
    finally:
        shutil.rmtree(tmp)


def test_ast_n1_standalone_no_violation():
    """get_post_meta outside loop → no violation."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\n$x = get_post_meta($id, 'key', true);\n$y = get_post_meta($id, 'val', true);\n")

        checker = AstChecker()
        violations = checker.check(_make_pattern(), [php], tmp)
        assert len(violations) == 0
    finally:
        shutil.rmtree(tmp)


def test_ast_n1_with_cache_guard():
    """get_post_meta in loop but file has update_meta_cache → no violation."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\nupdate_meta_cache('post', $ids);\nforeach ($items as $item) {\n    $x = get_post_meta($item, 'key', true);\n}\n")

        checker = AstChecker()
        violations = checker.check(_make_pattern(), [php], tmp)
        assert len(violations) == 0
    finally:
        shutil.rmtree(tmp)


def test_ast_n1_wp_loop_guard():
    """get_post_meta after have_posts() (WP main loop) → no violation."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "single.php")
        with open(php, "w") as f:
            f.write("<?php\nwhile (have_posts()) :\n    the_post();\n    $x = get_post_meta(get_the_ID(), 'key', true);\nendwhile;\n")

        checker = AstChecker()
        violations = checker.check(_make_pattern(), [php], tmp)
        assert len(violations) == 0
    finally:
        shutil.rmtree(tmp)


def test_ast_n1_for_loop():
    """get_post_meta inside for loop → violation."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\nfor ($i=0; $i<count($ids); $i++) {\n    $x = get_post_meta($ids[$i], 'key', true);\n}\n")

        checker = AstChecker()
        violations = checker.check(_make_pattern(), [php], tmp)
        assert len(violations) == 1
    finally:
        shutil.rmtree(tmp)


def test_ast_n1_dedup_per_loop():
    """Multiple get_post_meta in same loop → only 1 violation (dedup per loop)."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\nforeach ($items as $item) {\n    $a = get_post_meta($item, 'k1', true);\n    $b = get_post_meta($item, 'k2', true);\n    $c = get_post_meta($item, 'k3', true);\n}\n")

        checker = AstChecker()
        violations = checker.check(_make_pattern(), [php], tmp)
        assert len(violations) == 1, f"Expected 1 (dedup per loop), got {len(violations)}"
    finally:
        shutil.rmtree(tmp)


def test_ast_n1_two_separate_loops():
    """Two separate loops with get_post_meta → 2 violations."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\nforeach ($a as $x) {\n    get_post_meta($x, 'k', true);\n}\nforeach ($b as $y) {\n    get_post_meta($y, 'k', true);\n}\n")

        checker = AstChecker()
        violations = checker.check(_make_pattern(), [php], tmp)
        assert len(violations) == 2
    finally:
        shutil.rmtree(tmp)


def test_ast_file_level_ignore():
    """@kiwi-ignore should suppress AST checker too."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\n// @kiwi-ignore LES-457\nforeach ($items as $item) {\n    get_post_meta($item, 'k', true);\n}\n")

        checker = AstChecker()
        violations = checker.check(_make_pattern(), [php], tmp)
        assert len(violations) == 0
    finally:
        shutil.rmtree(tmp)


# ============================================================
# Unescaped output
# ============================================================

def test_ast_unescaped_echo():
    """echo $var without esc_html → violation."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\necho $user_input;\n")

        checker = AstChecker()
        pdef = {
            "id": "LES-XSS", "severity": "CRITICAL", "category": "php-security",
            "description": "Unescaped output", "ast_check": "unescaped_output",
            "scope": "**/*.php",
        }
        violations = checker.check(pdef, [php], tmp)
        assert len(violations) >= 1
    finally:
        shutil.rmtree(tmp)


def test_ast_escaped_echo():
    """echo esc_html($var) → no violation."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\necho esc_html($user_input);\n")

        checker = AstChecker()
        pdef = {
            "id": "LES-XSS", "severity": "CRITICAL", "category": "php-security",
            "description": "Unescaped output", "ast_check": "unescaped_output",
            "scope": "**/*.php",
        }
        violations = checker.check(pdef, [php], tmp)
        assert len(violations) == 0
    finally:
        shutil.rmtree(tmp)


# ============================================================
# Raw SQL
# ============================================================

def test_ast_raw_sql_detected():
    """$wpdb->query with variable in string without prepare → violation."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write('<?php\nglobal $wpdb;\n$wpdb->query("DELETE FROM {$wpdb->prefix}orders WHERE id = $id");\n')

        checker = AstChecker()
        pdef = {
            "id": "LES-459", "severity": "CRITICAL", "category": "php-security",
            "description": "Raw SQL", "ast_check": "raw_sql",
            "scope": "**/*.php",
        }
        violations = checker.check(pdef, [php], tmp)
        assert len(violations) >= 1
    finally:
        shutil.rmtree(tmp)


def test_ast_raw_sql_prepared_safe():
    """$wpdb->query with prepare() → no violation."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write('<?php\nglobal $wpdb;\n$wpdb->query($wpdb->prepare("DELETE FROM {$wpdb->prefix}orders WHERE id = %d", $id));\n')

        checker = AstChecker()
        pdef = {
            "id": "LES-459", "severity": "CRITICAL", "category": "php-security",
            "description": "Raw SQL", "ast_check": "raw_sql",
            "scope": "**/*.php",
        }
        violations = checker.check(pdef, [php], tmp)
        assert len(violations) == 0
    finally:
        shutil.rmtree(tmp)


# ============================================================
# Nonce missing
# ============================================================

def _make_nonce_pattern():
    return {
        "id": "LES-460", "severity": "CRITICAL", "category": "php-security",
        "description": "Missing nonce", "ast_check": "nonce_missing",
        "scope": "**/*.php",
    }


def test_ast_nonce_missing_in_ajax():
    """AJAX handler without nonce → violation."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("""<?php
add_action( 'wp_ajax_wz_add_item', 'handle_add_item' );
function handle_add_item() {
    $id = absint( $_POST['id'] );
    wp_send_json_success( array( 'id' => $id ) );
}
""")

        checker = AstChecker()
        violations = checker.check(_make_nonce_pattern(), [php], tmp)
        assert len(violations) >= 1
        assert "missing nonce" in violations[0].description.lower()
    finally:
        shutil.rmtree(tmp)


def test_ast_nonce_present_no_violation():
    """AJAX handler with check_ajax_referer → no violation."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("""<?php
add_action( 'wp_ajax_wz_add_item', 'handle_add_item' );
function handle_add_item() {
    check_ajax_referer( 'wz_add', 'nonce' );
    $id = absint( $_POST['id'] );
    wp_send_json_success( array( 'id' => $id ) );
}
""")

        checker = AstChecker()
        violations = checker.check(_make_nonce_pattern(), [php], tmp)
        assert len(violations) == 0
    finally:
        shutil.rmtree(tmp)


def test_ast_nonce_wp_verify_nonce_ok():
    """wp_verify_nonce is also valid nonce check."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("""<?php
add_action( 'wp_ajax_wz_update', 'handle_update' );
function handle_update() {
    if ( ! wp_verify_nonce( $_POST['_wpnonce'], 'wz_update' ) ) {
        wp_send_json_error( 'Invalid nonce' );
    }
    wp_send_json_success();
}
""")

        checker = AstChecker()
        violations = checker.check(_make_nonce_pattern(), [php], tmp)
        assert len(violations) == 0
    finally:
        shutil.rmtree(tmp)


def test_ast_nonce_non_ajax_function_ignored():
    """Regular function (no wp_send_json) should not flag."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("""<?php
add_action( 'wp_ajax_wz_test', 'handle_test' );
function get_product_title( $id ) {
    return get_the_title( $id );
}
""")

        checker = AstChecker()
        violations = checker.check(_make_nonce_pattern(), [php], tmp)
        assert len(violations) == 0
    finally:
        shutil.rmtree(tmp)


# ============================================================
# Direct superglobal
# ============================================================

def _make_superglobal_pattern():
    return {
        "id": "LES-461", "severity": "CRITICAL", "category": "php-security",
        "description": "Unsanitized superglobal", "ast_check": "direct_superglobal",
        "scope": "**/*.php",
    }


def test_ast_direct_superglobal_post():
    """$_POST['x'] without sanitize → violation."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\n$name = $_POST['name'];\n")

        checker = AstChecker()
        violations = checker.check(_make_superglobal_pattern(), [php], tmp)
        assert len(violations) >= 1
    finally:
        shutil.rmtree(tmp)


def test_ast_direct_superglobal_get():
    """$_GET['x'] without sanitize → violation."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\n$page = $_GET['page'];\n")

        checker = AstChecker()
        violations = checker.check(_make_superglobal_pattern(), [php], tmp)
        assert len(violations) >= 1
    finally:
        shutil.rmtree(tmp)


def test_ast_superglobal_sanitized_no_violation():
    """$_POST with sanitize_text_field → no violation."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\n$name = sanitize_text_field( wp_unslash( $_POST['name'] ) );\n")

        checker = AstChecker()
        violations = checker.check(_make_superglobal_pattern(), [php], tmp)
        assert len(violations) == 0
    finally:
        shutil.rmtree(tmp)


def test_ast_superglobal_absint_no_violation():
    """$_GET with absint → no violation."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\n$id = absint( $_GET['id'] );\n")

        checker = AstChecker()
        violations = checker.check(_make_superglobal_pattern(), [php], tmp)
        assert len(violations) == 0
    finally:
        shutil.rmtree(tmp)


def test_ast_superglobal_dedup_per_line():
    """Multiple $_POST accesses on same line → only 1 violation."""
    tmp = tempfile.mkdtemp()
    try:
        php = os.path.join(tmp, "test.php")
        with open(php, "w") as f:
            f.write("<?php\n$x = $_POST['a'] . $_POST['b'];\n$y = $_GET['c'];\n")

        checker = AstChecker()
        violations = checker.check(_make_superglobal_pattern(), [php], tmp)
        assert len(violations) == 2, f"Expected 2 (1 per line), got {len(violations)}"
    finally:
        shutil.rmtree(tmp)