"""Test API webhook and callback patterns (signatures, validation, retry logic)."""

import pytest
from scanner.loader import load_patterns
from scanner.checkers import check_pattern
from pathlib import Path

LESSONS_DIR = Path(__file__).parent.parent / "lessons"


def test_webhook_missing_signature_validation():
    """LES-164: Webhook missing signature validation."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-164"), None)
    assert pattern is not None, "LES-164 not found"

    bad_code = """
function handle_payment_webhook() {
    $payload = file_get_contents('php://input');
    $data = json_decode($payload, true);
    process_payment($data);
}
"""

    good_code = """
function handle_payment_webhook() {
    $payload = file_get_contents('php://input');
    $signature = $_SERVER['HTTP_X_SIGNATURE'] ?? '';

    $expected = hash_hmac('sha256', $payload, WEBHOOK_SECRET);
    if (!hash_equals($expected, $signature)) {
        wp_send_json_error('Invalid signature', 401);
        return;
    }

    $data = json_decode($payload, true);
    process_payment($data);
}
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect missing signature validation"
    assert len(good_violations) == 0, "Should pass with signature validation"


def test_webhook_replay_attack():
    """LES-165: Webhook vulnerable to replay attacks."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-165"), None)
    assert pattern is not None, "LES-165 not found"

    bad_code = """
function handle_webhook() {
    verify_signature();
    $data = json_decode(file_get_contents('php://input'), true);
    process_order($data['order_id']);
}
"""

    good_code = """
function handle_webhook() {
    verify_signature();
    $data = json_decode(file_get_contents('php://input'), true);

    $webhook_id = $data['webhook_id'];
    if (get_transient('webhook_' . $webhook_id)) {
        wp_send_json_error('Duplicate webhook', 409);
        return;
    }
    set_transient('webhook_' . $webhook_id, true, 3600);

    process_order($data['order_id']);
}
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect replay vulnerability"
    assert len(good_violations) == 0, "Should pass with replay protection"


def test_webhook_timeout_handling():
    """LES-166: Webhook processing without timeout handling."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-166"), None)
    assert pattern is not None, "LES-166 not found"

    bad_code = """
function handle_webhook() {
    verify_signature();
    $data = json_decode(file_get_contents('php://input'), true);

    // Long-running process
    process_large_batch($data['items']);

    wp_send_json_success();
}
"""

    good_code = """
function handle_webhook() {
    verify_signature();
    $data = json_decode(file_get_contents('php://input'), true);

    // Queue for background processing
    wp_schedule_single_event(time(), 'process_webhook_batch', [$data['items']]);

    wp_send_json_success(['status' => 'queued']);
}
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect missing timeout handling"
    assert len(good_violations) == 0, "Should pass with async processing"


def test_callback_url_validation():
    """LES-167: Callback URL not validated before redirect."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-167"), None)
    assert pattern is not None, "LES-167 not found"

    bad_code = """
function handle_oauth_callback() {
    $return_url = $_GET['return_url'];
    $token = generate_token();
    wp_redirect($return_url . '?token=' . $token);
    exit;
}
"""

    good_code = """
function handle_oauth_callback() {
    $return_url = $_GET['return_url'];
    $allowed_hosts = ['wezone.vn', 'demo.wezone.vn'];

    $parsed = parse_url($return_url);
    if (!in_array($parsed['host'], $allowed_hosts)) {
        wp_die('Invalid return URL');
    }

    $token = generate_token();
    wp_redirect($return_url . '?token=' . $token);
    exit;
}
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect unvalidated redirect"
    assert len(good_violations) == 0, "Should pass with URL validation"


def test_api_idempotency():
    """LES-168: API endpoint missing idempotency key support."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-168"), None)
    assert pattern is not None, "LES-168 not found"

    bad_code = """
function create_order($request) {
    $order_data = $request->get_json_params();
    $order_id = wz_create_order($order_data);
    return rest_ensure_response(['order_id' => $order_id]);
}
"""

    good_code = """
function create_order($request) {
    $idempotency_key = $request->get_header('X-Idempotency-Key');
    if ($idempotency_key) {
        $cached = get_transient('idempotency_' . $idempotency_key);
        if ($cached) {
            return rest_ensure_response($cached);
        }
    }

    $order_data = $request->get_json_params();
    $order_id = wz_create_order($order_data);
    $response = ['order_id' => $order_id];

    if ($idempotency_key) {
        set_transient('idempotency_' . $idempotency_key, $response, 3600);
    }

    return rest_ensure_response($response);
}
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect missing idempotency support"
    assert len(good_violations) == 0, "Should pass with idempotency key"


def test_api_versioning():
    """LES-169: API endpoint without version namespace."""
    patterns = load_patterns(str(LESSONS_DIR), platform="wp")
    pattern = next((p for p in patterns if p.lesson_id == "LES-169"), None)
    assert pattern is not None, "LES-169 not found"

    bad_code = """
register_rest_route('wz', '/products', [
    'methods' => 'GET',
    'callback' => 'get_products',
]);
"""

    good_code = """
register_rest_route('wz/v1', '/products', [
    'methods' => 'GET',
    'callback' => 'get_products',
]);
"""

    bad_violations = check_pattern(pattern, bad_code, "test.php")
    good_violations = check_pattern(pattern, good_code, "test.php")

    assert len(bad_violations) > 0, "Should detect missing version namespace"
    assert len(good_violations) == 0, "Should pass with version namespace"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
