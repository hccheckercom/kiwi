"""Scan cache for incremental scanning."""

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "kiwi.db"


def _get_file_hash(file_path: str) -> str:
    """Calculate SHA256 hash of file content."""
    try:
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except (OSError, IOError):
        return ""


def _get_git_commit_hash(repo_path: str) -> Optional[str]:
    """Get current git commit hash."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=repo_path, timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def init_cache_db():
    """Initialize scan cache tables."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS scan_cache (
            file_path TEXT PRIMARY KEY,
            file_hash TEXT NOT NULL,
            git_commit TEXT,
            violations_json TEXT,
            scanned_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_cache_commit ON scan_cache(git_commit);
        CREATE INDEX IF NOT EXISTS idx_cache_scanned ON scan_cache(scanned_at);
    """)
    conn.close()


def get_cached_violations(file_path: str, current_hash: str) -> Optional[list]:
    """Get cached violations if file hasn't changed.

    Returns:
        List of violations if cache hit, None if cache miss
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        "SELECT file_hash, violations_json FROM scan_cache WHERE file_path = ?",
        (file_path,)
    ).fetchone()
    conn.close()

    if not row:
        return None

    if row["file_hash"] != current_hash:
        return None

    try:
        return json.loads(row["violations_json"])
    except json.JSONDecodeError:
        return None


def cache_violations(file_path: str, file_hash: str, violations: list, git_commit: Optional[str] = None):
    """Cache scan results for a file."""
    from datetime import datetime, timezone

    violations_json = json.dumps([
        {
            "lesson_id": v.lesson_id,
            "severity": v.severity,
            "category": v.category,
            "description": v.description,
            "file": v.file,
            "line": v.line,
            "match_text": getattr(v, "match_text", ""),
        }
        for v in violations
    ])

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        INSERT OR REPLACE INTO scan_cache
        (file_path, file_hash, git_commit, violations_json, scanned_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        file_path,
        file_hash,
        git_commit,
        violations_json,
        datetime.now(timezone.utc).isoformat(),
    ))
    conn.commit()
    conn.close()


def clear_cache(older_than_days: int = 30):
    """Clear old cache entries."""
    from datetime import datetime, timedelta, timezone

    cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DELETE FROM scan_cache WHERE scanned_at < ?", (cutoff,))
    conn.commit()
    conn.close()


def get_cache_stats() -> dict:
    """Get cache statistics."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    row = conn.execute("""
        SELECT
            COUNT(*) as total_entries,
            COUNT(DISTINCT git_commit) as unique_commits,
            MAX(scanned_at) as last_scan
        FROM scan_cache
    """).fetchone()
    conn.close()

    return dict(row) if row else {}