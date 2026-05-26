"""Test Phase 3 AST checks."""

import os
import sys
from pathlib import Path

# Add kiwi to path
KIWI_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(KIWI_DIR))

from scanner.checkers.ast_checker import AstChecker
from scanner.models import Violation


def test_idor_no_auth():
    """Test LES-001: Account template without is_user_logged_in()."""
    checker = AstChecker()

    # Create test PHP file
    test_file = KIWI_DIR / "tests" / "fixtures" / "account_no_auth.php"
    test_file.parent.mkdir(exist_ok=True)

    test_file.write_text("""<?php
// Account orders page - MISSING auth check
$orders = wz_get_user_orders( get_current_user_id() );
foreach ( $orders as $order ) {
    echo esc_html( $order['id'] );
}
""", encoding="utf-8")

    pattern_def = {
        "id": "LES-001",
        "severity": "CRITICAL",
        "category": "php-security",
        "description": "Account template without auth gate",
        "ast_check": "idor_no_auth",
    }

    violations = checker.check(pattern_def, [str(test_file)], str(KIWI_DIR))

    assert len(violations) == 1
    assert violations[0].lesson_id == "LES-001"
    print("[PASS] test_idor_no_auth")


def test_wpdb_insert_in_loop():
    """Test LES-080: $wpdb->insert() in loop."""
    checker = AstChecker()

    test_file = KIWI_DIR / "tests" / "fixtures" / "wpdb_loop.php"
    test_file.parent.mkdir(exist_ok=True)

    test_file.write_text("""<?php
global $wpdb;
$rows = [['id' => 1], ['id' => 2]];
foreach ( $rows as $row ) {
    $wpdb->insert("{$wpdb->prefix}analytics", $row);
}
""", encoding="utf-8")

    pattern_def = {
        "id": "LES-080",
        "severity": "HIGH",
        "category": "performance",
        "description": "$wpdb->insert in loop",
        "ast_check": "wpdb_insert_in_loop",
    }

    violations = checker.check(pattern_def, [str(test_file)], str(KIWI_DIR))

    assert len(violations) == 1
    assert violations[0].lesson_id == "LES-080"
    print("[PASS] test_wpdb_insert_in_loop")


def test_n_plus_one_wz_get_product():
    """Test LES-049: wz_get_product() in loop."""
    checker = AstChecker()

    test_file = KIWI_DIR / "tests" / "fixtures" / "n_plus_one.php"
    test_file.parent.mkdir(exist_ok=True)

    test_file.write_text("""<?php
$ids = [1, 2, 3];
foreach ( $ids as $id ) {
    $product = wz_get_product( $id );
    echo $product['name'];
}
""", encoding="utf-8")

    pattern_def = {
        "id": "LES-049",
        "severity": "HIGH",
        "category": "performance",
        "description": "N+1 query in loop",
        "ast_check": "n_plus_one",
        "ast_function": "wz_get_product",
        "ast_guard": "wz_get_products_by_ids",
    }

    violations = checker.check(pattern_def, [str(test_file)], str(KIWI_DIR))

    assert len(violations) == 1
    assert violations[0].lesson_id == "LES-049"
    print("[PASS] test_n_plus_one_wz_get_product")


def test_fetch_no_nonce():
    """Test LES-039: fetch() to cart API without nonce."""
    checker = AstChecker()

    test_file = KIWI_DIR / "tests" / "fixtures" / "fetch_no_nonce.js"
    test_file.parent.mkdir(exist_ok=True)

    test_file.write_text("""
// Cart API call without nonce header
fetch('/wp-json/wezone/v1/cart/add', {
    method: 'POST',
    body: JSON.stringify({ product_id: 5, qty: 1 })
});
""", encoding="utf-8")

    pattern_def = {
        "id": "LES-039",
        "severity": "CRITICAL",
        "category": "php-security",
        "description": "fetch without nonce header",
        "ast_check": "fetch_no_nonce",
    }

    violations = checker.check(pattern_def, [str(test_file)], str(KIWI_DIR))

    assert len(violations) == 1
    assert violations[0].lesson_id == "LES-039"
    print("[PASS] test_fetch_no_nonce")


if __name__ == "__main__":
    print("Running Phase 3 AST tests...")
    print("=" * 60)

    try:
        test_idor_no_auth()
        test_wpdb_insert_in_loop()
        test_n_plus_one_wz_get_product()
        test_fetch_no_nonce()

        print("=" * 60)
        print("[SUCCESS] All Phase 3 AST tests passed!")
    except AssertionError as e:
        print(f"[FAIL] Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)