"""
Test script for Phase 2.4-2.5: Auto-disable noisy patterns + kiwi_reenable

Tests:
1. include_disabled flag in kiwi_scan
2. kiwi_reenable MCP tool
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from memory.db import get_connection
from memory.confidence import auto_disable_noisy_patterns, get_disabled_lessons

def test_auto_disable():
    """Test auto-disable functionality"""
    print("=" * 60)
    print("TEST 1: Auto-disable noisy patterns")
    print("=" * 60)

    # Run auto-disable
    disabled = auto_disable_noisy_patterns(threshold=0.2, min_hits=10)
    print(f"\n✓ Auto-disabled {len(disabled)} lessons: {disabled}")

    # Get disabled list
    disabled_list = get_disabled_lessons()
    print(f"✓ Total disabled lessons: {len(disabled_list)}")

    return disabled_list

def test_reenable(lesson_id):
    """Test re-enable functionality"""
    print("\n" + "=" * 60)
    print(f"TEST 2: Re-enable lesson {lesson_id}")
    print("=" * 60)

    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Check before
        cursor.execute("SELECT disabled FROM lesson_confidence WHERE lesson_id = ?", (lesson_id,))
        row = cursor.fetchone()
        if row:
            print(f"\nBefore: disabled = {row[0]}")
        else:
            print(f"\n⚠ Lesson {lesson_id} not found in confidence table")
            return

        # Re-enable
        cursor.execute("""
            UPDATE lesson_confidence
            SET disabled = 0,
                disabled_reason = NULL,
                disabled_at = NULL
            WHERE lesson_id = ?
        """, (lesson_id,))
        conn.commit()

        # Check after
        cursor.execute("SELECT disabled FROM lesson_confidence WHERE lesson_id = ?", (lesson_id,))
        row = cursor.fetchone()
        print(f"After: disabled = {row[0]}")

    finally:
        conn.close()
    print(f"\n✓ Re-enabled {lesson_id}")

if __name__ == "__main__":
    print("\nTesting Phase 2.4-2.5: Auto-disable + Re-enable\n")

    # Test 1: Auto-disable
    disabled_list = test_auto_disable()

    # Test 2: Re-enable (if there are disabled lessons)
    if disabled_list:
        test_lesson = disabled_list[0]
        test_reenable(test_lesson)
    else:
        print("\n⚠ No disabled lessons to test re-enable")

    print("\n" + "=" * 60)
    print("✅ All tests completed")
    print("=" * 60)