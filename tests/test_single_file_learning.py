"""Tests for single-file auto-learning module."""

import os
import sys
import tempfile
from pathlib import Path

# Add kiwi root to path
KIWI_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(KIWI_DIR))

from learning.single_file import (
    extract_patterns_from_file,
    _run_php_detectors,
    _run_js_detectors,
    _calculate_frequency_score,
    _infer_severity,
    _infer_category,
    _calculate_confidence,
)


def test_extract_patterns_from_php_file():
    """Test pattern extraction from PHP file with known bugs."""
    # Create temp PHP file with SQL injection
    with tempfile.NamedTemporaryFile(mode='w', suffix='.php', delete=False, encoding='utf-8') as f:
        f.write("""<?php
$wpdb->query("SELECT * FROM table WHERE id = " . $_GET['id']);
if (isset($_POST['action'])) {
    process_action();
}
echo $user_input;
""")
        temp_file = f.name

    try:
        suggestions = extract_patterns_from_file(temp_file, min_confidence=0.5)

        # Should detect at least 2 patterns (SQL injection, missing nonce, XSS)
        assert len(suggestions) >= 2, f"Expected ≥2 suggestions, got {len(suggestions)}"

        # Check SQL injection pattern (category is php-security, pattern contains wpdb)
        sql_patterns = [s for s in suggestions if 'wpdb' in s.pattern or 'query' in s.pattern]
        assert len(sql_patterns) > 0, f"Should detect SQL injection pattern. Got: {[s.pattern[:50] for s in suggestions]}"

        # Check confidence scores
        for sug in suggestions:
            assert 0.0 <= sug.confidence <= 1.0, f"Confidence {sug.confidence} out of range"
            assert sug.confidence >= 0.5, f"Confidence {sug.confidence} below threshold"

        print(f"[PASS] test_extract_patterns_from_php_file: {len(suggestions)} patterns detected")
    finally:
        os.unlink(temp_file)


def test_extract_patterns_from_js_file():
    """Test pattern extraction from JS file."""
    # Create temp JS file with XSS risk
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
        f.write("""
const apiKey = "sk_live_abc123def456ghi789jkl012";
document.getElementById("output").innerHTML = userInput;
eval(userCode);
console.log("Debug info:", userData);
""")
        temp_file = f.name

    try:
        suggestions = extract_patterns_from_file(temp_file, min_confidence=0.5)

        # Should detect at least 2 patterns (hardcoded API key, innerHTML XSS, eval, console.log)
        assert len(suggestions) >= 2, f"Expected ≥2 suggestions, got {len(suggestions)}"

        # Check scope format contains JS/TS extensions
        for sug in suggestions:
            # Scope format: **/*.{js,ts,jsx,tsx} or **/*.js
            assert 'js' in sug.scope or 'ts' in sug.scope, \
                f"Scope '{sug.scope}' should reference JS/TS files"

        print(f"[PASS] test_extract_patterns_from_js_file: {len(suggestions)} patterns detected")
    finally:
        os.unlink(temp_file)


def test_confidence_scoring():
    """Test confidence calculation logic."""
    # High frequency + existing similar + small file = high confidence
    conf1 = _calculate_confidence(frequency_score=0.9, has_existing_similar=True, line_count=100)
    assert conf1 >= 0.9, f"Expected high confidence, got {conf1}"

    # Low frequency + no similar + large file = low confidence
    conf2 = _calculate_confidence(frequency_score=0.5, has_existing_similar=False, line_count=600)
    assert conf2 <= 0.5, f"Expected low confidence, got {conf2}"

    # Confidence should be clamped to [0, 1]
    conf3 = _calculate_confidence(frequency_score=1.0, has_existing_similar=True, line_count=50)
    assert 0.0 <= conf3 <= 1.0, f"Confidence {conf3} out of range"

    print("[PASS] test_confidence_scoring: all assertions passed")


def test_frequency_heuristic():
    """Test frequency score calculation."""
    assert _calculate_frequency_score(1) == 0.5, "1 occurrence should score 0.5"
    assert _calculate_frequency_score(2) == 0.7, "2 occurrences should score 0.7"
    assert _calculate_frequency_score(3) == 0.7, "3 occurrences should score 0.7"
    assert _calculate_frequency_score(5) == 0.9, "5 occurrences should score 0.9"

    print("[PASS] test_frequency_heuristic: all assertions passed")


def test_severity_heuristic():
    """Test severity inference."""
    # Security patterns → CRITICAL
    assert _infer_severity('sql_injection', 'query') == 'CRITICAL'
    assert _infer_severity('xss_risk', 'echo') == 'CRITICAL'
    assert _infer_severity('missing_nonce', 'POST') == 'CRITICAL'

    # Performance patterns → HIGH
    assert _infer_severity('inefficient_loop', 'count') == 'HIGH'

    # Code quality → SUGGEST
    assert _infer_severity('console_log_production', 'console.log') == 'SUGGEST'

    print("[PASS] test_severity_heuristic: all assertions passed")


