"""UsageTracker — singleton that records every Kiwi operation into SQLite."""

import sqlite3
import time
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "memory" / "kiwi.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

_instance: Optional["UsageTracker"] = None


def get_tracker() -> "UsageTracker":
    global _instance
    if _instance is None:
        _instance = UsageTracker()
    return _instance


class UsageTracker:

    def __init__(self, db_path: Path = None):
        self._db_path = db_path or DB_PATH
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is not None:
            try:
                self._conn.execute("SELECT 1")
                return self._conn
            except sqlite3.Error:
                self._conn = None

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), timeout=5)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=3000")
        self._conn.row_factory = sqlite3.Row
        return self._conn

    def _ensure_schema(self):
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='usage_events'"
        )
        if cursor.fetchone() is None:
            schema = SCHEMA_PATH.read_text(encoding="utf-8")
            conn.executescript(schema)

    def record(
        self,
        operation: str,
        target_path: str = None,
        sub_operation: str = None,
        session_id: str = None,
        tokens_local: int = 0,
        tokens_claude: int = 0,
        cost_actual_usd: float = 0.0,
        latency_ms: int = 0,
        tokens_baseline: int = None,
        cost_baseline_usd: float = None,
        latency_baseline_ms: int = None,
        violations_found: int = 0,
        files_processed: int = 0,
        success: bool = True,
    ) -> int:
        from .baseline_estimator import estimate_baseline

        if tokens_baseline is None or cost_baseline_usd is None:
            est = estimate_baseline(
                operation=operation,
                files_processed=files_processed,
                file_lines=0,
            )
            if tokens_baseline is None:
                tokens_baseline = est["tokens"]
            if cost_baseline_usd is None:
                cost_baseline_usd = est["cost_usd"]
            if latency_baseline_ms is None:
                latency_baseline_ms = est["latency_ms"]

        conn = self._get_conn()
        cursor = conn.execute(
            "INSERT INTO usage_events "
            "(timestamp, session_id, operation, sub_operation, target_path, "
            "tokens_local, tokens_claude, cost_actual_usd, latency_ms, "
            "tokens_baseline, cost_baseline_usd, latency_baseline_ms, "
            "violations_found, files_processed, success) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                time.time(),
                session_id,
                operation,
                sub_operation,
                target_path,
                tokens_local,
                tokens_claude,
                cost_actual_usd,
                latency_ms,
                tokens_baseline,
                cost_baseline_usd,
                latency_baseline_ms,
                violations_found,
                files_processed,
                1 if success else 0,
            ),
        )
        conn.commit()
        return cursor.lastrowid

    def get_events(self, limit: int = 100, operation: str = None) -> list:
        conn = self._get_conn()
        if operation:
            rows = conn.execute(
                "SELECT * FROM usage_events WHERE operation = ? ORDER BY timestamp DESC LIMIT ?",
                (operation, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM usage_events ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_event_count(self) -> int:
        conn = self._get_conn()
        return conn.execute("SELECT COUNT(*) FROM usage_events").fetchone()[0]

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None