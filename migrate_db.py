"""
Run database migration to add disabled columns to lesson_confidence table
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from memory.db import init_db, get_connection

def run_migration():
    print("Running database migration...")
    print("=" * 60)

    # Run init_db which includes migration logic
    init_db()

    # Verify columns were added
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(lesson_confidence)")
        columns = [row[1] for row in cursor.fetchall()]

        print("\nColumns in lesson_confidence table:")
        for col in columns:
            print(f"  - {col}")

        # Check if disabled columns exist
        required_cols = ['disabled', 'disabled_reason', 'disabled_at']
        missing = [col for col in required_cols if col not in columns]

        if missing:
            print(f"\nERROR: Missing columns: {missing}")
            return False

        print("\nSUCCESS: All required columns exist")
    finally:
        conn.close()
    return True

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)