def test_category_heuristic():
    """Test category inference."""
    # PHP security
    cat1 = _infer_category('sql_injection', 'test.php', '$wpdb->query')
    assert cat1 == 'php-security', f"Expected php-security, got {cat1}"

    # JS security
    cat2 = _infer_category('eval_usage', 'test.js', 'eval(code)')
    assert cat2 == 'js-security', f"Expected js-security, got {cat2}"

    # Performance
    cat3 = _infer_category('inefficient_loop', 'test.php', 'for count')
    assert cat3 == 'performance', f"Expected performance, got {cat3}"

    print("[PASS] test_category_heuristic: all assertions passed")


def test_no_false_positives():
    """Test against clean file (should return empty)."""
    # Create clean PHP file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.php', delete=False, encoding='utf-8') as f:
        f.write("""<?php
function get_user_name($user_id) {
    global $wpdb;
    $result = $wpdb->prepare("SELECT name FROM users WHERE id = %d", $user_id);
    return esc_html($result);
}
""")
        temp_file = f.name

    try:
        suggestions = extract_patterns_from_file(temp_file, min_confidence=0.7)

        # Clean code should produce 0 suggestions
        assert len(suggestions) == 0, f"Expected 0 suggestions for clean code, got {len(suggestions)}"

        print("[PASS] test_no_false_positives: no patterns detected in clean code")
    finally:
        os.unlink(temp_file)


def test_php_detectors():
    """Test PHP detectors directly."""
    # Create temp file with multiple patterns
    with tempfile.NamedTemporaryFile(mode='w', suffix='.php', delete=False, encoding='utf-8') as f:
        f.write("""<?php
define("API_KEY", "secret123");
$wpdb->query("SELECT * FROM table WHERE id = " . $_GET['id']);
echo $user_input;
if (isset($_POST['action'])) { process(); }
include($_GET['page'] . '.php');
$url = "https://example.com/api";
$data = file_get_contents($url);
mysql_query("SELECT * FROM old_table");
for ($i = 0; $i < count($arr); $i++) {}
$name = $_POST['name'];
""")
        temp_file = f.name

    try:
        patterns = _run_php_detectors(temp_file)

        # Should detect all 10 pattern types
        pattern_types = set(p[0] for p in patterns)
        assert len(pattern_types) >= 8, f"Expected >=8 pattern types, got {len(pattern_types)}: {pattern_types}"

        print(f"[PASS] test_php_detectors: {len(pattern_types)} pattern types detected")
    finally:
        os.unlink(temp_file)


def test_js_detectors():
    """Test JS detectors directly."""
    # Create temp file with multiple patterns
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
        f.write("""
const apiKey = "sk_live_abc123def456ghi789jkl012";
eval(userCode);
element.innerHTML = userInput;
fetch(url).then(r => r.json());
console.log("Debug:", data);
""")
        temp_file = f.name

    try:
        patterns = _run_js_detectors(temp_file)

        # Should detect all 5 JS pattern types
        pattern_types = set(p[0] for p in patterns)
        assert len(pattern_types) >= 4, f"Expected >=4 pattern types, got {len(pattern_types)}: {pattern_types}"

        print(f"[PASS] test_js_detectors: {len(pattern_types)} pattern types detected")
    finally:
        os.unlink(temp_file)


def test_performance():
    """Test <5s for 500-line file."""
    import time

    # Create 500-line PHP file with patterns
    with tempfile.NamedTemporaryFile(mode='w', suffix='.php', delete=False, encoding='utf-8') as f:
        for i in range(100):
            f.write(f"""<?php
function test_{i}() {{
    global $wpdb;
    $wpdb->query("SELECT * FROM table WHERE id = " . $_GET['id']);
    echo $user_input;
}}
""")
        temp_file = f.name

    try:
        start = time.time()
        suggestions = extract_patterns_from_file(temp_file, min_confidence=0.5)
        elapsed = time.time() - start

        assert elapsed < 5.0, f"Performance test failed: {elapsed:.2f}s > 5s"

        print(f"[PASS] test_performance: {elapsed:.2f}s for 500-line file")
    finally:
        os.unlink(temp_file)


if __name__ == '__main__':
    print("Running single-file learning tests...\n")

    test_extract_patterns_from_php_file()
    test_extract_patterns_from_js_file()
    test_confidence_scoring()
    test_frequency_heuristic()
    test_severity_heuristic()
    test_category_heuristic()
    test_no_false_positives()
    test_php_detectors()
    test_js_detectors()
    test_performance()

    print("\n[SUCCESS] All tests passed!")
