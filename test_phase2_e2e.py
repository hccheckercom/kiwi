"""
End-to-end test for Phase 2: Auto-disable + Re-enable

Simulates:
1. Create fake violations with high FP rate
2. Trigger auto-disable
3. Verify disabled lessons are filtered
4. Re-enable lesson
5. Verify lesson is active again
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from memory.db import get_connection
from memory.confidence import (
    update_hit,
    recalculate_confidence,
    auto_disable_noisy_patterns,
    get_disabled_lessons
)

def setup_test_data():
    """Create test lesson with high FP rate"""
    print("Setting up test data...")

    lesson_id = "LES-999-TEST"

    # Simulate 10 hits with 9 false positives (90% FP rate)
    # This gives confidence = 0.1 which is < 0.2 threshold
    for i in range(10):
        is_tp = i < 1  # Only first 1 is true positive
        update_hit(lesson_id, is_true_positive=is_tp)

    # Recalculate confidence
    conf = recalculate_confidence(lesson_id)
    print(f"Created {lesson_id}: confidence={conf:.2f}, FP rate=90%")

    return lesson_id

def test_auto_disable():
    """Test auto-disable with 90% FP threshold"""
    print("\n" + "=" * 60)
    print("TEST: Auto-disable noisy patterns")
    print("=" * 60)

    # Check DB state (auto-disable already called by recalculate_confidence in setup)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT lesson_id, confidence, total_hits, disabled, disabled_reason
            FROM lesson_confidence
            WHERE lesson_id = 'LES-999-TEST'
        """)
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        print("ERROR: LES-999-TEST not found in DB")
        return False

    lesson_id, conf, total, disabled, reason = row
    print(f"DB state: lesson_id={lesson_id}, confidence={conf:.2f}, total_hits={total}, disabled={disabled}")
    print(f"Disabled reason: {reason}")

    if disabled != 1:
        print("ERROR: Expected disabled=1")
        return False

    print(f"SUCCESS: Lesson auto-disabled with reason: {reason}")

    # Verify in DB
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT lesson_id, disabled, disabled_reason, confidence
            FROM lesson_confidence
            WHERE lesson_id = 'LES-999-TEST'
        """)
        row = cursor.fetchone()
    finally:
        conn.close()

    if row:
        print(f"  lesson_id: {row[0]}")
        print(f"  disabled: {row[1]}")
        print(f"  reason: {row[2]}")
        print(f"  confidence: {row[3]:.2f}")

        if row[1] != 1:
            print("ERROR: Lesson should be disabled=1")
            return False

    return True

def test_get_disabled_lessons():
    """Test get_disabled_lessons()"""
    print("\n" + "=" * 60)
    print("TEST: Get disabled lessons")
    print("=" * 60)

    disabled_list = get_disabled_lessons()
    print(f"Disabled lessons: {disabled_list}")

    if 'LES-999-TEST' not in disabled_list:
        print("ERROR: LES-999-TEST should be in disabled list")
        return False

    print("SUCCESS: LES-999-TEST found in disabled list")
    return True

def test_reenable():
    """Test re-enable functionality"""
    print("\n" + "=" * 60)
    print("TEST: Re-enable lesson")
    print("=" * 60)

    lesson_id = "LES-999-TEST"

    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Re-enable
        cursor.execute("""
            UPDATE lesson_confidence
            SET disabled = 0,
                disabled_reason = NULL,
                disabled_at = NULL
            WHERE lesson_id = ?
        """, (lesson_id,))
        conn.commit()

        # Verify
        cursor.execute("SELECT disabled FROM lesson_confidence WHERE lesson_id = ?", (lesson_id,))
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row or row[0] != 0:
        print(f"ERROR: Lesson should be disabled=0, got {row}")
        return False

    print(f"SUCCESS: Re-enabled {lesson_id}")

    # Verify not in disabled list
    disabled_list = get_disabled_lessons()
    if lesson_id in disabled_list:
        print("ERROR: Lesson should not be in disabled list after re-enable")
        return False

    print("SUCCESS: Lesson removed from disabled list")
    return True

def cleanup():
    """Remove test data"""
    print("\n" + "=" * 60)
    print("Cleanup")
    print("=" * 60)

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM lesson_confidence WHERE lesson_id = 'LES-999-TEST'")
        conn.commit()
    finally:
        conn.close()

    print("Removed test data")

if __name__ == "__main__":
    print("\nEnd-to-End Test: Phase 2 (Auto-disable + Re-enable)\n")

    try:
        # Setup
        lesson_id = setup_test_data()

        # Test 1: Auto-disable
        if not test_auto_disable():
            sys.exit(1)

        # Test 2: Get disabled lessons
        if not test_get_disabled_lessons():
            sys.exit(1)

        # Test 3: Re-enable
        if not test_reenable():
            sys.exit(1)

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)

    finally:
        # Always cleanup
        cleanup()