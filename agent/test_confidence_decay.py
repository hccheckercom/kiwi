"""Test P2: Confidence Decay Theo Thoi Gian."""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.db import get_connection, init_db
from agent.confidence_decay import (
    calculate_decay,
    apply_decay,
    apply_decay_all,
    get_stale_lessons,
    reset_decay,
)


def setup_test_data():
    """Create test data for decay testing."""
    init_db()
    conn = get_connection()

    # Clear existing test data
    conn.execute("DELETE FROM lesson_confidence WHERE lesson_id LIKE 'DECAY-%'")
    conn.execute("DELETE FROM decay_history WHERE lesson_id LIKE 'DECAY-%'")
    conn.commit()

    now = datetime.now(timezone.utc)

    # Test case 1: 35 days old (1 decay period) - confidence 0.90 -> 0.81
    last_hit_1 = (now - timedelta(days=35)).isoformat()
    conn.execute("""
        INSERT INTO lesson_confidence
        (lesson_id, total_hits, true_positive_count, false_positive_count,
         confidence, effective_severity, last_hit)
        VALUES ('DECAY-001', 50, 45, 5, 0.90, 'CRITICAL', ?)
    """, (last_hit_1,))

    # Test case 2: 65 days old (2 decay periods) - confidence 0.80 -> 0.648
    last_hit_2 = (now - timedelta(days=65)).isoformat()
    conn.execute("""
        INSERT INTO lesson_confidence
        (lesson_id, total_hits, true_positive_count, false_positive_count,
         confidence, effective_severity, last_hit)
        VALUES ('DECAY-002', 40, 32, 8, 0.80, 'HIGH', ?)
    """, (last_hit_2,))

    # Test case 3: 125 days old (4 decay periods) - confidence 0.70 -> 0.46
    # Should trigger "needs review" (< 0.50)
    # Period 1: 0.70 - 0.07 = 0.63
    # Period 2: 0.63 - 0.063 = 0.567
    # Period 3: 0.567 - 0.0567 = 0.51
    # Period 4: 0.51 - 0.051 = 0.459
    last_hit_3 = (now - timedelta(days=125)).isoformat()
    conn.execute("""
        INSERT INTO lesson_confidence
        (lesson_id, total_hits, true_positive_count, false_positive_count,
         confidence, effective_severity, last_hit)
        VALUES ('DECAY-003', 30, 21, 9, 0.70, 'HIGH', ?)
    """, (last_hit_3,))

    # Test case 4: 20 days old (no decay yet)
    last_hit_4 = (now - timedelta(days=20)).isoformat()
    conn.execute("""
        INSERT INTO lesson_confidence
        (lesson_id, total_hits, true_positive_count, false_positive_count,
         confidence, effective_severity, last_hit)
        VALUES ('DECAY-004', 25, 20, 5, 0.85, 'CRITICAL', ?)
    """, (last_hit_4,))

    # Test case 5: No last_hit (never fired)
    conn.execute("""
        INSERT INTO lesson_confidence
        (lesson_id, total_hits, true_positive_count, false_positive_count,
         confidence, effective_severity, last_hit)
        VALUES ('DECAY-005', 0, 0, 0, 1.0, 'HIGH', NULL)
    """)

    conn.commit()
    conn.close()


def test_calculate_decay():
    """Test decay calculation."""
    print("Test 1: Calculate decay")

    # DECAY-001: 35 days, 1 period
    result = calculate_decay('DECAY-001')
    assert result['days_since_hit'] >= 35
    assert result['decay_periods'] == 1
    # 0.90 - (0.90 * 0.10) = 0.81
    assert abs(result['new_confidence'] - 0.81) < 0.01
    assert result['needs_review'] == False
    print(f"  OK DECAY-001: {result['current_confidence']:.2f} -> {result['new_confidence']:.2f} (1 period)")

    # DECAY-002: 65 days, 2 periods
    result = calculate_decay('DECAY-002')
    assert result['decay_periods'] == 2
    # Period 1: 0.80 - 0.08 = 0.72
    # Period 2: 0.72 - 0.072 = 0.648
    assert abs(result['new_confidence'] - 0.65) < 0.02
    print(f"  OK DECAY-002: {result['current_confidence']:.2f} -> {result['new_confidence']:.2f} (2 periods)")

    # DECAY-003: 125 days, 4 periods - should need review
    result = calculate_decay('DECAY-003')
    assert result['decay_periods'] == 4
    assert result['new_confidence'] < 0.50
    assert result['needs_review'] == True
    print(f"  OK DECAY-003: {result['current_confidence']:.2f} -> {result['new_confidence']:.2f} (needs review)")

    # DECAY-004: 20 days, no decay
    result = calculate_decay('DECAY-004')
    assert result['decay_periods'] == 0
    assert result['new_confidence'] == result['current_confidence']
    print(f"  OK DECAY-004: no decay (20 days)")

    # DECAY-005: no last_hit
    result = calculate_decay('DECAY-005')
    assert 'message' in result
    assert result['decay_periods'] == 0
    print(f"  OK DECAY-005: no hits recorded")

    print("  PASS\n")


