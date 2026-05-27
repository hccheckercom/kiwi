"""Test API security patterns (authentication, authorization, rate limiting)."""

import pytest
from scanner.loader import load_patterns
from scanner.checkers import check_pattern
from pathlib import Path

LESSONS_DIR = Path(__file__).parent.parent / "lessons"


def test_api_missing_auth_check():
    """LES-089: API endpoint missing authentication check."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-089"), None)
    assert pattern is not None, "LES-089 not found"

    bad_code = """
function handle_api_request() {
    $user_id = $_POST['user_id'];
    $data = get_user_data($user_id);
    wp_send_json_success($data);
}
"""

    good_code = """
function handle_api_request() {
    if (!is_user_logged_in()) {
        wp_send_json_error('Unauthorized', 401);
        return;
    }
    $user_id = get_current_user_id();
    $data = get_user_data($user_id);
    wp_send_json_success($data);
}
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect missing auth check"
    assert len(good_violations) == 0, "Should pass with auth check"


def test_api_idor_vulnerability():
    """LES-091: IDOR - user can access other users' data."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-091"), None)
    assert pattern is not None, "LES-091 not found"

    bad_code = """
function get_order_details() {
    $order_id = $_GET['order_id'];
    $order = wz_get_order($order_id);
    return $order;
}
"""

    good_code = """
function get_order_details() {
    $order_id = $_GET['order_id'];
    $order = wz_get_order($order_id);
    if ($order['user_id'] !== get_current_user_id()) {
        wp_send_json_error('Forbidden', 403);
        return;
    }
    return $order;
}
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect IDOR vulnerability"
    assert len(good_violations) == 0, "Should pass with ownership check"


def test_api_rate_limiting():
    """LES-156: API endpoint missing rate limiting."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-156"), None)
    assert pattern is not None, "LES-156 not found"

    bad_code = """
add_action('rest_api_init', function() {
    register_rest_route('wz/v1', '/send-otp', [
        'methods' => 'POST',
        'callback' => 'send_otp_handler',
    ]);
});
"""

    good_code = """
add_action('rest_api_init', function() {
    register_rest_route('wz/v1', '/send-otp', [
        'methods' => 'POST',
        'callback' => 'send_otp_handler',
        'permission_callback' => 'check_rate_limit',
    ]);
});

function check_rate_limit() {
    $key = 'otp_' . get_current_user_id();
    $count = get_transient($key) ?: 0;
    if ($count >= 5) {
        return new WP_Error('rate_limit', 'Too many requests', ['status' => 429]);
    }
    set_transient($key, $count + 1, 300);
    return true;
}
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect missing rate limiting"
    assert len(good_violations) == 0, "Should pass with rate limiting"


def test_api_input_validation():
    """LES-092: API missing input validation."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-092"), None)
    assert pattern is not None, "LES-092 not found"

    bad_code = """
function update_profile() {
    $user_id = $_POST['user_id'];
    $email = $_POST['email'];
    wp_update_user(['ID' => $user_id, 'user_email' => $email]);
}
"""

    good_code = """
function update_profile() {
    $user_id = absint($_POST['user_id']);
    $email = sanitize_email($_POST['email']);
    if (!is_email($email)) {
        wp_send_json_error('Invalid email');
        return;
    }
    wp_update_user(['ID' => $user_id, 'user_email' => $email]);
}
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect missing input validation"
    assert len(good_violations) == 0, "Should pass with validation"


def test_api_response_exposure():
    """LES-158: API exposing sensitive data in response."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-158"), None)
    assert pattern is not None, "LES-158 not found"

    bad_code = """
function get_user_profile() {
    $user = get_userdata(get_current_user_id());
    wp_send_json_success($user);
}
"""

    good_code = """
function get_user_profile() {
    $user = get_userdata(get_current_user_id());
    $safe_data = [
        'id' => $user->ID,
        'name' => $user->display_name,
        'email' => $user->user_email,
    ];
    wp_send_json_success($safe_data);
}
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect sensitive data exposure"
    assert len(good_violations) == 0, "Should pass with filtered response"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])