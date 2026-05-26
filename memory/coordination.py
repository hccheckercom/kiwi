"""Multi-agent coordination state management."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .db import get_connection, _now

COORDINATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    mode TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT DEFAULT 'pending',
    checkpoint_data TEXT,
    parent_run_id INTEGER,
    agent_type TEXT,
    FOREIGN KEY (parent_run_id) REFERENCES agent_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_path ON agent_runs(path);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status);
CREATE INDEX IF NOT EXISTS idx_agent_runs_parent ON agent_runs(parent_run_id);

CREATE TABLE IF NOT EXISTS agent_consensus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id TEXT NOT NULL,
    file TEXT NOT NULL,
    line INTEGER DEFAULT 0,
    agent_run_id INTEGER NOT NULL,
    agent_type TEXT NOT NULL,
    verdict TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    reasoning TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (agent_run_id) REFERENCES agent_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_consensus_lesson ON agent_consensus(lesson_id);
CREATE INDEX IF NOT EXISTS idx_consensus_file ON agent_consensus(file);
CREATE INDEX IF NOT EXISTS idx_consensus_run ON agent_consensus(agent_run_id);

CREATE TABLE IF NOT EXISTS agent_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent_id INTEGER NOT NULL,
    to_agent_id INTEGER,
    message_type TEXT NOT NULL,
    payload TEXT,
    created_at TEXT NOT NULL,
    processed BOOLEAN DEFAULT 0,
    FOREIGN KEY (from_agent_id) REFERENCES agent_runs(id),
    FOREIGN KEY (to_agent_id) REFERENCES agent_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_messages_to ON agent_messages(to_agent_id, processed);
CREATE INDEX IF NOT EXISTS idx_messages_from ON agent_messages(from_agent_id);
"""


