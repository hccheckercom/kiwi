"""Test P4: User Feedback Loop."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.db import get_connection, init_db
from agent.feedback_loop import (
    analyze_dismiss_patterns,
    suggest_regex_tune,
    apply_feedback_to_confidence,
    get_lessons_needing_tune,
    auto_apply_feedback,
)


def setup_test_data():
    """Create test data for feedback loop testing."""
    init_db()
    conn = get_connection()

    # Clear existing test data
    conn.execute("DELETE FROM false_positives WHERE lesson_id LIKE 'FEED-%'")
    conn.execute("DELETE FROM lesson_confidence WHERE lesson_id LIKE 'FEED-%'")
    conn.execute("DELETE FROM feedback_adjustments WHERE lesson_id LIKE 'FEED-%'")
    conn.commit()

    # Test case 1: FEED-001 with recurring dismiss pattern (test files)
    for i in range(7):
        conn.execute("""
            INSERT INTO false_positives
            (lesson_id, file, match_text, reason, dismissed_at, scope, active)
            VALUES ('FEED-001', ?, 'test code', 'false positive in test file', datetime('now'), 'file', 1)
        """, (f"tests/test_{i}.php",))

    # Test case 2: FEED-002 with recurring pattern (already called in parent)
    for i in range(6):
        conn.execute("""
            INSERT INTO false_positives
            (lesson_id, file, match_text, reason, dismissed_at, scope, active)
            VALUES ('FEED-002', 'plugin.php', 'wz_config()', 'wz_config already called in parent scope', datetime('now'), 'file', 1)
        """)

    # Test case 3: FEED-003 with mixed patterns (no clear dominant pattern)
    conn.execute("""
        INSERT INTO false_positives
        (lesson_id, file, match_text, reason, dismissed_at, scope, active)
        VALUES ('FEED-003', 'file1.php', 'code', 'reason A', datetime('now'), 'file', 1)
    """)
    conn.execute("""
        INSERT INTO false_positives
        (lesson_id, file, match_text, reason, dismissed_at, scope, active)
        VALUES ('FEED-003', 'file2.php', 'code', 'reason B', datetime('now'), 'file', 1)
    """)
    conn.execute("""
        INSERT INTO false_positives
        (lesson_id, file, match_text, reason, dismissed_at, scope, active)
        VALUES ('FEED-003', 'file3.php', 'code', 'reason C', datetime('now'), 'file', 1)
    """)

    # Create lesson_confidence entries
    conn.execute("""
        INSERT INTO lesson_confidence
        (lesson_id, total_hits, true_positive_count, false_positive_count,
         fix_success_count, fix_failure_count, confidence, effective_severity)
        VALUES ('FEED-001', 20, 13, 7, 10, 3, 0.85, 'HIGH')
    """)

    conn.execute("""
        INSERT INTO lesson_confidence
        (lesson_id, total_hits, true_positive_count, false_positive_count,
         fix_success_count, fix_failure_count, confidence, effective_severity)
        VALUES ('FEED-002', 15, 9, 6, 8, 1, 0.80, 'CRITICAL')
    """)

    conn.execute("""
        INSERT INTO lesson_confidence
        (lesson_id, total_hits, true_positive_count, false_positive_count,
         fix_success_count, fix_failure_count, confidence, effective_severity)
        VALUES ('FEED-003', 10, 7, 3, 5, 2, 0.90, 'HIGH')
    """)

    # Test case 4: FEED-004 with many approvals (should increase confidence)
    conn.execute("""
        INSERT INTO lesson_confidence
        (lesson_id, total_hits, true_positive_count, false_positive_count,
         fix_success_count, fix_failure_count, confidence, effective_severity)
        VALUES ('FEED-004', 30, 28, 2, 25, 3, 0.75, 'CRITICAL')
    """)

    conn.commit()
    conn.close()


def test_analyze_patterns():
    """Test dismiss pattern analysis."""
    print("Test 1: Analyze dismiss patterns")

    # FEED-001: should find "test file" pattern
    patterns = analyze_dismiss_patterns('FEED-001', min_occurrences=3)
    assert len(patterns) > 0
    # Check for "false positive in" or "in test file" pattern
    found_test_pattern = any('test file' in p['pattern'] for p in patterns)
    assert found_test_pattern
    print(f"  OK FEED-001: found {len(patterns)} patterns, including test file pattern")

    # FEED-002: should find "already called" pattern
    patterns = analyze_dismiss_patterns('FEED-002', min_occurrences=3)
    assert len(patterns) > 0
    found_already_pattern = any('already called' in p['pattern'] for p in patterns)
    assert found_already_pattern
    print(f"  OK FEED-002: found {len(patterns)} patterns, including 'already called' pattern")

    # FEED-003: no recurring pattern (< 3 occurrences each)
    patterns = analyze_dismiss_patterns('FEED-003', min_occurrences=3)
    assert len(patterns) == 0
    print(f"  OK FEED-003: no recurring patterns (mixed reasons)")

    print("  PASS\n")


def test_suggest_tune():
    """Test regex tune suggestions."""
    print("Test 2: Suggest regex tune")

    # FEED-001: 7 dismissals, should suggest tune
    suggestion = suggest_regex_tune('FEED-001', min_dismissals=5)
    assert suggestion is not None
    assert suggestion['total_dismissals'] == 7
    assert len(suggestion['patterns']) > 0
    print(f"  OK FEED-001: {suggestion['total_dismissals']} dismissals, tune suggested")
    print(f"     Action: {suggestion['recommended_action'][:80]}...")

    # FEED-002: 6 dismissals, should suggest tune
    suggestion = suggest_regex_tune('FEED-002', min_dismissals=5)
    assert suggestion is not None
    assert suggestion['total_dismissals'] == 6
    print(f"  OK FEED-002: {suggestion['total_dismissals']} dismissals, tune suggested")

    # FEED-003: 3 dismissals, below threshold
    suggestion = suggest_regex_tune('FEED-003', min_dismissals=5)
    assert suggestion is None
    print(f"  OK FEED-003: below threshold, no tune suggested")

    print("  PASS\n")


def test_apply_feedback():
    """Test applying feedback to confidence."""
    print("Test 3: Apply feedback to confidence")

    # FEED-001: 7 dismissals, 10 approvals
    # adjustment = (10 * 0.01) - (7 * 0.02) = 0.10 - 0.14 = -0.04
    result1 = apply_feedback_to_confidence('FEED-001')
    assert 'error' not in result1
    assert result1['dismissals'] == 7
    assert result1['approvals'] == 10
    assert result1['adjustment'] == -0.04
    # Use approximate comparison for floating point
    expected = result1['old_confidence'] - 0.04
    assert abs(result1['new_confidence'] - expected) < 0.01
    print(f"  OK FEED-001: {result1['old_confidence']:.2f} -> {result1['new_confidence']:.2f} (adjustment {result1['adjustment']:+.2f})")

    # FEED-004: 2 dismissals, 25 approvals
    # adjustment = (25 * 0.01) - (2 * 0.02) = 0.25 - 0.04 = +0.21
    result4 = apply_feedback_to_confidence('FEED-004')
    assert result4['adjustment'] == 0.21
    assert result4['new_confidence'] == min(1.0, result4['old_confidence'] + 0.21)
    print(f"  OK FEED-004: {result4['old_confidence']:.2f} -> {result4['new_confidence']:.2f} (adjustment {result4['adjustment']:+.2f})")

    # Verify DB updated
    conn = get_connection()
    row = conn.execute("""
        SELECT confidence FROM lesson_confidence WHERE lesson_id = 'FEED-001'
    """).fetchone()
    assert abs(row['confidence'] - result1['new_confidence']) < 0.01
    print(f"  OK DB updated correctly")

    # Verify history logged
    history = conn.execute("""
        SELECT * FROM feedback_adjustments
        WHERE lesson_id = 'FEED-001'
        ORDER BY timestamp DESC
        LIMIT 1
    """).fetchone()
    assert history is not None
    assert abs(history['adjustment'] - (-0.04)) < 0.01
    print(f"  OK History logged")

    conn.close()
    print("  PASS\n")


def test_needing_tune():
    """Test getting lessons needing tune."""
    print("Test 4: Get lessons needing tune")

    lessons = get_lessons_needing_tune(min_dismissals=5)

    # Should include FEED-001 (7 dismissals) and FEED-002 (6 dismissals)
    # Should NOT include FEED-003 (3 dismissals)
    lesson_ids = [l['lesson_id'] for l in lessons]
    assert 'FEED-001' in lesson_ids
    assert 'FEED-002' in lesson_ids
    assert 'FEED-003' not in lesson_ids
    print(f"  OK Found {len(lessons)} lessons needing tune")
    print(f"     Lessons: {lesson_ids}")

    print("  PASS\n")


def test_auto_apply():
    """Test auto-apply feedback."""
    print("Test 5: Auto-apply feedback")

    # Reset FEED-001 confidence for this test
    conn = get_connection()
    conn.execute("""
        UPDATE lesson_confidence
        SET confidence = 0.85
        WHERE lesson_id = 'FEED-001'
    """)
    conn.execute("DELETE FROM feedback_adjustments WHERE lesson_id = 'FEED-001'")
    conn.commit()
    conn.close()

    # Auto-apply with min_dismissals=5
    results = auto_apply_feedback(min_dismissals=5, dry_run=False)

    # Should process FEED-001 (7 dismissals) and FEED-002 (6 dismissals)
    # FEED-004 has only 2 dismissals but 25 approvals, so should also be processed
    lesson_ids = [r['lesson_id'] for r in results]
    assert 'FEED-001' in lesson_ids
    assert 'FEED-002' in lesson_ids
    print(f"  OK Auto-applied feedback to {len(results)} lessons")

    # Verify adjustments
    for r in results:
        if r['lesson_id'] == 'FEED-001':
            assert r['adjustment'] < 0  # more dismissals than approvals
        elif r['lesson_id'] == 'FEED-004':
            assert r['adjustment'] > 0  # more approvals than dismissals

    print(f"  OK Adjustments calculated correctly")

    print("  PASS\n")


def cleanup_test_data():
    """Clean up test data."""
    conn = get_connection()
    conn.execute("DELETE FROM false_positives WHERE lesson_id LIKE 'FEED-%'")
    conn.execute("DELETE FROM lesson_confidence WHERE lesson_id LIKE 'FEED-%'")
    conn.execute("DELETE FROM feedback_adjustments WHERE lesson_id LIKE 'FEED-%'")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("P4: User Feedback Loop - Test Suite")
    print("=" * 60 + "\n")

    try:
        setup_test_data()
        test_analyze_patterns()
        test_suggest_tune()
        test_apply_feedback()
        test_needing_tune()
        test_auto_apply()

        print("=" * 60)
        print("ALL TESTS PASSED OK")
        print("=" * 60)

    except AssertionError as e:
        print(f"\nX TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

    finally:
        cleanup_test_data()