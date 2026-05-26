"""Deployment state tracking — cache git commits, scan results, deploy history."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

KIWI_DIR = Path(__file__).parent.parent
DB_PATH = KIWI_DIR / "kiwi.db"


def get_connection():
    """Get SQLite connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_deploy_tables():
    """Initialize deployment tables in kiwi.db."""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS deploy_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_path TEXT NOT NULL,
                deploy_type TEXT NOT NULL,
                target TEXT NOT NULL,
                git_commit TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                duration_ms INTEGER DEFAULT 0,
                success BOOLEAN DEFAULT 1,
                error_pattern TEXT,
                rollback BOOLEAN DEFAULT 0,
                backup_path TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_deploy_path ON deploy_history(project_path);
            CREATE INDEX IF NOT EXISTS idx_deploy_time ON deploy_history(timestamp);

            CREATE TABLE IF NOT EXISTS deploy_cache (
                project_path TEXT PRIMARY KEY,
                last_git_commit TEXT NOT NULL,
                last_scan_result TEXT,
                last_deploy_timestamp TEXT,
                cache_valid BOOLEAN DEFAULT 1
            );
        """)
        conn.commit()
    finally:
        conn.close()


def _now():
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def log_deploy(
    project_path: str,
    deploy_type: str,
    target: str,
    git_commit: str,
    success: bool,
    duration_ms: int,
    error_pattern: str = None,
    rollback: bool = False,
    backup_path: str = None,
):
    """Log deployment to history."""
    init_deploy_tables()
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO deploy_history
            (project_path, deploy_type, target, git_commit, timestamp, duration_ms, success, error_pattern, rollback, backup_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project_path,
            deploy_type,
            target,
            git_commit,
            _now(),
            duration_ms,
            success,
            error_pattern,
            rollback,
            backup_path,
        ))
        conn.commit()

        # Update cache
        if success:
            update_cache(project_path, git_commit, None)
    finally:
        conn.close()


def get_cache(project_path: str) -> Optional[Dict]:
    """Get cached deployment state."""
    init_deploy_tables()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM deploy_cache WHERE project_path = ? AND cache_valid = 1",
            (project_path,)
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return None

    result = dict(row)
    if result.get("last_scan_result"):
        try:
            result["last_scan_result"] = json.loads(result["last_scan_result"])
        except json.JSONDecodeError:
            result["last_scan_result"] = None

    return result


def update_cache(project_path: str, git_commit: str, scan_result: Optional[Dict]):
    """Update deployment cache."""
    init_deploy_tables()
    conn = get_connection()
    try:
        scan_json = json.dumps(scan_result) if scan_result else None

        conn.execute("""
            INSERT INTO deploy_cache (project_path, last_git_commit, last_scan_result, last_deploy_timestamp, cache_valid)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(project_path) DO UPDATE SET
                last_git_commit = excluded.last_git_commit,
                last_scan_result = excluded.last_scan_result,
                last_deploy_timestamp = excluded.last_deploy_timestamp,
                cache_valid = 1
        """, (project_path, git_commit, scan_json, _now()))

        conn.commit()
    finally:
        conn.close()


def invalidate_cache(project_path: str):
    """Invalidate deployment cache."""
    init_deploy_tables()
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE deploy_cache SET cache_valid = 0 WHERE project_path = ?",
            (project_path,)
        )
        conn.commit()
    finally:
        conn.close()


def should_rescan(project_path: str, current_commit: str) -> bool:
    """Check if rescan is needed based on git commit."""
    cache = get_cache(project_path)
    if not cache:
        return True
    return cache["last_git_commit"] != current_commit


def get_deploy_history(project_path: str = None, limit: int = 10) -> list:
    """Get deployment history."""
    init_deploy_tables()
    conn = get_connection()
    try:
        if project_path:
            rows = conn.execute(
                "SELECT * FROM deploy_history WHERE project_path = ? ORDER BY timestamp DESC LIMIT ?",
                (project_path, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM deploy_history ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def get_deploy_stats(project_path: str) -> Dict:
    """Get deployment statistics."""
    init_deploy_tables()
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT
                COUNT(*) as total_deploys,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_deploys,
                SUM(CASE WHEN rollback = 1 THEN 1 ELSE 0 END) as rollbacks,
                AVG(duration_ms) as avg_duration_ms,
                MAX(timestamp) as last_deploy
            FROM deploy_history
            WHERE project_path = ?
        """, (project_path,)).fetchone()
    finally:
        conn.close()

    if not row or row["total_deploys"] == 0:
        return {
            "total_deploys": 0,
            "successful_deploys": 0,
            "rollbacks": 0,
            "avg_duration_ms": 0,
            "last_deploy": None,
            "success_rate": 0.0,
        }

    return {
        "total_deploys": row["total_deploys"],
        "successful_deploys": row["successful_deploys"],
        "rollbacks": row["rollbacks"],
        "avg_duration_ms": int(row["avg_duration_ms"]) if row["avg_duration_ms"] else 0,
        "last_deploy": row["last_deploy"],
        "success_rate": row["successful_deploys"] / row["total_deploys"] if row["total_deploys"] > 0 else 0.0,
    }
