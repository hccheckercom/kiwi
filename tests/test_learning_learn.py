"""
Test learn_from_folder functionality.

Tests the 10 built-in detectors and lesson generation workflow.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add kiwi to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def test_hardcoded_credentials_detection():
    """Test detector #1: Hardcoded credentials"""
    print("=" * 60)
    print("TEST 1: Hardcoded credentials detection")
    print("=" * 60)

    from agent.learn import _extract_code_patterns

    tmp = tempfile.mkdtemp()
    try:
        php_file = os.path.join(tmp, "config.php")
        with open(php_file, 'w', encoding='utf-8') as f:
            f.write("""<?php
define('API_KEY', 'sk_live_abc123');
$password = "hardcoded_pass";
$secret = 'my_secret_key';
""")

        patterns = _extract_code_patterns(php_file)
        cred_patterns = [p for p in patterns if p[0] == 'hardcoded_credentials']

        print(f"Found {len(cred_patterns)} hardcoded credential patterns")
        assert len(cred_patterns) >= 2, f"Should detect at least 2 patterns, got {len(cred_patterns)}"
        print("✓ Hardcoded credentials detector working")

        return True
    finally:
        shutil.rmtree(tmp)


def test_sql_injection_detection():
    """Test detector #2: SQL injection"""
    print("\n" + "=" * 60)
    print("TEST 2: SQL injection detection")
    print("=" * 60)

    from agent.learn import _extract_code_patterns

    tmp = tempfile.mkdtemp()
    try:
        php_file = os.path.join(tmp, "query.php")
        with open(php_file, 'w', encoding='utf-8') as f:
            f.write("""<?php
$wpdb->query("SELECT * FROM table WHERE id = " . $_GET['id']);
$wpdb->get_results("DELETE FROM users WHERE name = " . $user);
""")

        patterns = _extract_code_patterns(php_file)
        sql_patterns = [p for p in patterns if p[0] == 'sql_injection']

        print(f"Found {len(sql_patterns)} SQL injection patterns")
        assert len(sql_patterns) >= 2, f"Should detect 2 patterns, got {len(sql_patterns)}"
        print("✓ SQL injection detector working")

        return True
    finally:
        shutil.rmtree(tmp)


def test_xss_risk_detection():
    """Test detector #3: XSS risk"""
    print("\n" + "=" * 60)
    print("TEST 3: XSS risk detection")
    print("=" * 60)

    from agent.learn import _extract_code_patterns

    tmp = tempfile.mkdtemp()
    try:
        php_file = os.path.join(tmp, "output.php")
        with open(php_file, 'w', encoding='utf-8') as f:
            f.write("""<?php
echo $user_input;
print $data;
echo esc_html($safe);  // This should NOT be detected
""")

        patterns = _extract_code_patterns(php_file)
        xss_patterns = [p for p in patterns if p[0] == 'xss_risk']

        print(f"Found {len(xss_patterns)} XSS risk patterns")
        assert len(xss_patterns) == 2, f"Should detect exactly 2 patterns (not the escaped one), got {len(xss_patterns)}"
        print("✓ XSS risk detector working")

        return True
    finally:
        shutil.rmtree(tmp)


def test_missing_nonce_detection():
    """Test detector #4: Missing nonce"""
    print("\n" + "=" * 60)
    print("TEST 4: Missing nonce detection")
    print("=" * 60)

    from agent.learn import _extract_code_patterns

    tmp = tempfile.mkdtemp()
    try:
        php_file = os.path.join(tmp, "form.php")
        with open(php_file, 'w', encoding='utf-8') as f:
            f.write("""<?php
if (isset($_POST['action'])) {
    process_form();
}
if (isset($_POST['data']) && wp_verify_nonce($_POST['_wpnonce'], 'action')) {
    // This should NOT be detected
}
""")

        patterns = _extract_code_patterns(php_file)
        nonce_patterns = [p for p in patterns if p[0] == 'missing_nonce']

        print(f"Found {len(nonce_patterns)} missing nonce patterns")
        assert len(nonce_patterns) == 1, f"Should detect 1 pattern (not the one with nonce), got {len(nonce_patterns)}"
        print("✓ Missing nonce detector working")

        return True
    finally:
        shutil.rmtree(tmp)


