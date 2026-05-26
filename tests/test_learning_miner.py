"""
Test pattern mining from scan history.

Tests the mine_patterns() function that discovers recurring patterns.
"""

import os
import sys
from pathlib import Path

# Add kiwi to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def test_mine_patterns_basic():
    """Test basic pattern mining with mock violations"""
    print("=" * 60)
    print("TEST 1: Basic pattern mining")
    print("=" * 60)

    from learning.miner import mine_patterns
    from memory.db import get_connection

    # Insert mock violations into database
    conn = get_connection()

    # Create scan history entry
    cursor = conn.execute("""
        INSERT INTO scan_history (path, platform, severity, timestamp)
        VALUES ('test-project', 'wp', 'ALL', datetime('now'))
    """)
    scan_id = cursor.lastrowid

    # Insert similar violations (should cluster)
    violations = [
        ("test1.php", 10, "$_GET['id']", "LES-001"),
        ("test2.php", 15, "$_GET['user']", "LES-001"),
        ("test3.php", 20, "$_GET['page']", "LES-001"),
        ("test4.php", 25, "$_GET['action']", "LES-001"),
        ("test5.php", 30, "$_GET['type']", "LES-001"),
    ]

    for file, line, match_text, lesson_id in violations:
        conn.execute("""
            INSERT INTO violations (scan_id, lesson_id, file, line, match_text, detected_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (scan_id, lesson_id, file, line, match_text))

    conn.commit()

    # Mine patterns
    patterns = mine_patterns(min_occurrences=3, similarity_threshold=0.7, lookback_days=1)

    print(f"Found {len(patterns)} patterns")

    # Cleanup
    conn.execute("DELETE FROM violations WHERE scan_id = ?", (scan_id,))
    conn.execute("DELETE FROM scan_history WHERE id = ?", (scan_id,))
    conn.execute("DELETE FROM suggested_lessons")
    conn.commit()
    conn.close()

    assert len(patterns) >= 1, "Should find at least 1 pattern from similar violations"
    print(f"✓ Pattern mining works: {patterns[0].pattern}")

    return True


def test_mine_patterns_no_violations():
    """Test pattern mining with no violations"""
    print("\n" + "=" * 60)
    print("TEST 2: Pattern mining with no violations")
    print("=" * 60)

    from learning.miner import mine_patterns

    patterns = mine_patterns(min_occurrences=5, lookback_days=1)

    print(f"Found {len(patterns)} patterns (expected 0)")

    assert len(patterns) == 0, "Should find no patterns when no violations exist"
    print("✓ Correctly returns empty list")

    return True


def test_clustering():
    """Test violation clustering by similarity"""
    print("\n" + "=" * 60)
    print("TEST 3: Violation clustering")
    print("=" * 60)

    from learning.miner import _cluster_violations

    violations = [
        {"match_text": "$_GET['id']"},
        {"match_text": "$_GET['user']"},
        {"match_text": "$_GET['page']"},
        {"match_text": "echo $output"},  # Different pattern
        {"match_text": "echo $result"},  # Different pattern
    ]

    clusters = _cluster_violations(violations, threshold=0.7)

    print(f"Created {len(clusters)} clusters")
    for i, cluster in enumerate(clusters):
        print(f"  Cluster {i+1}: {len(cluster)} items")

    assert len(clusters) >= 2, "Should create at least 2 clusters for different patterns"
    print("✓ Clustering works correctly")

    return True


def test_mine_patterns_large_dataset():
    """Test pattern mining with 1000+ violations for performance"""
    print("\n" + "=" * 60)
    print("TEST 4: Large dataset performance (1000+ violations)")
    print("=" * 60)

    from learning.miner import mine_patterns
    from memory.db import get_connection
    import time

    conn = get_connection()

    # Create scan history
    cursor = conn.execute("""
        INSERT INTO scan_history (path, platform, severity, timestamp)
        VALUES ('large-project', 'wp', 'ALL', datetime('now'))
    """)
    scan_id = cursor.lastrowid

    # Insert 1000 similar violations
    print("Inserting 1000 violations...")
    for i in range(1000):
        conn.execute("""
            INSERT INTO violations (scan_id, lesson_id, file, line, match_text, detected_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (scan_id, "LES-001", f"test{i % 100}.php", i, f"$_GET['param{i % 50}']", ))

    conn.commit()

    # Mine patterns and measure time
    start = time.time()
    patterns = mine_patterns(min_occurrences=10, similarity_threshold=0.7, lookback_days=1)
    elapsed = time.time() - start

    print(f"Found {len(patterns)} patterns in {elapsed:.2f}s")

    # Cleanup
    conn.execute("DELETE FROM violations WHERE scan_id = ?", (scan_id,))
    conn.execute("DELETE FROM scan_history WHERE id = ?", (scan_id,))
    conn.execute("DELETE FROM suggested_lessons")
    conn.commit()
    conn.close()

    assert elapsed < 5.0, f"Performance regression: took {elapsed:.2f}s (expected <5s)"
    assert len(patterns) >= 1, "Should find patterns from 1000 violations"
    print(f"✓ Performance acceptable: {elapsed:.2f}s")

    return True


def test_clustering_edge_cases():
    """Test clustering with edge cases: empty strings, unicode, very long text"""
    print("\n" + "=" * 60)
    print("TEST 5: Clustering edge cases")
    print("=" * 60)

    from learning.miner import _cluster_violations

    violations = [
        {"match_text": ""},  # Empty string
        {"match_text": ""},  # Another empty
        {"match_text": "Tiếng Việt có dấu"},  # Unicode
        {"match_text": "Tiếng Việt không dấu"},  # Similar unicode
        {"match_text": "x" * 1000},  # Very long text
        {"match_text": "y" * 1000},  # Another long text
    ]

    clusters = _cluster_violations(violations, threshold=0.7)

    print(f"Created {len(clusters)} clusters from edge cases")
    for i, cluster in enumerate(clusters):
        print(f"  Cluster {i+1}: {len(cluster)} items")

    assert len(clusters) >= 1, "Should handle edge cases without crashing"
    print("✓ Edge cases handled correctly")

    return True


def test_pattern_extraction_quality():
    """Test that extracted patterns are valid and useful"""
    print("\n" + "=" * 60)
    print("TEST 6: Pattern extraction quality")
    print("=" * 60)

    from learning.miner import _extract_pattern_from_cluster

    cluster = [
        {"file": "test1.php", "line": 10, "match_text": "$_GET['id']"},
        {"file": "test2.php", "line": 15, "match_text": "$_GET['user']"},
        {"file": "test3.php", "line": 20, "match_text": "$_GET['page']"},
    ]

    pattern_obj = _extract_pattern_from_cluster(cluster, '.php')

    assert pattern_obj is not None, "Should extract pattern from cluster"
    assert pattern_obj.pattern, "Pattern should not be empty"
    assert pattern_obj.occurrence_count == 3, f"Should track 3 occurrences, got {pattern_obj.occurrence_count}"
    assert pattern_obj.category == 'php-security', f"Should detect php-security category, got {pattern_obj.category}"
    assert pattern_obj.severity == 'CRITICAL', f"Security patterns should be CRITICAL, got {pattern_obj.severity}"
    assert 0.0 < pattern_obj.confidence <= 1.0, f"Confidence should be in (0, 1], got {pattern_obj.confidence}"

    print(f"Extracted pattern: {pattern_obj.pattern}")
    print(f"Category: {pattern_obj.category}, Severity: {pattern_obj.severity}")
    print(f"Confidence: {pattern_obj.confidence:.2f}, Occurrences: {pattern_obj.occurrence_count}")
    print("✓ Pattern extraction quality acceptable")

    return True


def test_confidence_scoring():
    """Test confidence calculation logic"""
    print("\n" + "=" * 60)
    print("TEST 7: Confidence scoring")
    print("=" * 60)

    from learning.miner import _extract_pattern_from_cluster

    # Small cluster (low confidence)
    small_cluster = [
        {"file": "test1.php", "line": 10, "match_text": "echo $var"},
        {"file": "test2.php", "line": 15, "match_text": "echo $data"},
    ]

    small_pattern = _extract_pattern_from_cluster(small_cluster, '.php')
    print(f"Small cluster (2 items): confidence = {small_pattern.confidence:.2f}")

    # Large cluster (high confidence)
    large_cluster = [{"file": f"test{i}.php", "line": i, "match_text": f"$_GET['var{i}']"} for i in range(15)]

    large_pattern = _extract_pattern_from_cluster(large_cluster, '.php')
    print(f"Large cluster (15 items): confidence = {large_pattern.confidence:.2f}")

    assert small_pattern.confidence < large_pattern.confidence, "Larger clusters should have higher confidence"
    assert 0.0 <= small_pattern.confidence <= 1.0, "Confidence should be in [0, 1]"
    assert 0.0 <= large_pattern.confidence <= 1.0, "Confidence should be in [0, 1]"
    print("✓ Confidence scoring works correctly")

    return True


def test_category_inference():
    """Test category detection rules"""
    print("\n" + "=" * 60)
    print("TEST 8: Category inference")
    print("=" * 60)

    from learning.miner import _infer_category

    # PHP security patterns
    php_security = _infer_category(["$_GET['id']", "$_POST['data']"], '.php')
    print(f"PHP $_GET/$_POST → {php_security}")
    assert php_security == 'php-security', f"Expected 'php-security', got '{php_security}'"

    # SQL patterns
    sql_pattern = _infer_category(["$wpdb->query($sql)", "SELECT * FROM"], '.php')
    print(f"SQL patterns → {sql_pattern}")
    assert sql_pattern == 'php-security', f"Expected 'php-security', got '{sql_pattern}'"

    # CSS patterns
    css_pattern = _infer_category(["color: #fff", "margin: 10px"], '.css')
    print(f"CSS patterns → {css_pattern}")
    assert css_pattern == 'css-tokens', f"Expected 'css-tokens', got '{css_pattern}'"

    # JS patterns
    js_pattern = _infer_category(["fetch('/api')", "axios.get()"], '.js')
    print(f"JS fetch/axios → {js_pattern}")
    assert js_pattern == 'js-contract', f"Expected 'js-contract', got '{js_pattern}'"

    # React patterns
    react_pattern = _infer_category(["useState()", "useEffect()"], '.tsx')
    print(f"React hooks → {react_pattern}")
    assert react_pattern == 'nextjs-react', f"Expected 'nextjs-react', got '{react_pattern}'"

    print("✓ All category inference rules working")

    return True


def test_severity_inference():
    """Test severity assignment logic"""
    print("\n" + "=" * 60)
    print("TEST 9: Severity inference")
    print("=" * 60)

    from learning.miner import _infer_severity

    # Security = CRITICAL
    security_cluster = [{"match_text": "$_GET['id']"}] * 5
    severity = _infer_severity(security_cluster, 'php-security')
    print(f"Security category → {severity}")
    assert severity == 'CRITICAL', f"Security should be CRITICAL, got {severity}"

    # High occurrence = HIGH
    high_cluster = [{"match_text": "test"}] * 12
    severity = _infer_severity(high_cluster, 'code-quality')
    print(f"12 occurrences → {severity}")
    assert severity == 'HIGH', f"12 occurrences should be HIGH, got {severity}"

    # Low occurrence = SUGGEST
    low_cluster = [{"match_text": "test"}] * 3
    severity = _infer_severity(low_cluster, 'code-quality')
    print(f"3 occurrences → {severity}")
    assert severity == 'SUGGEST', f"3 occurrences should be SUGGEST, got {severity}"

    print("✓ Severity inference working correctly")

    return True


def test_database_transaction_rollback():
    """Test cleanup on error"""
    print("\n" + "=" * 60)
    print("TEST 10: Database transaction rollback")
    print("=" * 60)

    from learning.miner import mine_patterns
    from memory.db import get_connection

    conn = get_connection()

    # Create invalid scan data that should cause error
    cursor = conn.execute("""
        INSERT INTO scan_history (path, platform, severity, timestamp)
        VALUES ('test-rollback', 'wp', 'ALL', datetime('now'))
    """)
    scan_id = cursor.lastrowid

    # Insert violations with missing required fields
    try:
        conn.execute("""
            INSERT INTO violations (scan_id, lesson_id, file, line, match_text, detected_at)
            VALUES (?, NULL, NULL, NULL, NULL, datetime('now'))
        """, (scan_id,))
        conn.commit()
    except Exception:
        conn.rollback()

    # Verify database is still consistent
    cursor = conn.execute("SELECT COUNT(*) FROM violations WHERE scan_id = ?", (scan_id,))
    count = cursor.fetchone()[0]

    # Cleanup
    conn.execute("DELETE FROM scan_history WHERE id = ?", (scan_id,))
    conn.commit()
    conn.close()

    print(f"Violations after rollback: {count}")
    assert count == 0, "Rollback should prevent invalid data insertion"
    print("✓ Transaction rollback working")

    return True


if __name__ == "__main__":
    print("\nLearning Miner Tests\n")

    tests = [
        test_mine_patterns_basic,
        test_mine_patterns_no_violations,
        test_clustering,
        test_mine_patterns_large_dataset,
        test_clustering_edge_cases,
        test_pattern_extraction_quality,
        test_confidence_scoring,
        test_category_inference,
        test_severity_inference,
        test_database_transaction_rollback,
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
