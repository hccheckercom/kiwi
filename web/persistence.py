"""SQLite persistence layer for Kiwi web dashboard."""

import sys
from datetime import datetime
from pathlib import Path

KIWI_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(KIWI_DIR))

from memory.db import get_connection


def save_approval(checkpoint_id: str, decision: str, comment: str, user: str):
    """Save approval decision to database."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO approvals
            (checkpoint_id, decision, comment, user, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (checkpoint_id, decision, comment, user, datetime.utcnow().isoformat()))
        conn.commit()
    finally:
        conn.close()


def get_approval(checkpoint_id: str):
    """Get approval decision from database."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT decision, comment, user, timestamp
            FROM approvals
            WHERE checkpoint_id = ?
        """, (checkpoint_id,))
        row = cursor.fetchone()
        if row:
            return {
                "decision": row[0],
                "comment": row[1],
                "user": row[2],
                "timestamp": row[3]
            }
        return None
    finally:
        conn.close()


def save_scan_history(project_path: str, report):
    """Save scan results to history for trends."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO scan_history
            (path, timestamp, violations_critical, violations_high, violations_suggest,
             files_scanned, patterns_checked)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            project_path,
            datetime.utcnow().isoformat(),
            report.critical_count,
            report.high_count,
            report.suggest_count,
            report.files_scanned,
            report.patterns_checked
        ))
        conn.commit()
    finally:
        conn.close()


def get_scan_trends(project_path: str, days: int = 30):
    """Get scan history for trends visualization."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, violations_critical, violations_high, violations_suggest
            FROM scan_history
            WHERE path = ?
            AND datetime(timestamp) >= datetime('now', '-' || ? || ' days')
            ORDER BY timestamp ASC
        """, (project_path, days))

        rows = cursor.fetchall()
        return [
            {
                "timestamp": row[0],
                "critical": row[1],
                "high": row[2],
                "suggest": row[3]
            }
            for row in rows
        ]
    finally:
        conn.close()


def save_agent_run(run_id: str, project_path: str, severity: str):
    """Create new agent run record."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO agent_runs
            (run_id, status, project_path, severity, started_at)
            VALUES (?, ?, ?, ?, ?)
        """, (run_id, "running", project_path, severity, datetime.utcnow().isoformat()))
        conn.commit()
    finally:
        conn.close()


def update_agent_run(run_id: str, status: str, violations_found: int = 0,
                     fixes_applied: int = 0, error: str = None):
    """Update agent run status."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        if status in ["completed", "failed"]:
            cursor.execute("""
                UPDATE agent_runs
                SET status = ?, violations_found = ?, fixes_applied = ?,
                    error = ?, completed_at = ?
                WHERE run_id = ?
            """, (status, violations_found, fixes_applied, error,
                  datetime.utcnow().isoformat(), run_id))
        else:
            cursor.execute("""
                UPDATE agent_runs
                SET status = ?, violations_found = ?, fixes_applied = ?
                WHERE run_id = ?
            """, (status, violations_found, fixes_applied, run_id))

        conn.commit()
    finally:
        conn.close()


def get_agent_runs(project_path: str = None, limit: int = 50):
    """Get agent run history."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        if project_path:
            cursor.execute("""
                SELECT run_id, status, project_path, severity, violations_found,
                       fixes_applied, started_at, completed_at, error
                FROM agent_runs
                WHERE project_path = ?
                ORDER BY started_at DESC
                LIMIT ?
            """, (project_path, limit))
        else:
            cursor.execute("""
                SELECT run_id, status, project_path, severity, violations_found,
                       fixes_applied, started_at, completed_at, error
                FROM agent_runs
                ORDER BY started_at DESC
                LIMIT ?
            """, (limit,))

        rows = cursor.fetchall()
        return [
            {
                "run_id": row[0],
                "status": row[1],
                "project_path": row[2],
                "severity": row[3],
                "violations_found": row[4],
                "fixes_applied": row[5],
                "started_at": row[6],
                "completed_at": row[7],
                "error": row[8]
            }
            for row in rows
        ]
    finally:
        conn.close()