def test_apply_decay():
    """Test apply decay with DB update."""
    print("Test 2: Apply decay")

    # Apply to DECAY-001
    result = apply_decay('DECAY-001', dry_run=False)
    assert result['applied'] == True
    assert result['new_confidence'] < result['current_confidence']

    # Verify DB updated
    conn = get_connection()
    row = conn.execute("""
        SELECT confidence FROM lesson_confidence WHERE lesson_id = 'DECAY-001'
    """).fetchone()
    assert abs(row['confidence'] - result['new_confidence']) < 0.01
    print(f"  OK DECAY-001 applied: confidence updated to {row['confidence']:.2f}")

    # Verify history logged
    history = conn.execute("""
        SELECT * FROM decay_history WHERE lesson_id = 'DECAY-001'
    """).fetchone()
    assert history is not None
    assert history['days_since_hit'] >= 35
    assert history['decay_amount'] > 0
    print(f"  OK History logged: decay_amount {history['decay_amount']:.2f}")

    conn.close()
    print("  PASS\n")


def test_apply_decay_all():
    """Test apply decay to all eligible lessons."""
    print("Test 3: Apply decay all")

    # Reset DECAY-001 for this test
    conn = get_connection()
    conn.execute("""
        UPDATE lesson_confidence
        SET confidence = 0.90
        WHERE lesson_id = 'DECAY-001'
    """)
    conn.execute("DELETE FROM decay_history WHERE lesson_id = 'DECAY-001'")
    conn.commit()
    conn.close()

    # Apply decay to all (min_days=30)
    results = apply_decay_all(min_days=30, dry_run=False)

    # Should decay DECAY-001, DECAY-002, DECAY-003
    # Should skip DECAY-004 (< 30 days) and DECAY-005 (no last_hit)
    lesson_ids = [r['lesson_id'] for r in results]
    assert 'DECAY-001' in lesson_ids
    assert 'DECAY-002' in lesson_ids
    assert 'DECAY-003' in lesson_ids
    assert 'DECAY-004' not in lesson_ids
    print(f"  OK Applied decay to {len(results)} lessons")

    # Check for needs_review warnings
    needs_review = [r for r in results if r.get('needs_review')]
    assert len(needs_review) > 0
    print(f"  OK {len(needs_review)} lessons need review (confidence < 0.50)")

    print("  PASS\n")


def test_stale_lessons():
    """Test get stale lessons."""
    print("Test 4: Get stale lessons")

    stale = get_stale_lessons(confidence_threshold=0.50)

    # DECAY-003 should be in stale list (confidence < 0.50 after decay)
    stale_ids = [s['lesson_id'] for s in stale]
    assert 'DECAY-003' in stale_ids
    print(f"  OK Found {len(stale)} stale lessons")

    # Verify days_since_hit calculated
    decay_003 = next(s for s in stale if s['lesson_id'] == 'DECAY-003')
    assert decay_003['days_since_hit'] >= 125
    print(f"  OK DECAY-003: {decay_003['days_since_hit']} days since hit")

    print("  PASS\n")


def test_reset_decay():
    """Test reset decay timer."""
    print("Test 5: Reset decay timer")

    # Reset DECAY-001
    result = reset_decay('DECAY-001')
    assert result['action'] == 'reset_decay'

    # Verify last_hit updated
    conn = get_connection()
    row = conn.execute("""
        SELECT last_hit FROM lesson_confidence WHERE lesson_id = 'DECAY-001'
    """).fetchone()

    from agent.confidence_decay import _parse_iso
    last_hit = _parse_iso(row['last_hit'])
    now = datetime.now(timezone.utc)
    diff = (now - last_hit).total_seconds()

    # Should be within last 5 seconds
    assert diff < 5
    print(f"  OK DECAY-001 last_hit reset to now")

    # Calculate decay again - should be 0 periods
    from agent.confidence_decay import calculate_decay
    decay_result = calculate_decay('DECAY-001')
    assert decay_result['decay_periods'] == 0
    print(f"  OK DECAY-001 decay periods reset to 0")

    conn.close()
    print("  PASS\n")


def cleanup_test_data():
    """Clean up test data."""
    conn = get_connection()
    conn.execute("DELETE FROM lesson_confidence WHERE lesson_id LIKE 'DECAY-%'")
    conn.execute("DELETE FROM decay_history WHERE lesson_id LIKE 'DECAY-%'")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("P2: Confidence Decay - Test Suite")
    print("=" * 60 + "\n")

    try:
        setup_test_data()
        test_calculate_decay()
        test_apply_decay()
        test_apply_decay_all()
        test_stale_lessons()
        test_reset_decay()

        print("=" * 60)
        print("ALL TESTS PASSED OK")
        print("=" * 60)

    except AssertionError as e:
        print(f"\nX TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

    finally:
        cleanup_test_data()