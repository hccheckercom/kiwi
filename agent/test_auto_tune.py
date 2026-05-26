"""Test P1: Auto-tune Noisy Lessons."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.db import get_connection, init_db
from agent.auto_tune import (
    calculate_lesson_metrics,
    auto_tune_lesson,
    auto_tune_all,
    get_severity_demotion,
)


def setup_test_data():
    """Create test data for auto-tune."""
    init_db()
    conn = get_connection()

    # Clear existing test data
    conn.execute("DELETE FROM lesson_confidence WHERE lesson_id LIKE 'TEST-%'")
    conn.execute("DELETE FROM auto_tune_history WHERE lesson_id LIKE 'TEST-%'")
    conn.commit()

    # Test case 1: Noisy lesson (precision 0.67, fp_rate 0.33) → should demote
    conn.execute("""
        INSERT INTO lesson_confidence
        (lesson_id, total_hits, true_positive_count, false_positive_count,
         fix_success_count, fix_failure_count, confidence, effective_severity)
        VALUES ('TEST-001', 30, 20, 10, 15, 5, 0.85, 'CRITICAL')
    """)

    # Test case 2: Very noisy lesson (precision 0.40) → should disable
    conn.execute("""
        INSERT INTO lesson_confidence
        (lesson_id, total_hits, true_positive_count, false_positive_count,
         fix_success_count, fix_failure_count, confidence, effective_severity)
        VALUES ('TEST-002', 50, 20, 30, 10, 10, 0.70, 'HIGH')
    """)

    # Test case 3: Good lesson (precision 0.90) → no action
    conn.execute("""
        INSERT INTO lesson_confidence
        (lesson_id, total_hits, true_positive_count, false_positive_count,
         fix_success_count, fix_failure_count, confidence, effective_severity)
        VALUES ('TEST-003', 40, 36, 4, 30, 6, 0.95, 'CRITICAL')
    """)

    # Test case 4: Already at lowest severity (SUGGEST) → no action
    conn.execute("""
        INSERT INTO lesson_confidence
        (lesson_id, total_hits, true_positive_count, false_positive_count,
         fix_success_count, fix_failure_count, confidence, effective_severity)
        VALUES ('TEST-004', 25, 15, 10, 10, 5, 0.75, 'SUGGEST')
    """)

    # Test case 5: Insufficient data (< 10 hits) → should skip
    conn.execute("""
        INSERT INTO lesson_confidence
        (lesson_id, total_hits, true_positive_count, false_positive_count,
         fix_success_count, fix_failure_count, confidence, effective_severity)
        VALUES ('TEST-005', 5, 3, 2, 2, 1, 0.80, 'HIGH')
    """)

    conn.commit()
    conn.close()


def test_calculate_metrics():
    """Test metric calculation."""
    print("Test 1: Calculate metrics")

    metrics = calculate_lesson_metrics('TEST-001')
    assert metrics is not None
    assert metrics['precision'] == 0.67  # 20/(20+10)
    assert metrics['false_positive_rate'] == 0.33  # 10/30
    assert metrics['total_hits'] == 30
    print("  OK TEST-001 metrics correct")

    metrics = calculate_lesson_metrics('TEST-002')
    assert metrics['precision'] == 0.40  # 20/(20+30)
    print("  OK TEST-002 metrics correct")

    metrics = calculate_lesson_metrics('TEST-003')
    assert metrics['precision'] == 0.90  # 36/(36+4)
    print("  OK TEST-003 metrics correct")

    print("  PASS\n")


def test_severity_demotion():
    """Test severity demotion logic."""
    print("Test 2: Severity demotion")

    assert get_severity_demotion('CRITICAL') == 'HIGH'
    assert get_severity_demotion('HIGH') == 'SUGGEST'
    assert get_severity_demotion('SUGGEST') is None
    print("  OK Demotion chain correct")
    print("  PASS\n")


def test_auto_tune_single():
    """Test auto-tune single lesson."""
    print("Test 3: Auto-tune single lesson (dry-run)")

    # TEST-001: should demote CRITICAL → HIGH
    result = auto_tune_lesson('TEST-001', dry_run=True)
    assert result['action'] == 'demote'
    assert result['old_severity'] == 'CRITICAL'
    assert result['new_severity'] == 'HIGH'
    print(f"  OK TEST-001: {result['action']} {result['old_severity']} -> {result['new_severity']}")

    # TEST-002: should disable
    result = auto_tune_lesson('TEST-002', dry_run=True)
    assert result['action'] == 'disable'
    print(f"  OK TEST-002: {result['action']} (precision {result['metrics']['precision']:.2f})")

    # TEST-003: no action (good lesson)
    result = auto_tune_lesson('TEST-003', dry_run=True)
    assert result['action'] == 'none'
    print(f"  OK TEST-003: {result['action']} (precision {result['metrics']['precision']:.2f})")

    # TEST-004: no action (already SUGGEST)
    result = auto_tune_lesson('TEST-004', dry_run=True)
    assert result['action'] == 'none'
    print(f"  OK TEST-004: {result['action']} (already at lowest severity)")

    print("  PASS\n")


def test_auto_tune_apply():
    """Test auto-tune with apply (not dry-run)."""
    print("Test 4: Auto-tune with apply")

    # Apply tune to TEST-001
    result = auto_tune_lesson('TEST-001', dry_run=False)
    assert result['action'] == 'demote'

    # Verify DB updated
    conn = get_connection()
    row = conn.execute("""
        SELECT effective_severity FROM lesson_confidence WHERE lesson_id = 'TEST-001'
    """).fetchone()
    assert row['effective_severity'] == 'HIGH'
    print("  OK TEST-001 demoted to HIGH in DB")

    # Verify history logged
    history = conn.execute("""
        SELECT * FROM auto_tune_history WHERE lesson_id = 'TEST-001'
    """).fetchone()
    assert history is not None
    assert history['action'] == 'demote'
    assert history['old_severity'] == 'CRITICAL'
    assert history['new_severity'] == 'HIGH'
    print("  OK History logged correctly")

    conn.close()
    print("  PASS\n")


def test_auto_tune_all():
    """Test auto-tune all lessons."""
    print("Test 5: Auto-tune all lessons")

    # Reset TEST-001 for this test
    conn = get_connection()
    conn.execute("""
        UPDATE lesson_confidence
        SET effective_severity = 'CRITICAL'
        WHERE lesson_id = 'TEST-001'
    """)
    conn.execute("DELETE FROM auto_tune_history WHERE lesson_id = 'TEST-001'")
    conn.commit()
    conn.close()

    # Run auto-tune all (min_hits=10, so TEST-005 should be skipped)
    results = auto_tune_all(min_hits=10, dry_run=False)

    # Should tune TEST-001 (demote) and TEST-002 (disable)
    # TEST-003 and TEST-004 should have no action
    # TEST-005 should be skipped (< 10 hits)
    actions = [r['action'] for r in results]
    assert 'demote' in actions  # TEST-001
    assert 'disable' in actions  # TEST-002
    print(f"  OK Tuned {len(results)} lessons")

    # Verify TEST-002 disabled
    conn = get_connection()
    row = conn.execute("""
        SELECT disabled, disabled_reason FROM lesson_confidence WHERE lesson_id = 'TEST-002'
    """).fetchone()
    assert row['disabled'] == 1
    assert 'precision' in row['disabled_reason'].lower()
    print("  OK TEST-002 disabled in DB")

    conn.close()
    print("  PASS\n")


def cleanup_test_data():
    """Clean up test data."""
    conn = get_connection()
    conn.execute("DELETE FROM lesson_confidence WHERE lesson_id LIKE 'TEST-%'")
    conn.execute("DELETE FROM auto_tune_history WHERE lesson_id LIKE 'TEST-%'")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("P1: Auto-tune Noisy Lessons - Test Suite")
    print("=" * 60 + "\n")

    try:
        setup_test_data()
        test_calculate_metrics()
        test_severity_demotion()
        test_auto_tune_single()
        test_auto_tune_apply()
        test_auto_tune_all()

        print("=" * 60)
        print("ALL TESTS PASSED OK")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

    finally:
        cleanup_test_data()