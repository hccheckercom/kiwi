"""Initialize theme_knowledge.db with learning schema"""

import sqlite3
from pathlib import Path
from datetime import datetime

KIWI_DIR = Path(__file__).parent.parent
DB_PATH = KIWI_DIR / "theme_knowledge.db"
SCHEMA_PATH = KIWI_DIR / "memory" / "schema_learning.sql"


def init_learning_db():
    """Create theme_knowledge.db with schema from schema_learning.sql"""

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Execute schema
    cursor.executescript(schema_sql)
    conn.commit()

    # Verify tables created
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    print(f"[OK] Database created: {DB_PATH}")
    print(f"[OK] Tables: {', '.join(tables)}")

    # Check schema version
    cursor.execute("SELECT version, applied_at FROM schema_version")
    version, applied_at = cursor.fetchone()
    print(f"[OK] Schema version: {version} (applied: {applied_at})")

    conn.close()

    return DB_PATH


if __name__ == "__main__":
    db_path = init_learning_db()
    print(f"\n[OK] Theme knowledge database ready: {db_path}")