def test_file_inclusion_detection():
    """Test detector #5: File inclusion"""
    print("\n" + "=" * 60)
    print("TEST 5: File inclusion detection")
    print("=" * 60)

    from agent.learn import _extract_code_patterns

    tmp = tempfile.mkdtemp()
    try:
        php_file = os.path.join(tmp, "include.php")
        with open(php_file, 'w', encoding='utf-8') as f:
            f.write("""<?php
include($file);
require_once($path);
include('static.php');  // This should NOT be detected
""")

        patterns = _extract_code_patterns(php_file)
        inclusion_patterns = [p for p in patterns if p[0] == 'file_inclusion']

        print(f"Found {len(inclusion_patterns)} file inclusion patterns")
        assert len(inclusion_patterns) == 2, f"Should detect 2 patterns (not static include), got {len(inclusion_patterns)}"
        print("✓ File inclusion detector working")

        return True
    finally:
        shutil.rmtree(tmp)


def test_hardcoded_url_detection():
    """Test detector #6: Hardcoded URLs"""
    print("\n" + "=" * 60)
    print("TEST 6: Hardcoded URL detection")
    print("=" * 60)

    from agent.learn import _extract_code_patterns

    tmp = tempfile.mkdtemp()
    try:
        php_file = os.path.join(tmp, "urls.php")
        with open(php_file, 'w', encoding='utf-8') as f:
            f.write("""<?php
$url = 'https://example.com/api';
$proper = home_url('/page');  // This should NOT be detected
""")

        patterns = _extract_code_patterns(php_file)
        url_patterns = [p for p in patterns if p[0] == 'hardcoded_url']

        print(f"Found {len(url_patterns)} hardcoded URL patterns")
        assert len(url_patterns) >= 1, f"Should detect at least 1 pattern, got {len(url_patterns)}"
        print("✓ Hardcoded URL detector working")

        return True
    finally:
        shutil.rmtree(tmp)


def test_missing_error_handling_detection():
    """Test detector #7: Missing error handling"""
    print("\n" + "=" * 60)
    print("TEST 7: Missing error handling detection")
    print("=" * 60)

    from agent.learn import _extract_code_patterns

    tmp = tempfile.mkdtemp()
    try:
        php_file = os.path.join(tmp, "api.php")
        with open(php_file, 'w', encoding='utf-8') as f:
            f.write("""<?php
$data = file_get_contents('https://api.example.com');
process($data);
more_code();
still_no_check();

$response = wp_remote_get('https://api.example.com');
if (is_wp_error($response)) {
    // This should NOT be detected - has error check within 3 lines
}
""")

        patterns = _extract_code_patterns(php_file)
        error_patterns = [p for p in patterns if p[0] == 'missing_error_handling']

        print(f"Found {len(error_patterns)} missing error handling patterns")
        assert len(error_patterns) >= 1, f"Should detect at least 1 pattern (file_get_contents without check), got {len(error_patterns)}"
        print("✓ Missing error handling detector working")

        return True
    finally:
        shutil.rmtree(tmp)


def test_deprecated_function_detection():
    """Test detector #8: Deprecated functions"""
    print("\n" + "=" * 60)
    print("TEST 8: Deprecated function detection")
    print("=" * 60)

    from agent.learn import _extract_code_patterns

    tmp = tempfile.mkdtemp()
    try:
        php_file = os.path.join(tmp, "legacy.php")
        with open(php_file, 'w', encoding='utf-8') as f:
            f.write("""<?php
mysql_query("SELECT * FROM users");
ereg("pattern", $string);
create_function('$a', 'return $a;');
""")

        patterns = _extract_code_patterns(php_file)
        deprecated_patterns = [p for p in patterns if p[0] == 'deprecated_function']

        print(f"Found {len(deprecated_patterns)} deprecated function patterns")
        assert len(deprecated_patterns) == 3, f"Should detect 3 patterns, got {len(deprecated_patterns)}"
        print("✓ Deprecated function detector working")

        return True
    finally:
        shutil.rmtree(tmp)


