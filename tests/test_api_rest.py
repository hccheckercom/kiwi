"""Test REST API patterns (endpoints, methods, responses, error handling)."""

import pytest
from scanner.loader import load_patterns
from scanner.checkers import check_pattern
from pathlib import Path

LESSONS_DIR = Path(__file__).parent.parent / "lessons"


def test_rest_missing_permission_callback():
    """LES-157: REST endpoint missing permission_callback."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-157"), None)
    assert pattern is not None, "LES-157 not found"

    bad_code = """
register_rest_route('wz/v1', '/products', [
    'methods' => 'GET',
    'callback' => 'get_products',
]);
"""

    good_code = """
register_rest_route('wz/v1', '/products', [
    'methods' => 'GET',
    'callback' => 'get_products',
    'permission_callback' => '__return_true',
]);
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect missing permission_callback"
    assert len(good_violations) == 0, "Should pass with permission_callback"


def test_rest_unsafe_methods():
    """LES-159: REST endpoint allowing unsafe HTTP methods."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-159"), None)
    assert pattern is not None, "LES-159 not found"

    bad_code = """
register_rest_route('wz/v1', '/delete-account', [
    'methods' => 'GET',
    'callback' => 'delete_account_handler',
]);
"""

    good_code = """
register_rest_route('wz/v1', '/delete-account', [
    'methods' => 'DELETE',
    'callback' => 'delete_account_handler',
    'permission_callback' => 'is_user_logged_in',
]);
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect unsafe HTTP method"
    assert len(good_violations) == 0, "Should pass with correct method"


def test_rest_missing_sanitization():
    """LES-160: REST callback missing input sanitization."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-160"), None)
    assert pattern is not None, "LES-160 not found"

    bad_code = """
function search_products($request) {
    $query = $request['q'];
    $results = wz_search_products($query);
    return rest_ensure_response($results);
}
"""

    good_code = """
function search_products($request) {
    $query = sanitize_text_field($request['q']);
    $results = wz_search_products($query);
    return rest_ensure_response($results);
}
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect missing sanitization"
    assert len(good_violations) == 0, "Should pass with sanitization"


def test_rest_error_handling():
    """LES-161: REST callback missing error handling."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-161"), None)
    assert pattern is not None, "LES-161 not found"

    bad_code = """
function get_order($request) {
    $order_id = $request['id'];
    $order = wz_get_order($order_id);
    return rest_ensure_response($order);
}
"""

    good_code = """
function get_order($request) {
    $order_id = $request['id'];
    $order = wz_get_order($order_id);
    if (!$order) {
        return new WP_Error('not_found', 'Order not found', ['status' => 404]);
    }
    return rest_ensure_response($order);
}
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect missing error handling"
    assert len(good_violations) == 0, "Should pass with error handling"


def test_rest_response_format():
    """LES-162: REST response not using rest_ensure_response."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-162"), None)
    assert pattern is not None, "LES-162 not found"

    bad_code = """
function get_products($request) {
    $products = wz_get_products();
    return $products;
}
"""

    good_code = """
function get_products($request) {
    $products = wz_get_products();
    return rest_ensure_response($products);
}
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect missing rest_ensure_response"
    assert len(good_violations) == 0, "Should pass with rest_ensure_response"


def test_rest_cors_headers():
    """LES-163: REST endpoint missing CORS headers for external access."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-163"), None)
    assert pattern is not None, "LES-163 not found"

    bad_code = """
add_action('rest_api_init', function() {
    register_rest_route('wz/v1', '/public-data', [
        'methods' => 'GET',
        'callback' => 'get_public_data',
        'permission_callback' => '__return_true',
    ]);
});
"""

    good_code = """
add_action('rest_api_init', function() {
    register_rest_route('wz/v1', '/public-data', [
        'methods' => 'GET',
        'callback' => 'get_public_data',
        'permission_callback' => '__return_true',
    ]);
});

add_filter('rest_pre_serve_request', function($served, $result, $request) {
    if (strpos($request->get_route(), '/wz/v1/') === 0) {
        header('Access-Control-Allow-Origin: *');
        header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
    }
    return $served;
}, 10, 3);
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect missing CORS headers"
    assert len(good_violations) == 0, "Should pass with CORS headers"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
