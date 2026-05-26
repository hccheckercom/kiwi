"""Test P3: Cross-Lesson Correlation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.db import get_connection, init_db
from agent.correlation import (
    calculate_correlation,
    find_correlated_lessons,
    mark_as_related,
    get_related_lessons,
    deduplicate_violations,
    auto_mark_correlated,
)


def setup_test_data():
    """Create test data for correlation testing."""
    init_db()
    conn = get_connection()

    # Clear existing test data
    conn.execute("DELETE FROM violations WHERE lesson_id LIKE 'CORR-%'")
    conn.execute("DELETE FROM lesson_relations WHERE lesson_a LIKE 'CORR-%' OR lesson_b LIKE 'CORR-%'")
    conn.commit()

    # Create fake scan_id
    conn.execute("""
        INSERT INTO scan_history (path, timestamp, violations_total)
        VALUES ('test', datetime('now'), 0)
    """)
    scan_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Test case 1: CORR-001 and CORR-002 highly correlated (8/10 same locations)
    # CORR-001: 10 violations
    for i in range(10):
        conn.execute("""
            INSERT INTO violations (scan_id, lesson_id, file, line, detected_at)
            VALUES (?, 'CORR-001', 'test.php', ?, datetime('now'))
        """, (scan_id, 100 + i))

    # CORR-002: 10 violations, 8 overlap with CORR-001
    for i in range(8):
        conn.execute("""
            INSERT INTO violations (scan_id, lesson_id, file, line, detected_at)
            VALUES (?, 'CORR-002', 'test.php', ?, datetime('now'))
        """, (scan_id, 100 + i))
    # 2 unique to CORR-002
    conn.execute("""
        INSERT INTO violations (scan_id, lesson_id, file, line, detected_at)
        VALUES (?, 'CORR-002', 'test.php', 200, datetime('now'))
    """, (scan_id,))
    conn.execute("""
        INSERT INTO violations (scan_id, lesson_id, file, line, detected_at)
        VALUES (?, 'CORR-002', 'test.php', 201, datetime('now'))
    """, (scan_id,))

    # Test case 2: CORR-003 and CORR-004 low correlation (2/10 same locations)
    # CORR-003: 10 violations
    for i in range(10):
        conn.execute("""
            INSERT INTO violations (scan_id, lesson_id, file, line, detected_at)
            VALUES (?, 'CORR-003', 'other.php', ?, datetime('now'))
        """, (scan_id, 300 + i))

    # CORR-004: 10 violations, only 2 overlap
    for i in range(2):
        conn.execute("""
            INSERT INTO violations (scan_id, lesson_id, file, line, detected_at)
            VALUES (?, 'CORR-004', 'other.php', ?, datetime('now'))
        """, (scan_id, 300 + i))
    # 8 unique to CORR-004
    for i in range(8):
        conn.execute("""
            INSERT INTO violations (scan_id, lesson_id, file, line, detected_at)
            VALUES (?, 'CORR-004', 'other.php', ?, datetime('now'))
        """, (scan_id, 400 + i))

    # Test case 3: CORR-005 no overlap with others
    for i in range(5):
        conn.execute("""
            INSERT INTO violations (scan_id, lesson_id, file, line, detected_at)
            VALUES (?, 'CORR-005', 'unique.php', ?, datetime('now'))
        """, (scan_id, 500 + i))

    conn.commit()
    conn.close()


def test_calculate_correlation():
    """Test correlation calculation."""
    print("Test 1: Calculate correlation")

    # CORR-001 and CORR-002: high correlation (8/10)
    result = calculate_correlation('CORR-001', 'CORR-002')
    assert result['co_occurrences'] == 8
    assert result['lesson_a_total'] == 10
    assert result['lesson_b_total'] == 10
    # correlation = 8 / min(10, 10) = 0.80
    assert result['correlation'] == 0.80
    print(f"  OK CORR-001 <-> CORR-002: correlation {result['correlation']:.2f}, co-occurrences {result['co_occurrences']}")

    # CORR-003 and CORR-004: low correlation (2/10)
    result = calculate_correlation('CORR-003', 'CORR-004')
    assert result['co_occurrences'] == 2
    # correlation = 2 / min(10, 10) = 0.20
    assert result['correlation'] == 0.20
    print(f"  OK CORR-003 <-> CORR-004: correlation {result['correlation']:.2f}, co-occurrences {result['co_occurrences']}")

    # CORR-001 and CORR-005: no overlap
    result = calculate_correlation('CORR-001', 'CORR-005')
    assert result['co_occurrences'] == 0
    assert result['correlation'] == 0.0
    print(f"  OK CORR-001 <-> CORR-005: correlation {result['correlation']:.2f} (no overlap)")

    print("  PASS\n")


def test_find_correlated():
    """Test finding correlated lessons."""
    print("Test 2: Find correlated lessons")

    # Find with min_correlation=0.80, min_co_occurrences=3
    results = find_correlated_lessons(min_correlation=0.80, min_co_occurrences=3)

    # Should find CORR-001 <-> CORR-002 (correlation 0.80, 8 co-occurrences)
    # Should NOT find CORR-003 <-> CORR-004 (correlation 0.20)
    assert len(results) >= 1
    found = any(
        (r['lesson_a'] == 'CORR-001' and r['lesson_b'] == 'CORR-002') or
        (r['lesson_a'] == 'CORR-002' and r['lesson_b'] == 'CORR-001')
        for r in results
    )
    assert found
    print(f"  OK Found {len(results)} correlated pairs")
    print(f"  OK CORR-001 <-> CORR-002 detected")

    print("  PASS\n")


def test_mark_related():
    """Test marking lessons as related."""
    print("Test 3: Mark lessons as related")

    # Mark CORR-001 and CORR-002 as related
    result = mark_as_related('CORR-001', 'CORR-002', reason="Test: high correlation")
    assert result['action'] == 'marked_related'
    print(f"  OK Marked CORR-001 <-> CORR-002 as related")

    # Verify in DB
    conn = get_connection()
    row = conn.execute("""
        SELECT * FROM lesson_relations
        WHERE (lesson_a = 'CORR-001' AND lesson_b = 'CORR-002')
        OR (lesson_a = 'CORR-002' AND lesson_b = 'CORR-001')
    """).fetchone()
    assert row is not None
    assert row['relation_type'] == 'related'
    print(f"  OK Relation stored in DB")

    # Try to mark again - should return already_related
    result = mark_as_related('CORR-001', 'CORR-002', reason="Test: duplicate")
    assert result['action'] == 'already_related'
    print(f"  OK Duplicate mark prevented")

    conn.close()
    print("  PASS\n")


def test_get_related():
    """Test getting related lessons."""
    print("Test 4: Get related lessons")

    # Get related lessons for CORR-001
    related = get_related_lessons('CORR-001')
    assert 'CORR-002' in related
    print(f"  OK CORR-001 related to: {related}")

    # Get related lessons for CORR-002
    related = get_related_lessons('CORR-002')
    assert 'CORR-001' in related
    print(f"  OK CORR-002 related to: {related}")

    # Get related lessons for CORR-005 (none)
    related = get_related_lessons('CORR-005')
    assert len(related) == 0
    print(f"  OK CORR-005 has no related lessons")

    print("  PASS\n")


def test_deduplicate_violations():
    """Test deduplicating violations."""
    print("Test 5: Deduplicate violations")

    # Create violations list with duplicates
    violations = [
        {'lesson_id': 'CORR-001', 'file': 'test.php', 'line': 100},
        {'lesson_id': 'CORR-002', 'file': 'test.php', 'line': 100},  # duplicate location, related
        {'lesson_id': 'CORR-003', 'file': 'other.php', 'line': 300},
        {'lesson_id': 'CORR-004', 'file': 'other.php', 'line': 300},  # duplicate location, not related
        {'lesson_id': 'CORR-005', 'file': 'unique.php', 'line': 500},  # unique
    ]

    kept, removed = deduplicate_violations(violations)

    # Should keep CORR-001, remove CORR-002 (related)
    # Should keep both CORR-003 and CORR-004 (not related)
    # Should keep CORR-005 (unique)
    kept_ids = [v['lesson_id'] for v in kept]
    removed_ids = [v['lesson_id'] for v in removed]

    assert 'CORR-001' in kept_ids
    assert 'CORR-002' in removed_ids
    assert 'CORR-003' in kept_ids
    assert 'CORR-004' in kept_ids
    assert 'CORR-005' in kept_ids

    print(f"  OK Kept {len(kept)} violations, removed {len(removed)} duplicates")
    print(f"  OK Removed: {removed_ids}")

    print("  PASS\n")


def test_auto_mark():
    """Test auto-mark correlated lessons."""
    print("Test 6: Auto-mark correlated lessons")

    # Clear existing relations
    conn = get_connection()
    conn.execute("DELETE FROM lesson_relations WHERE lesson_a LIKE 'CORR-%' OR lesson_b LIKE 'CORR-%'")
    conn.commit()
    conn.close()

    # Auto-mark with min_correlation=0.80, min_co_occurrences=5
    results = auto_mark_correlated(min_correlation=0.80, min_co_occurrences=5, dry_run=False)

    # Should mark CORR-001 <-> CORR-002 (correlation 0.80, 8 co-occurrences)
    assert len(results) >= 1
    marked = any(
        (r['lesson_a'] == 'CORR-001' and r['lesson_b'] == 'CORR-002') or
        (r['lesson_a'] == 'CORR-002' and r['lesson_b'] == 'CORR-001')
        for r in results
    )
    assert marked
    print(f"  OK Auto-marked {len(results)} pairs")

    # Verify in DB
    conn = get_connection()
    row = conn.execute("""
        SELECT * FROM lesson_relations
        WHERE (lesson_a = 'CORR-001' AND lesson_b = 'CORR-002')
        OR (lesson_a = 'CORR-002' AND lesson_b = 'CORR-001')
    """).fetchone()
    assert row is not None
    assert 'Auto-marked' in row['reason']
    print(f"  OK Relation stored with auto-mark reason")

    conn.close()
    print("  PASS\n")


def cleanup_test_data():
    """Clean up test data."""
    conn = get_connection()
    conn.execute("DELETE FROM violations WHERE lesson_id LIKE 'CORR-%'")
    conn.execute("DELETE FROM lesson_relations WHERE lesson_a LIKE 'CORR-%' OR lesson_b LIKE 'CORR-%'")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("P3: Cross-Lesson Correlation - Test Suite")
    print("=" * 60 + "\n")

    try:
        setup_test_data()
        test_calculate_correlation()
        test_find_correlated()
        test_mark_related()
        test_get_related()
        test_deduplicate_violations()
        test_auto_mark()

        print("=" * 60)
        print("ALL TESTS PASSED OK")
        print("=" * 60)

    except AssertionError as e:
        print(f"\nX TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

    finally:
        cleanup_test_data()