def test_inefficient_loop_detection():
    """Test detector #9: Inefficient loops"""
    print("\n" + "=" * 60)
    print("TEST 9: Inefficient loop detection")
    print("=" * 60)

    from agent.learn import _extract_code_patterns

    tmp = tempfile.mkdtemp()
    try:
        php_file = os.path.join(tmp, "loop.php")
        with open(php_file, 'w', encoding='utf-8') as f:
            f.write("""<?php
for ($i = 0; $i < count($array); $i++) {
    echo $array[$i];
}
while ($i < count($items)) {
    process($items[$i++]);
}
$count = count($array);
for ($i = 0; $i < $count; $i++) {
    // This should NOT be detected (count cached)
}
""")

        patterns = _extract_code_patterns(php_file)
        loop_patterns = [p for p in patterns if p[0] == 'inefficient_loop']

        print(f"Found {len(loop_patterns)} inefficient loop patterns")
        assert len(loop_patterns) == 2, f"Should detect 2 patterns (not cached count), got {len(loop_patterns)}"
        print("✓ Inefficient loop detector working")

        return True
    finally:
        shutil.rmtree(tmp)


def test_missing_sanitization_detection():
    """Test detector #10: Missing sanitization"""
    print("\n" + "=" * 60)
    print("TEST 10: Missing sanitization detection")
    print("=" * 60)

    from agent.learn import _extract_code_patterns

    tmp = tempfile.mkdtemp()
    try:
        php_file = os.path.join(tmp, "input.php")
        with open(php_file, 'w', encoding='utf-8') as f:
            f.write("""<?php
$id = $_GET['id'];
$name = $_POST['name'];
$safe_id = absint($_GET['id']);  // This should NOT be detected
$safe_name = sanitize_text_field($_POST['name']);  // This should NOT be detected
""")

        patterns = _extract_code_patterns(php_file)
        sanitization_patterns = [p for p in patterns if p[0] == 'missing_sanitization']

        print(f"Found {len(sanitization_patterns)} missing sanitization patterns")
        assert len(sanitization_patterns) == 2, f"Should detect 2 patterns (not sanitized ones), got {len(sanitization_patterns)}"
        print("✓ Missing sanitization detector working")

        return True
    finally:
        shutil.rmtree(tmp)


def test_extract_patterns_all_10_types():
    """Test that all 10 detector types work together"""
    print("\n" + "=" * 60)
    print("TEST 11: All 10 detectors integration")
    print("=" * 60)

    from agent.learn import _extract_code_patterns

    tmp = tempfile.mkdtemp()
    try:
        php_file = os.path.join(tmp, "mixed.php")
        with open(php_file, 'w', encoding='utf-8') as f:
            f.write("""<?php
// Pattern 1: Hardcoded credentials
define('API_KEY', 'sk_live_abc123');
$password = "hardcoded_pass";

// Pattern 2: SQL injection
$wpdb->query("SELECT * FROM table WHERE id = " . $_GET['id']);

// Pattern 3: XSS risk
echo $user_input;

// Pattern 4: Missing nonce
if (isset($_POST['action'])) { process(); }

// Pattern 5: File inclusion
include($file);

// Pattern 6: Hardcoded URL
$url = 'https://example.com/api';

// Pattern 7: Missing error handling
$data = file_get_contents('https://api.example.com');

// Pattern 8: Deprecated function
mysql_query("SELECT * FROM users");

// Pattern 9: Inefficient loop
for ($i = 0; $i < count($array); $i++) { }

// Pattern 10: Missing sanitization
$id = $_GET['id'];
""")

        patterns = _extract_code_patterns(php_file)
        pattern_types = set(p[0] for p in patterns)

        print(f"Detected {len(pattern_types)} unique pattern types:")
        for pt in sorted(pattern_types):
            count = len([p for p in patterns if p[0] == pt])
            print(f"  - {pt}: {count} occurrences")

        assert len(pattern_types) == 10, f"Should detect all 10 pattern types, got {len(pattern_types)}: {sorted(pattern_types)}"
        print("✓ All 10 detectors working together")

        return True
    finally:
        shutil.rmtree(tmp)