def init_coordination_db():
    """Initialize coordination tables."""
    conn = get_connection()
    try:
        conn.executescript(COORDINATION_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def create_agent_run(path: str, mode: str = "review", agent_type: str = "general",
                     parent_run_id: Optional[int] = None) -> int:
    """Create new agent run record."""
    conn = get_connection()
    try:
        cursor = conn.execute("""
            INSERT INTO agent_runs (path, mode, started_at, status, agent_type, parent_run_id)
            VALUES (?, ?, ?, 'pending', ?, ?)
        """, (path, mode, _now(), agent_type, parent_run_id))
        run_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    return run_id


def update_agent_run(run_id: int, status: str = None, checkpoint_data: dict = None):
    """Update agent run status and checkpoint data."""
    conn = get_connection()
    try:

        updates = []
        params = []

        if status:
            updates.append("status = ?")
            params.append(status)

            if status in ("completed", "failed"):
                updates.append("completed_at = ?")
                params.append(_now())

        if checkpoint_data is not None:
            updates.append("checkpoint_data = ?")
            params.append(json.dumps(checkpoint_data))

        if updates:
            params.append(run_id)
            conn.execute(f"""
                UPDATE agent_runs
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)
            conn.commit()

    finally:
        conn.close()


def get_agent_run(run_id: int) -> Optional[dict]:
    """Get agent run by ID."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
    finally:
        conn.close()

    if not row:
        return None

    result = dict(row)
    if result.get("checkpoint_data"):
        result["checkpoint_data"] = json.loads(result["checkpoint_data"])
    return result


def get_active_runs(path: str = None) -> list[dict]:
    """Get all active (pending/checkpoint_waiting) agent runs."""
    conn = get_connection()
    try:

        if path:
            rows = conn.execute("""
                SELECT * FROM agent_runs
                WHERE path = ? AND status IN ('pending', 'checkpoint_waiting')
                ORDER BY started_at DESC
            """, (path,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM agent_runs
                WHERE status IN ('pending', 'checkpoint_waiting')
                ORDER BY started_at DESC
            """).fetchall()

    finally:
        conn.close()

    results = []
    for row in rows:
        result = dict(row)
        if result.get("checkpoint_data"):
            result["checkpoint_data"] = json.loads(result["checkpoint_data"])
        results.append(result)

    return results


def get_child_runs(parent_run_id: int) -> list[dict]:
    """Get all child agent runs for a parent run."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM agent_runs
            WHERE parent_run_id = ?
            ORDER BY started_at ASC
        """, (parent_run_id,)).fetchall()
    finally:
        conn.close()

    results = []
    for row in rows:
        result = dict(row)
        if result.get("checkpoint_data"):
            result["checkpoint_data"] = json.loads(result["checkpoint_data"])
        results.append(result)

    return results


def record_verdict(run_id: int, agent_type: str, lesson_id: str, file: str,
                   line: int, verdict: str, confidence: float = 1.0,
                   reasoning: str = "") -> int:
    """Record agent verdict on a violation."""
    conn = get_connection()
    try:
        cursor = conn.execute("""
            INSERT INTO agent_consensus
            (agent_run_id, agent_type, lesson_id, file, line, verdict, confidence, reasoning, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (run_id, agent_type, lesson_id, file, line, verdict, confidence, reasoning, _now()))
        verdict_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    return verdict_id


def get_verdicts(lesson_id: str, file: str, line: int = None) -> list[dict]:
    """Get all agent verdicts for a specific violation."""
    conn = get_connection()
    try:

        if line is not None:
            rows = conn.execute("""
                SELECT ac.*, ar.agent_type as run_agent_type, ar.mode
                FROM agent_consensus ac
                JOIN agent_runs ar ON ac.agent_run_id = ar.id
                WHERE ac.lesson_id = ? AND ac.file = ? AND ac.line = ?
                ORDER BY ac.created_at DESC
            """, (lesson_id, file, line)).fetchall()
        else:
            rows = conn.execute("""
                SELECT ac.*, ar.agent_type as run_agent_type, ar.mode
                FROM agent_consensus ac
                JOIN agent_runs ar ON ac.agent_run_id = ar.id
                WHERE ac.lesson_id = ? AND ac.file = ?
                ORDER BY ac.created_at DESC
            """, (lesson_id, file)).fetchall()

    finally:
        conn.close()
    return [dict(r) for r in rows]


def calculate_consensus(lesson_id: str, file: str, line: int = None) -> dict:
    """Calculate consensus score for a violation across all agent verdicts."""
    verdicts = get_verdicts(lesson_id, file, line)

    if not verdicts:
        return {
            "consensus": "unknown",
            "confidence": 0.0,
            "agent_count": 0,
            "verdicts": []
        }

    verdict_counts = {}
    total_confidence = 0.0

    for v in verdicts:
        verdict = v["verdict"]
        confidence = v["confidence"]

        if verdict not in verdict_counts:
            verdict_counts[verdict] = {"count": 0, "confidence_sum": 0.0}

        verdict_counts[verdict]["count"] += 1
        verdict_counts[verdict]["confidence_sum"] += confidence
        total_confidence += confidence

    majority_verdict = max(verdict_counts.items(), key=lambda x: (x[1]["count"], x[1]["confidence_sum"]))
    majority_count = majority_verdict[1]["count"]
    total_count = len(verdicts)

    consensus_score = (majority_count / total_count) * (majority_verdict[1]["confidence_sum"] / majority_count)

    return {
        "consensus": majority_verdict[0],
        "confidence": round(consensus_score, 2),
        "agent_count": total_count,
        "verdicts": verdict_counts,
        "needs_human": consensus_score < 0.7 or (total_count > 1 and majority_count == 1)
    }


def send_message(from_run_id: int, to_run_id: Optional[int], message_type: str,
                 payload: dict = None) -> int:
    """Send message between agents."""
    conn = get_connection()
    try:
        cursor = conn.execute("""
            INSERT INTO agent_messages (from_agent_id, to_agent_id, message_type, payload, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (from_run_id, to_run_id, message_type, json.dumps(payload) if payload else None, _now()))
        message_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    return message_id


def get_messages(to_run_id: int, unprocessed_only: bool = True) -> list[dict]:
    """Get messages for an agent."""
    conn = get_connection()
    try:

        if unprocessed_only:
            rows = conn.execute("""
                SELECT * FROM agent_messages
                WHERE to_agent_id = ? AND processed = 0
                ORDER BY created_at ASC
            """, (to_run_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM agent_messages
                WHERE to_agent_id = ?
                ORDER BY created_at DESC
                LIMIT 50
            """, (to_run_id,)).fetchall()

    finally:
        conn.close()

    results = []
    for row in rows:
        result = dict(row)
        if result.get("payload"):
            result["payload"] = json.loads(result["payload"])
        results.append(result)

    return results


def mark_message_processed(message_id: int):
    """Mark message as processed."""
    conn = get_connection()
    try:
        conn.execute("UPDATE agent_messages SET processed = 1 WHERE id = ?", (message_id,))
        conn.commit()
    finally:
        conn.close()


def get_coordination_stats(path: str = None) -> dict:
    """Get coordination statistics."""
    conn = get_connection()
    try:

        if path:
            total_runs = conn.execute(
                "SELECT COUNT(*) FROM agent_runs WHERE path = ?", (path,)
            ).fetchone()[0]

            active_runs = conn.execute(
                "SELECT COUNT(*) FROM agent_runs WHERE path = ? AND status IN ('pending', 'checkpoint_waiting')",
                (path,)
            ).fetchone()[0]

            total_verdicts = conn.execute(
                "SELECT COUNT(*) FROM agent_consensus ac JOIN agent_runs ar ON ac.agent_run_id = ar.id WHERE ar.path = ?",
                (path,)
            ).fetchone()[0]
        else:
            total_runs = conn.execute("SELECT COUNT(*) FROM agent_runs").fetchone()[0]
            active_runs = conn.execute(
                "SELECT COUNT(*) FROM agent_runs WHERE status IN ('pending', 'checkpoint_waiting')"
            ).fetchone()[0]
            total_verdicts = conn.execute("SELECT COUNT(*) FROM agent_consensus").fetchone()[0]

        unprocessed_messages = conn.execute(
            "SELECT COUNT(*) FROM agent_messages WHERE processed = 0"
        ).fetchone()[0]

    finally:
        conn.close()

    return {
        "total_runs": total_runs,
        "active_runs": active_runs,
        "total_verdicts": total_verdicts,
        "unprocessed_messages": unprocessed_messages
    }
