"""Test P5: A/B Testing Framework."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.db import get_connection, init_db
from agent.ab_testing import (
    create_ab_test,
    record_ab_result,
    calculate_ab_metrics,
    finalize_ab_test,
    get_active_tests,
)


def setup_test_data():
    """Create test data for A/B testing."""
    init_db()
    conn = get_connection()

    # Clear existing test data
    conn.execute("DELETE FROM ab_tests WHERE lesson_id LIKE 'AB-%'")
    conn.execute("DELETE FROM ab_results WHERE test_id IN (SELECT id FROM ab_tests WHERE lesson_id LIKE 'AB-%')")
    conn.commit()

    # Create fake scan_id
    conn.execute("""
        INSERT INTO scan_history (path, timestamp, violations_total)
        VALUES ('test', datetime('now'), 0)
    """)
    scan_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.commit()
    conn.close()

    return scan_id


def test_create_ab_test():
    """Test creating A/B test."""
    print("Test 1: Create A/B test")

    result = create_ab_test(
        'AB-001',
        'baseline_pattern.*',
        'variant_pattern.*',
        'Test improved pattern',
        target_scans=10
    )

    assert 'error' not in result
    assert result['lesson_id'] == 'AB-001'
    assert result['status'] == 'active'
    print(f"  OK Created test {result['test_id']} for AB-001")

    # Try to create duplicate - should fail
    result2 = create_ab_test(
        'AB-001',
        'baseline_pattern.*',
        'variant_pattern.*',
        'Duplicate test',
        target_scans=10
    )
    assert 'error' in result2
    print(f"  OK Duplicate test prevented")

    print("  PASS\n")
    return result['test_id']


def test_record_results(test_id, scan_id):
    """Test recording A/B results."""
    print("Test 2: Record A/B results")

    # Record baseline results (good performance)
    for i in range(10):
        result = record_ab_result(
            test_id, 'baseline', scan_id,
            true_positives=9, false_positives=1, false_negatives=1,
            fix_success=8, fix_failure=1
        )
        assert 'error' not in result
        assert result['version'] == 'baseline'

    print(f"  OK Recorded 10 baseline results")

    # Record variant results (better performance)
    for i in range(10):
        result = record_ab_result(
            test_id, 'variant', scan_id,
            true_positives=10, false_positives=0, false_negatives=0,
            fix_success=9, fix_failure=1
        )
        assert 'error' not in result
        assert result['version'] == 'variant'

    print(f"  OK Recorded 10 variant results")

    print("  PASS\n")


def test_calculate_metrics(test_id):
    """Test calculating A/B metrics."""
    print("Test 3: Calculate metrics")

    metrics = calculate_ab_metrics(test_id)

    assert 'error' not in metrics
    assert metrics['baseline']['scans'] == 10
    assert metrics['variant']['scans'] == 10

    # Baseline: 90 TP, 10 FP, 10 FN
    # Precision = 90/(90+10) = 0.90
    # Recall = 90/(90+10) = 0.90
    assert metrics['baseline']['precision'] == 0.90
    assert metrics['baseline']['recall'] == 0.90

    # Variant: 100 TP, 0 FP, 0 FN
    # Precision = 100/(100+0) = 1.00
    # Recall = 100/(100+0) = 1.00
    assert metrics['variant']['precision'] == 1.00
    assert metrics['variant']['recall'] == 1.00

    # Variant should be winner
    assert metrics['winner'] == 'variant'
    assert metrics['confidence'] > 0.0

    print(f"  OK Baseline: precision {metrics['baseline']['precision']:.2f}, recall {metrics['baseline']['recall']:.2f}, F1 {metrics['baseline']['f1_score']:.2f}")
    print(f"  OK Variant: precision {metrics['variant']['precision']:.2f}, recall {metrics['variant']['recall']:.2f}, F1 {metrics['variant']['f1_score']:.2f}")
    print(f"  OK Winner: {metrics['winner']} (confidence {metrics['confidence']:.2f})")

    print("  PASS\n")


def test_finalize(test_id):
    """Test finalizing A/B test."""
    print("Test 4: Finalize A/B test")

    result = finalize_ab_test(test_id)

    assert 'error' not in result
    assert result['winner'] == 'variant'
    assert result['action'] == 'applied'
    print(f"  OK Finalized test: winner={result['winner']}, action={result['action']}")

    # Verify test status updated
    conn = get_connection()
    row = conn.execute("""
        SELECT status, winner FROM ab_tests WHERE id = ?
    """, (test_id,)).fetchone()
    assert row['status'] == 'completed'
    assert row['winner'] == 'variant'
    print(f"  OK Test status updated to completed")

    conn.close()
    print("  PASS\n")


def test_active_tests():
    """Test getting active tests."""
    print("Test 5: Get active tests")

    # Create another active test
    result = create_ab_test(
        'AB-002',
        'baseline2.*',
        'variant2.*',
        'Another test',
        target_scans=10
    )
    test_id_2 = result['test_id']

    # Get active tests
    active = get_active_tests()

    # Should have AB-002 (AB-001 was finalized)
    lesson_ids = [t['lesson_id'] for t in active]
    assert 'AB-002' in lesson_ids
    assert 'AB-001' not in lesson_ids  # finalized
    print(f"  OK Found {len(active)} active tests")
    print(f"     Active: {lesson_ids}")

    print("  PASS\n")


def test_tie_scenario():
    """Test tie scenario (similar performance)."""
    print("Test 6: Tie scenario")

    # Create test
    result = create_ab_test(
        'AB-003',
        'baseline3.*',
        'variant3.*',
        'Tie test',
        target_scans=10
    )
    test_id = result['test_id']

    conn = get_connection()
    scan_id = conn.execute("SELECT id FROM scan_history LIMIT 1").fetchone()[0]
    conn.close()

    # Record similar results for both versions
    for i in range(10):
        # Baseline: precision 0.90, recall 0.90
        record_ab_result(
            test_id, 'baseline', scan_id,
            true_positives=9, false_positives=1, false_negatives=1,
            fix_success=8, fix_failure=1
        )
        # Variant: precision 0.91, recall 0.91 (very close)
        record_ab_result(
            test_id, 'variant', scan_id,
            true_positives=91, false_positives=9, false_negatives=9,
            fix_success=80, fix_failure=10
        )

    metrics = calculate_ab_metrics(test_id)

    # Should be tie (diff < 0.05)
    assert metrics['winner'] == 'tie'
    print(f"  OK Detected tie: baseline F1 {metrics['baseline']['f1_score']:.2f}, variant F1 {metrics['variant']['f1_score']:.2f}")

    # Finalize should keep baseline
    result = finalize_ab_test(test_id)
    assert result['winner'] == 'tie'
    assert result['action'] == 'no_change'
    print(f"  OK Tie finalized: action={result['action']}")

    print("  PASS\n")


def cleanup_test_data():
    """Clean up test data."""
    conn = get_connection()
    conn.execute("DELETE FROM ab_tests WHERE lesson_id LIKE 'AB-%'")
    conn.execute("DELETE FROM ab_results WHERE test_id IN (SELECT id FROM ab_tests WHERE lesson_id LIKE 'AB-%')")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("P5: A/B Testing Framework - Test Suite")
    print("=" * 60 + "\n")

    try:
        scan_id = setup_test_data()
        test_id = test_create_ab_test()
        test_record_results(test_id, scan_id)
        test_calculate_metrics(test_id)
        test_finalize(test_id)
        test_active_tests()
        test_tie_scenario()

        print("=" * 60)
        print("ALL TESTS PASSED OK")
        print("=" * 60)

    except AssertionError as e:
        print(f"\nX TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

    finally:
        cleanup_test_data()