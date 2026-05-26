"""SQLite usage tracking for Kiwi Command Factory."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "kiwi.db"

COMMAND_SCHEMA = """
CREATE TABLE IF NOT EXISTS command_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    command     TEXT NOT NULL,
    action      TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    success     BOOLEAN DEFAULT 1,
    error_msg   TEXT,
    duration_ms INTEGER DEFAULT 0,
    notes       TEXT
);

CREATE INDEX IF NOT EXISTS idx_cmd_name ON command_history(command);
CREATE INDEX IF NOT EXISTS idx_cmd_time ON command_history(timestamp);

CREATE TABLE IF NOT EXISTS command_feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    command     TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    feedback    TEXT NOT NULL,
    category    TEXT DEFAULT 'general'
);

CREATE INDEX IF NOT EXISTS idx_fb_cmd ON command_feedback(command);
"""


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(COMMAND_SCHEMA)
    return conn


def log_invocation(command: str, action: str, success: bool = True,
                   error_msg: str = "", duration_ms: int = 0, notes: str = ""):
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO command_history (command, action, timestamp, success, error_msg, duration_ms, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (command, action, datetime.now(timezone.utc).isoformat(), success, error_msg, duration_ms, notes),
        )
        conn.commit()
    finally:
        conn.close()


def add_feedback(command: str, feedback: str, category: str = "general"):
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO command_feedback (command, timestamp, feedback, category) VALUES (?, ?, ?, ?)",
            (command, datetime.now(timezone.utc).isoformat(), feedback, category),
        )
        conn.commit()
    finally:
        conn.close()


def get_stats(command: str = None) -> dict:
    conn = _get_conn()
    try:
        if command:
            row = conn.execute(
                "SELECT COUNT(*) as total, SUM(success) as ok, SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) as fail, "
                "MAX(timestamp) as last_used FROM command_history WHERE command=?", (command,)
            ).fetchone()
            feedbacks = conn.execute(
                "SELECT feedback, category, timestamp FROM command_feedback WHERE command=? ORDER BY timestamp DESC LIMIT 10",
                (command,)
            ).fetchall()
            errors = conn.execute(
                "SELECT error_msg, timestamp FROM command_history WHERE command=? AND success=0 ORDER BY timestamp DESC LIMIT 5",
                (command,)
            ).fetchall()
            return {
                "command": command,
                "total_invocations": row["total"],
                "successes": row["ok"] or 0,
                "failures": row["fail"] or 0,
                "last_used": row["last_used"],
                "recent_feedback": [{"feedback": f["feedback"], "category": f["category"], "at": f["timestamp"]} for f in feedbacks],
                "recent_errors": [{"error": e["error_msg"], "at": e["timestamp"]} for e in errors],
            }
        else:
            rows = conn.execute(
                "SELECT command, COUNT(*) as total, SUM(success) as ok, "
                "SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) as fail, MAX(timestamp) as last_used "
                "FROM command_history GROUP BY command ORDER BY total DESC"
            ).fetchall()
            return {
                "commands": [
                    {"command": r["command"], "total": r["total"], "ok": r["ok"] or 0, "fail": r["fail"] or 0, "last_used": r["last_used"]}
                    for r in rows
                ]
            }
    finally:
        conn.close()


def get_improvement_data(command: str) -> dict:
    """Gather all data needed to suggest improvements for a command."""
    conn = _get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM command_history WHERE command=?", (command,)).fetchone()[0]
        fails = conn.execute(
            "SELECT error_msg, notes, timestamp FROM command_history WHERE command=? AND success=0 ORDER BY timestamp DESC LIMIT 10",
            (command,)
        ).fetchall()
        feedbacks = conn.execute(
            "SELECT feedback, category, timestamp FROM command_feedback WHERE command=? ORDER BY timestamp DESC LIMIT 20",
            (command,)
        ).fetchall()
        recent = conn.execute(
            "SELECT action, success, error_msg, notes, timestamp FROM command_history WHERE command=? ORDER BY timestamp DESC LIMIT 20",
            (command,)
        ).fetchall()
        return {
            "command": command,
            "total_invocations": total,
            "failure_rate": len(fails) / max(total, 1),
            "recent_failures": [{"error": f["error_msg"], "notes": f["notes"], "at": f["timestamp"]} for f in fails],
            "feedback": [{"text": f["feedback"], "category": f["category"], "at": f["timestamp"]} for f in feedbacks],
            "recent_activity": [
                {"action": r["action"], "success": bool(r["success"]), "error": r["error_msg"], "notes": r["notes"], "at": r["timestamp"]}
                for r in recent
            ],
        }
    finally:
        conn.close()