def test_learn_from_folder_integration():
    """Test end-to-end learn_from_folder workflow"""
    print("\n" + "=" * 60)
    print("TEST 12: learn_from_folder integration")
    print("=" * 60)

    from agent.learn import learn_from_folder

    tmp = tempfile.mkdtemp()
    try:
        # Create test folder structure
        os.makedirs(os.path.join(tmp, "src"))

        # File 1: Multiple security issues
        with open(os.path.join(tmp, "src", "auth.php"), 'w', encoding='utf-8') as f:
            f.write("""<?php
define('SECRET_KEY', 'hardcoded_secret');
$wpdb->query("SELECT * FROM users WHERE id = " . $_GET['id']);
echo $user_input;
""")

        # File 2: More issues
        with open(os.path.join(tmp, "src", "api.php"), 'w', encoding='utf-8') as f:
            f.write("""<?php
$data = file_get_contents('https://api.example.com');
mysql_query("SELECT * FROM table");
""")

        # Run learn_from_folder
        result = learn_from_folder(tmp, min_occurrences=1, auto_approve=False)

        print(f"Scanned {result['scanned_files']} files")
        print(f"Found {result['patterns_found']} pattern types")
        print(f"Generated {len(result['suggestions'])} suggestions")

        assert result['scanned_files'] == 2, f"Should scan 2 files, got {result['scanned_files']}"
        assert result['patterns_found'] >= 5, f"Should find at least 5 pattern types, got {result['patterns_found']}"
        assert len(result['suggestions']) >= 5, f"Should generate at least 5 suggestions, got {len(result['suggestions'])}"

        # Verify suggestion structure
        for sug in result['suggestions']:
            assert 'pattern_type' in sug, "Suggestion missing pattern_type"
            assert 'severity' in sug, "Suggestion missing severity"
            assert 'occurrences' in sug, "Suggestion missing occurrences"
            assert 'files' in sug, "Suggestion missing files"

        print("✓ learn_from_folder integration working")

        return True
    finally:
        shutil.rmtree(tmp)


def test_js_hardcoded_api_key_detection():
    """Test JS detector #11: Hardcoded API keys"""
    print("\n" + "=" * 60)
    print("TEST 13: JS hardcoded API key detection")
    print("=" * 60)

    from agent.learn import _extract_js_patterns

    tmp = tempfile.mkdtemp()
    try:
        js_file = os.path.join(tmp, "config.js")
        with open(js_file, 'w', encoding='utf-8') as f:
            f.write("""
const apiKey = "sk_live_abc123def456ghi789";
const API_KEY = 'pk_test_xyz123abc456def789';
const token = "short"; // Too short, should NOT be detected
""")

        patterns = _extract_js_patterns(js_file)
        api_key_patterns = [p for p in patterns if p[0] == 'js_hardcoded_api_key']

        print(f"Found {len(api_key_patterns)} hardcoded API key patterns")
        assert len(api_key_patterns) == 2, f"Should detect 2 patterns (not short token), got {len(api_key_patterns)}"
        print("✓ JS hardcoded API key detector working")

        return True
    finally:
        shutil.rmtree(tmp)


def test_js_eval_usage_detection():
    """Test JS detector #12: eval() usage"""
    print("\n" + "=" * 60)
    print("TEST 14: JS eval() usage detection")
    print("=" * 60)

    from agent.learn import _extract_js_patterns

    tmp = tempfile.mkdtemp()
    try:
        js_file = os.path.join(tmp, "unsafe.js")
        with open(js_file, 'w', encoding='utf-8') as f:
            f.write("""
eval(userInput);
const result = eval("2 + 2");
// evaluate() should NOT be detected
""")

        patterns = _extract_js_patterns(js_file)
        eval_patterns = [p for p in patterns if p[0] == 'js_eval_usage']

        print(f"Found {len(eval_patterns)} eval() usage patterns")
        assert len(eval_patterns) == 2, f"Should detect 2 eval() calls, got {len(eval_patterns)}"
        print("✓ JS eval() detector working")

        return True
    finally:
        shutil.rmtree(tmp)


