"""Migrate confidence.db to add rollback tracking columns."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "kiwi.db"


def migrate_add_rollback_columns():
    """Add rollback_count and last_rollback_at columns to lesson_confidence."""

    # First, ensure DB is initialized
    from db import init_db
    init_db()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(lesson_confidence)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'rollback_count' not in columns:
            print("Adding rollback_count column...")
            cursor.execute("""
                ALTER TABLE lesson_confidence
                ADD COLUMN rollback_count INTEGER DEFAULT 0
            """)
            print("✓ rollback_count added")
        else:
            print("✓ rollback_count already exists")

        if 'last_rollback_at' not in columns:
            print("Adding last_rollback_at column...")
            cursor.execute("""
                ALTER TABLE lesson_confidence
                ADD COLUMN last_rollback_at TEXT
            """)
            print("✓ last_rollback_at added")
        else:
            print("✓ last_rollback_at already exists")

        conn.commit()
        print("\n[SUCCESS] Migration complete")

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_add_rollback_columns()