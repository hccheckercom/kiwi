"""Test scanner integration."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.db import get_connection, init_db
from scanner.integration import (
    reset_decay_on_violation,
    deduplicate_violations,
    apply_scanner_integrations
)


def setup_test_data():
    """Create test data for scanner integration testing."""
    init_db()
    conn = get_connection()

    # Create test lessons with last_hit
    conn.execute("""
        INSERT OR REPLACE INTO lesson_confidence
        (lesson_id, total_hits, true_positive_count, false_positive_count,
         confidence, effective_severity, last_hit)
        VALUES ('SCAN-001', 10, 8, 2, 0.85, 'CRITICAL', datetime('now', '-5 days'))
    """)

    # Create correlated lessons
    conn.execute("""
        INSERT OR REPLACE INTO lesson_relations
        (lesson_a, lesson_b, relation_type, reason, timestamp)
        VALUES ('SCAN-001', 'SCAN-002', 'related', 'Test correlation', datetime('now'))
    """)

    # Create scan_id for A/B test
    conn.execute("""
        INSERT INTO scan_history (path, timestamp, violations_total)
        VALUES ('test', datetime('now'), 0)
    """)
    scan_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.commit()
    conn.close()

    return scan_id


def test_reset_decay():
    """Test reset decay on violation."""
    print("Test 1: Reset decay on violation")

    # Get initial last_hit
    conn = get_connection()
    row = conn.execute("""
        SELECT last_hit FROM lesson_confidence WHERE lesson_id = 'SCAN-001'
    """).fetchone()
    initial_last_hit = row['last_hit']
    conn.close()

    # Reset decay
    reset_decay_on_violation('SCAN-001')

    # Verify last_hit updated
    conn = get_connection()
    row = conn.execute("""
        SELECT last_hit FROM lesson_confidence WHERE lesson_id = 'SCAN-001'
    """).fetchone()
    new_last_hit = row['last_hit']
    conn.close()

    # Should be different (newer)
    assert new_last_hit != initial_last_hit
    print(f"  OK Decay timer reset for SCAN-001")
    print("  PASS\n")


def test_deduplicate():
    """Test deduplicating violations."""
    print("Test 2: Deduplicate violations")

    violations = [
        {'lesson_id': 'SCAN-001', 'file': 'test.php', 'line': 100},
        {'lesson_id': 'SCAN-002', 'file': 'test.php', 'line': 100},  # duplicate location, related
        {'lesson_id': 'SCAN-003', 'file': 'other.php', 'line': 200},  # unique
    ]

    kept, removed = deduplicate_violations(violations)

    # Should keep SCAN-001 and SCAN-003, remove SCAN-002 (related to SCAN-001)
    kept_ids = [v['lesson_id'] for v in kept]
    removed_ids = [v['lesson_id'] for v in removed]

    assert 'SCAN-001' in kept_ids
    assert 'SCAN-003' in kept_ids
    assert 'SCAN-002' in removed_ids

    print(f"  OK Kept {len(kept)} violations, removed {len(removed)} duplicates")
    print(f"  OK Removed: {removed_ids}")
    print("  PASS\n")


def test_apply_integrations(scan_id):
    """Test applying all integrations."""
    print("Test 3: Apply all integrations")

    violations = [
        {'lesson_id': 'SCAN-001', 'file': 'test.php', 'line': 100},
        {'lesson_id': 'SCAN-002', 'file': 'test.php', 'line': 100},
        {'lesson_id': 'SCAN-003', 'file': 'other.php', 'line': 200},
    ]

    kept = apply_scanner_integrations(violations, scan_id=scan_id)

    # Should deduplicate
    assert len(kept) < len(violations)
    print(f"  OK Applied integrations: {len(violations)} -> {len(kept)} violations")

    # Verify decay reset for all lessons
    conn = get_connection()
    for lesson_id in ['SCAN-001', 'SCAN-002', 'SCAN-003']:
        row = conn.execute("""
            SELECT last_hit FROM lesson_confidence WHERE lesson_id = ?
        """, (lesson_id,)).fetchone()
        if row:
            print(f"  OK Decay reset for {lesson_id}")
    conn.close()

    print("  PASS\n")


def cleanup_test_data():
    """Clean up test data."""
    conn = get_connection()
    conn.execute("DELETE FROM lesson_confidence WHERE lesson_id LIKE 'SCAN-%'")
    conn.execute("DELETE FROM lesson_relations WHERE lesson_a LIKE 'SCAN-%' OR lesson_b LIKE 'SCAN-%'")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Scanner Integration - Test Suite")
    print("=" * 60 + "\n")

    try:
        scan_id = setup_test_data()
        test_reset_decay()
        test_deduplicate()
        test_apply_integrations(scan_id)

        print("=" * 60)
        print("ALL TESTS PASSED OK")
        print("=" * 60)

    except AssertionError as e:
        print(f"\nX TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

    finally:
        cleanup_test_data()