def test_js_innerhtml_xss_detection():
    """Test JS detector #13: innerHTML XSS"""
    print("\n" + "=" * 60)
    print("TEST 15: JS innerHTML XSS detection")
    print("=" * 60)

    from agent.learn import _extract_js_patterns

    tmp = tempfile.mkdtemp()
    try:
        js_file = os.path.join(tmp, "dom.js")
        with open(js_file, 'w', encoding='utf-8') as f:
            f.write("""
element.innerHTML = userInput;
div.innerHTML = "<p>" + data + "</p>";
safe.innerHTML = DOMPurify.sanitize(input); // Should NOT be detected
""")

        patterns = _extract_js_patterns(js_file)
        innerHTML_patterns = [p for p in patterns if p[0] == 'js_innerhtml_xss']

        print(f"Found {len(innerHTML_patterns)} innerHTML XSS patterns")
        assert len(innerHTML_patterns) == 2, f"Should detect 2 patterns (not DOMPurify), got {len(innerHTML_patterns)}"
        print("✓ JS innerHTML XSS detector working")

        return True
    finally:
        shutil.rmtree(tmp)


def test_js_missing_error_handling_detection():
    """Test JS detector #14: Missing error handling"""
    print("\n" + "=" * 60)
    print("TEST 16: JS missing error handling detection")
    print("=" * 60)

    from agent.learn import _extract_js_patterns

    tmp = tempfile.mkdtemp()
    try:
        js_file = os.path.join(tmp, "api.js")
        with open(js_file, 'w', encoding='utf-8') as f:
            f.write("""
fetch('/api/data').then(r => r.json());
axios.get('/api/users').then(r => console.log(r));

fetch('/api/safe')
  .then(r => r.json())
  .catch(err => console.error(err)); // Should NOT be detected
""")

        patterns = _extract_js_patterns(js_file)
        error_patterns = [p for p in patterns if p[0] == 'js_missing_error_handling']

        print(f"Found {len(error_patterns)} missing error handling patterns")
        assert len(error_patterns) == 2, f"Should detect 2 patterns (not the one with .catch), got {len(error_patterns)}"
        print("✓ JS missing error handling detector working")

        return True
    finally:
        shutil.rmtree(tmp)


def test_js_console_log_detection():
    """Test JS detector #15: console.log in production"""
    print("\n" + "=" * 60)
    print("TEST 17: JS console.log detection")
    print("=" * 60)

    from agent.learn import _extract_js_patterns

    tmp = tempfile.mkdtemp()
    try:
        js_file = os.path.join(tmp, "debug.js")
        with open(js_file, 'w', encoding='utf-8') as f:
            f.write("""
console.log("Debug:", data);
console.debug("Value:", x);
console.info("Info message");
console.error("Error"); // Should NOT be detected (error is ok)
console.warn("Warning"); // Should NOT be detected (warn is ok)
""")

        patterns = _extract_js_patterns(js_file)
        console_patterns = [p for p in patterns if p[0] == 'js_console_log']

        print(f"Found {len(console_patterns)} console.log patterns")
        assert len(console_patterns) == 3, f"Should detect 3 patterns (log/debug/info, not error/warn), got {len(console_patterns)}"
        print("✓ JS console.log detector working")

        return True
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    print("\nLearn from Folder Tests\n")

    tests = [
        test_hardcoded_credentials_detection,
        test_sql_injection_detection,
        test_xss_risk_detection,
        test_missing_nonce_detection,
        test_file_inclusion_detection,
        test_hardcoded_url_detection,
        test_missing_error_handling_detection,
        test_deprecated_function_detection,
        test_inefficient_loop_detection,
        test_missing_sanitization_detection,
        test_extract_patterns_all_10_types,
        test_learn_from_folder_integration,
        test_js_hardcoded_api_key_detection,
        test_js_eval_usage_detection,
        test_js_innerhtml_xss_detection,
        test_js_missing_error_handling_detection,
        test_js_console_log_detection,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"\nX TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
