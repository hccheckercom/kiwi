"""Batch-fill Bad/Good/Why for pattern-only lessons based on their metadata."""
import re
from pathlib import Path

LESSONS_DIR = Path(__file__).parent.parent / "lessons"

# Templates keyed by (category, pattern-keyword or id)
DOCS = {
    "LES-043": {
        "bad": "fetch('/api/data').then(r => r.json()).then(handle);\n// No .catch() — network error silently breaks UI",
        "good": "fetch('/api/data')\n  .then(r => r.json())\n  .then(handle)\n  .catch(err => {\n    console.error('Request failed:', err);\n    showErrorToast('Không thể tải dữ liệu');\n  });",
        "why": "fetch() without .catch() — network failure, timeout, or server error silently breaks UI. User sees nothing happen.",
    },
    "LES-044": {
        "bad": '<img src="product.jpg" loading="lazy" class="w-full">',
        "good": '<img src="product.jpg" loading="lazy" width="400" height="400" class="w-full h-auto">',
        "why": "Lazy-loaded images without explicit width/height cause CLS (Cumulative Layout Shift). Browser can't reserve space until image loads.",
    },
    "LES-045": {
        "bad": "$name = $_GET['name'];\n$wpdb->query(\"SELECT * FROM users WHERE name = '$name'\");",
        "good": "$name = sanitize_text_field( wp_unslash( $_GET['name'] ?? '' ) );",
        "why": "Raw superglobal access without sanitization — SQL injection, XSS, and other injection risks.",
    },
    "LES-046": {
        "bad": "$template = $_GET['page'];\ninclude $template . '.php';",
        "good": "$allowed = ['home', 'about', 'contact'];\n$page = sanitize_file_name( $_GET['page'] ?? 'home' );\nif ( in_array( $page, $allowed, true ) ) {\n    include get_template_directory() . '/pages/' . $page . '.php';\n}",
        "why": "include/require with variable path — Local File Inclusion (LFI) allows attacker to read arbitrary files.",
    },
    "LES-047": {
        "bad": "document.getElementById('wz-cart-count').textContent = count;",
        "good": "const el = document.getElementById('wz-cart-count');\nif (el) { el.textContent = count; }",
        "why": "getElementById returns null if element doesn't exist (conditional rendering, different pages). Accessing .property on null throws TypeError.",
    },
    "LES-048": {
        "bad": '<input type="email" name="email" class="w-full px-4 py-2">',
        "good": '<label for="wz-email">Email</label>\n<input type="email" id="wz-email" name="email" aria-required="true" class="w-full px-4 py-2">',
        "why": "Form input without associated label — WCAG 2.1 Level A violation. Screen readers can't identify the field.",
    },
    "LES-049": {
        "bad": "foreach ( $ids as $id ) {\n    $product = wz_get_product( $id ); // 1 query per iteration\n}",
        "good": "$products = wz_get_products_by_ids( $ids ); // 1 query total",
        "why": "N+1 DB queries — wz_get_product() in loop fires 1 query per item. 50 products = 50 queries. Use batch function.",
    },
    "LES-050": {
        "bad": "$query = new WP_Query( $args );\nforeach ( $query->posts as $post ) {\n    // use $post\n}\n// Missing wp_reset_postdata()",
        "good": "$query = new WP_Query( $args );\nif ( $query->have_posts() ) {\n    while ( $query->have_posts() ) {\n        $query->the_post();\n        // use the_title(), the_content(), etc.\n    }\n    wp_reset_postdata();\n}",
        "why": "WP_Query without wp_reset_postdata() corrupts the global $post — subsequent template tags return wrong data.",
    },
    "LES-051": {
        "bad": "const msg = 'Thêm vào giỏ hàng thành công';\nalert(msg);",
        "good": "const msg = wzTheme.i18n.addedToCart || 'Added to cart';\nshowToast(msg);",
        "why": "Hardcoded Vietnamese in JS — can't rebrand when cloning theme for English/other language clients.",
    },
    "LES-052": {
        "bad": "document.body.classList.add('overflow-hidden');\n// Modal opens... but never removes the class on close",
        "good": "document.body.classList.add('overflow-hidden');\nmodal.addEventListener('close', () => {\n  document.body.classList.remove('overflow-hidden');\n});",
        "why": "Adding overflow-hidden without cleanup — user can never scroll again after closing modal. Permanent scroll lock.",
    },
    "LES-034": {
        "bad": "// File starts with EF BB BF bytes (invisible BOM)\n<?php declare(strict_types=1);",
        "good": "// File starts clean — no BOM\n<?php declare(strict_types=1);",
        "why": "UTF-8 BOM before <?php causes output before headers. With strict_types, PHP throws fatal error.",
    },
    "LES-070": {
        "bad": "register_rest_route( 'wezone/v1', '/search', [\n    'args' => [\n        'q' => [ 'type' => 'string' ],  // no sanitize_callback\n    ],\n]);",
        "good": "register_rest_route( 'wezone/v1', '/search', [\n    'args' => [\n        'q' => [\n            'type' => 'string',\n            'sanitize_callback' => 'sanitize_text_field',\n            'validate_callback' => function( $v ) { return ! empty( $v ); },\n        ],\n    ],\n]);",
        "why": "REST route args without sanitize_callback — raw user input reaches handler. Always sanitize at boundary.",
    },
    "LES-071": {
        "bad": "register_rest_route( 'wezone/v1', '/orders', [\n    'methods' => 'POST',\n    'permission_callback' => '__return_true',\n]);",
        "good": "register_rest_route( 'wezone/v1', '/orders', [\n    'methods' => 'POST',\n    'permission_callback' => function() {\n        return current_user_can( 'edit_posts' );\n    },\n]);",
        "why": "Write endpoint with __return_true permission — anyone can create/modify data without authentication.",
    },
    "LES-072": {
        "bad": "register_rest_route( 'wezone/v1', '/login', [\n    'methods' => 'POST',\n    'permission_callback' => '__return_true',\n    'callback' => 'handle_login',\n]);",
        "good": "register_rest_route( 'wezone/v1', '/login', [\n    'methods' => 'POST',\n    'permission_callback' => '__return_true',\n    'callback' => 'handle_login',\n]);\n// In handle_login():\nApiRateLimit::check( 'login', 5, 60 ); // 5 attempts per 60s",
        "why": "Public endpoint without rate limiting — brute-force login, DDoS, or resource exhaustion attacks.",
    },
    "LES-073": {
        "bad": "$id = $request->get_param('id');\n$wpdb->get_row(\"SELECT * FROM table WHERE id = $id\");",
        "good": "$id = (int) $request->get_param('id');\n$wpdb->get_row( $wpdb->prepare('SELECT * FROM table WHERE id = %d', $id) );",
        "why": "get_param() returns raw string. Without type cast, string '1 OR 1=1' passes through — type confusion risk.",
    },
    "LES-074": {
        "bad": "return new WP_REST_Response([\n    'user' => $user,  // contains password hash, email, tokens\n]);",
        "good": "return new WP_REST_Response([\n    'user' => [\n        'id' => $user->ID,\n        'name' => $user->display_name,\n    ],\n]);",
        "why": "REST response leaking sensitive data — password hashes, tokens, secrets exposed to frontend.",
    },
    "LES-075": {
        "bad": "register_rest_route( 'wezone/v1', '/cart/add', [\n    'methods' => WP_REST_Server::CREATABLE,\n    'callback' => 'add_to_cart',\n    // No nonce verification\n]);",
        "good": "// In callback:\nif ( ! wp_verify_nonce( $request->get_header('X-WP-Nonce'), 'wp_rest' ) ) {\n    return new WP_Error( 'rest_forbidden', 'Invalid nonce', ['status' => 403] );\n}",
        "why": "Write REST route without nonce — CSRF attack can trigger actions on behalf of logged-in user.",
    },
    "LES-076": {
        "bad": "$wpdb->query(\"DELETE FROM {$wpdb->prefix}orders WHERE id = $id\");",
        "good": "$wpdb->query( $wpdb->prepare(\n    \"DELETE FROM {$wpdb->prefix}orders WHERE id = %d\", $id\n) );",
        "why": "SQL query without prepare() — SQL injection. Always use $wpdb->prepare() with placeholders.",
    },
    "LES-077": {
        "bad": "$wpdb->prepare(\"SELECT * FROM table WHERE name = '$name'\");",
        "good": "$wpdb->prepare('SELECT * FROM table WHERE name = %s', $name);",
        "why": "Variable interpolated inside prepare() format string — defeats the purpose of prepared statements.",
    },
    "LES-078": {
        "bad": "$wpdb->query('DROP TABLE wp_orders');  // in a helper function",
        "good": "// Destructive operations ONLY in migration files\n// migrations/001_drop_legacy_orders.php\n$wpdb->query('DROP TABLE IF EXISTS wp_orders');",
        "why": "DROP/TRUNCATE outside migration file — accidental data loss. Destructive DB ops must be in versioned migrations.",
    },
    "LES-079": {
        "bad": "$wpdb->insert('orders', $data);  // missing prefix",
        "good": "$wpdb->insert(\"{$wpdb->prefix}orders\", $data);",
        "why": "DB operation without $wpdb->prefix — breaks on multisite where tables have different prefixes.",
    },
    "LES-080": {
        "bad": "foreach ( $rows as $row ) {\n    $wpdb->insert(\"{$wpdb->prefix}analytics\", $row);\n}",
        "good": "wz_bulk_insert(\"{$wpdb->prefix}analytics\", $rows, ['%d','%s','%f']);",
        "why": "N+1 DB writes in loop. 100 rows = 100 INSERT queries. Use wz_bulk_insert() for batch operations.",
    },
    "LES-081": {
        "bad": "function handle_payment_ipn() {\n    $data = json_decode(file_get_contents('php://input'), true);\n    update_order_status($data['order_id'], 'paid');\n}",
        "good": "function handle_payment_ipn() {\n    $data = json_decode(file_get_contents('php://input'), true);\n    $signature = $_SERVER['HTTP_X_SIGNATURE'] ?? '';\n    if ( ! verify_hmac($data, $signature, $secret_key) ) {\n        wp_send_json_error('Invalid signature', 403);\n    }\n    update_order_status($data['order_id'], 'paid');\n}",
        "why": "IPN/webhook handler without signature verification — attacker can forge payment confirmations.",
    },
    "LES-082": {
        "bad": "$key = get_option('vnpay_secret_key');\n$hash = hash_hmac('sha256', $data, $key);",
        "good": "$key = get_option('vnpay_secret_key');\nif ( empty($key) ) {\n    wz_log('Payment key not configured', 'error');\n    return new WP_Error('config', 'Payment not configured');\n}\n$hash = hash_hmac('sha256', $data, $key);",
        "why": "HMAC with empty key — hash_hmac('sha256', data, '') produces a valid hash that attacker can reproduce.",
    },
    "LES-083": {
        "bad": "if ( $response_amount == $order_total ) { // float comparison\n    mark_paid();\n}",
        "good": "if ( abs($response_amount - $order_total) < 0.01 ) {\n    mark_paid();\n}",
        "why": "Float comparison with == — 99999.99 vs 99999.990000001 fails. Use epsilon comparison for money.",
    },
    "LES-084": {
        "bad": "update_order_status($order_id, 'cancelled');",
        "good": "wz_log(\"Order #{$order_id} status: processing → cancelled by user #{$user_id}\");\nupdate_order_status($order_id, 'cancelled');",
        "why": "Order status change without audit log — no trail when customer disputes. Always log who/when/why.",
    },
    "LES-085": {
        "bad": "$return_url = $_GET['redirect_to'];\nwp_redirect($return_url);",
        "good": "$return_url = wp_validate_redirect(\n    esc_url_raw($_GET['redirect_to'] ?? ''),\n    home_url('/')\n);\nwp_safe_redirect($return_url);",
        "why": "Payment redirect URL not validated — open redirect to phishing site after checkout.",
    },
    "LES-086": {
        "bad": "namespace WeZone\\Shipping;\nfunction boot() {\n    add_action('init', 'register_routes');\n    flush_rewrite_rules();\n}",
        "good": "namespace WeZone\\Shipping;\nfunction boot() {\n    \\add_action('init', [self::class, 'register_routes']);\n    \\flush_rewrite_rules();\n}",
        "why": "WordPress functions called without \\ prefix in namespace — PHP looks for WeZone\\Shipping\\add_action() which doesn't exist. Fatal error.",
    },
    "LES-087": {
        "bad": "namespace WeZone\\Core;\nclass OrderEngine {\n    public function create(array $data) {",
        "good": "declare(strict_types=1);\nnamespace WeZone\\Core;\nclass OrderEngine {\n    public function create(array $data): int {",
        "why": "Namespaced file without declare(strict_types=1) — silent type coercion bugs. String '0' treated as falsy int.",
    },
    "LES-088": {
        "bad": "use WeZone\\Core\\Services\\OldPaymentGateway; // class was removed",
        "good": "use WeZone\\Core\\Services\\PaymentGateway; // verify class exists",
        "why": "use statement imports non-existent class — fatal 'Class not found' when autoloader tries to load it.",
    },
    "LES-089": {
        "bad": "public function getTotal($items) {\n    // returns mixed — could be int, float, or null",
        "good": "public function getTotal(array $items): float {\n    return (float) array_sum(array_column($items, 'subtotal'));",
        "why": "Public method without return type — strict_types can't enforce return value. Callers get unexpected types.",
    },
    "LES-090": {
        "bad": "add_action('init', [$this, 'onInit']);\n// But class has no onInit() method",
        "good": "add_action('init', [$this, 'register_routes']);\n// Method exists in this class\npublic function register_routes(): void { ... }",
        "why": "Hook callback references non-existent method — WordPress silently fails. Feature never activates, no error.",
    },
    "LES-091": {
        "bad": "public function boot(): void {\n    $this->register_hooks();\n}",
        "good": "public function boot(): void {\n    if ( function_exists('wz_config') ) {\n        wz_config('plugin-name');\n    }\n    $this->register_hooks();\n}",
        "why": "Plugin boot() without wz_config() — config never loads, all settings return null. Silent misconfiguration.",
    },
    "LES-092": {
        "bad": "add_action('init', [$this, 'boot'], 0); // priority 0 = reserved for core",
        "good": "add_action('init', [$this, 'boot'], 10); // default priority",
        "why": "Priority 0 on init hook — races with wezone-core which also uses priority 0. Undefined execution order.",
    },
    "LES-093": {
        "bad": "class Cache {\n    private static array $store = [];\n    public static function set($k, $v) { self::$store[$k] = $v; }\n}",
        "good": "class Cache {\n    private array $store = [];\n    public function set(string $k, $v): void { $this->store[$k] = $v; }\n}",
        "why": "Mutable static property — state leaks between PHPUnit tests. Test A's cache pollutes Test B.",
    },
    "LES-094": {
        "bad": "try {\n    $order = $engine->create($data);\n} catch (Exception $e) {\n    // empty\n}",
        "good": "try {\n    $order = $engine->create($data);\n} catch (Exception $e) {\n    wz_log('Order creation failed: ' . $e->getMessage(), 'error');\n    throw $e;\n}",
        "why": "Empty catch block swallows exception — bug is hidden, no error logged, impossible to debug in production.",
    },
    "LES-095": {
        "bad": "function handle_ajax_request() {\n    if (!$valid) {\n        wp_die('Invalid request');\n    }\n}",
        "good": "function handle_ajax_request() {\n    if (!$valid) {\n        wp_send_json_error(['message' => 'Invalid request'], 400);\n    }\n}",
        "why": "wp_die() in REST/AJAX handler returns HTML — frontend JS expects JSON, gets parse error.",
    },
    "LES-096": {
        "bad": "error_log('Order created: ' . $order_id);",
        "good": "wz_log('Order created', 'info', ['order_id' => $order_id]);",
        "why": "error_log() not structured — can't filter, search, or aggregate. Use wz_log() for structured logging.",
    },
    "LES-097": {
        "bad": "throw new Exception();",
        "good": "throw new RuntimeException('OrderEngine::create() failed: billing.email is required');",
        "why": "Exception without message — stack trace shows 'Exception' with no context. Useless for debugging.",
    },
    "LES-098": {
        "bad": "$response = wp_remote_get('https://api.shipping.vn/rates');",
        "good": "$response = wp_remote_get('https://api.shipping.vn/rates', [\n    'timeout' => 10,\n]);",
        "why": "wp_remote_get without timeout — default is 5s but can block PHP worker if API is slow. Set explicit timeout.",
    },
    "LES-099": {
        "bad": "$response = wp_remote_get($url);\n$body = wp_remote_retrieve_body($response);",
        "good": "$response = wp_remote_get($url, ['timeout' => 10]);\nif ( is_wp_error($response) ) {\n    wz_log('API request failed: ' . $response->get_error_message(), 'error');\n    return [];\n}\n$body = wp_remote_retrieve_body($response);",
        "why": "wp_remote_* response not checked for WP_Error — timeout/DNS failure causes fatal when accessing body.",
    },
    "LES-100": {
        "bad": "$url = 'https://api.ghn.vn/shiip/public-api/v2/shipping-order/fee';",
        "good": "$url = wz_config('shipping.api_url', 'https://api.ghn.vn/shiip/public-api/v2');\n$url .= '/shipping-order/fee';",
        "why": "Shipping API URL hardcoded — can't switch between sandbox and production environments.",
    },
    "LES-101": {
        "bad": "function calculate_shipping($items) {\n    $total_weight = array_sum(array_column($items, 'weight'));\n    return $this->get_rate($total_weight);\n}",
        "good": "function calculate_shipping(array $items): float {\n    $total_weight = array_sum(array_column($items, 'weight'));\n    if ($total_weight <= 0) {\n        wz_log('Invalid weight for shipping calculation', 'warning');\n        return (float) wz_config('shipping.fees.default', 30000);\n    }\n    return $this->get_rate($total_weight);\n}",
        "why": "Shipping rate calculation without weight/dimensions validation — carrier API returns error or fee=0.",
    },
    "LES-102": {
        "bad": "echo json_encode($data);",
        "good": "echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);",
        "why": "json_encode() without JSON_UNESCAPED_UNICODE — Vietnamese text becomes \\uXXXX sequences. Unreadable in logs.",
    },
    "LES-103": {
        "bad": "file_put_contents($path, $content);",
        "good": "global $wp_filesystem;\nif ( ! $wp_filesystem ) {\n    require_once ABSPATH . 'wp-admin/includes/file.php';\n    WP_Filesystem();\n}\n$wp_filesystem->put_contents($path, $content);",
        "why": "file_get/put_contents bypasses WP_Filesystem — permission issues on hosts with restricted file access.",
    },
    "LES-104": {
        "bad": "$path = ABSPATH . 'wp-content/plugins/wezone-core/templates/';",
        "good": "$path = WP_PLUGIN_DIR . '/wezone-core/templates/';",
        "why": "Hardcoded wp-content/plugins/ path — breaks when WP_CONTENT_DIR is customized.",
    },
    "LES-105": {
        "bad": "define('WZ_API_KEY', get_option('wz_api_key'));",
        "good": "// Don't define constants from DB at file load time\n// Instead, use a getter:\nfunction wz_api_key(): string {\n    static $key = null;\n    if ($key === null) { $key = get_option('wz_api_key', ''); }\n    return $key;\n}",
        "why": "define() with get_option() at file load time — if DB isn't ready yet, constant = false forever.",
    },
}


def fill_lesson(filepath: Path, doc: dict) -> bool:
    content = filepath.read_text(encoding="utf-8")
    if "TODO" not in content and "## Summary" not in content:
        return False

    end_idx = content.find("\n---", 3)
    if end_idx == -1:
        return False

    header = content[: end_idx + 5]  # include \n---\n

    new_body = f"""
## Bad
```php
{doc['bad']}
```

## Good
```php
{doc['good']}
```

## Why
{doc['why']}
"""

    filepath.write_text(header + new_body, encoding="utf-8")
    return True


def main():
    filled = 0
    for lesson_id, doc in DOCS.items():
        # Find the file
        for md in LESSONS_DIR.rglob(f"{lesson_id}.md"):
            if fill_lesson(md, doc):
                filled += 1
                break

    print(f"Filled: {filled}/{len(DOCS)} lessons")


if __name__ == "__main__":
    main()
