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


def _get_patterns_version(lessons_dir: str = None) -> str:
    """Compute version hash of all lesson files."""
    from pathlib import Path
    lessons_path = Path(lessons_dir) if lessons_dir else Path(__file__).parent.parent / "lessons"
    if not lessons_path.exists():
        return "unknown"

    lesson_files = sorted(lessons_path.rglob("*.md"))
    hasher = hashlib.sha256()
    for lesson_file in lesson_files:
        try:
            hasher.update(str(lesson_file).encode())
            hasher.update(lesson_file.read_bytes())
        except (OSError, IOError):
            continue
    return hasher.hexdigest()[:16]


def init_cache_db():
    """Initialize scan cache tables."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS scan_cache (
            file_path TEXT PRIMARY KEY,
            file_hash TEXT NOT NULL,
            git_commit TEXT,
            patterns_version TEXT,
            violations_json TEXT,
            scanned_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_cache_commit ON scan_cache(git_commit);
        CREATE INDEX IF NOT EXISTS idx_cache_scanned ON scan_cache(scanned_at);
        CREATE INDEX IF NOT EXISTS idx_cache_patterns ON scan_cache(patterns_version);
    """)
    conn.close()


def get_cached_violations(file_path: str, current_hash: str, patterns_version: str = None) -> Optional[list]:
    """Get cached violations if file hasn't changed.

    Returns:
        List of violations if cache hit, None if cache miss
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        "SELECT file_hash, patterns_version, violations_json FROM scan_cache WHERE file_path = ?",
        (file_path,)
    ).fetchone()
    conn.close()

    if not row:
        return None

    if row["file_hash"] != current_hash:
        return None

    # Invalidate cache if patterns changed
    if patterns_version and row["patterns_version"] and row["patterns_version"] != patterns_version:
        return None

    try:
        return json.loads(row["violations_json"])
    except json.JSONDecodeError:
        return None


def get_cached_violations_batch(file_paths: list[str], patterns_version: str = None) -> dict[str, Optional[list]]:
    """Get cached violations for multiple files in one query.

    Args:
        file_paths: List of file paths to check
        patterns_version: Current patterns version for cache invalidation

    Returns:
        Dict mapping file_path -> violations list (or None if cache miss)
    """
    if not file_paths:
        return {}

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # Batch query with IN clause - only fetch files that have cache entries
    placeholders = ",".join("?" * len(file_paths))
    rows = conn.execute(
        f"SELECT file_path, file_hash, patterns_version, violations_json FROM scan_cache WHERE file_path IN ({placeholders})",
        file_paths
    ).fetchall()
    conn.close()

    # Only compute hashes for files that have cache entries
    cached_data = {row["file_path"]: row for row in rows}

    # Build result dict
    result = {}
    for file_path in file_paths:
        row = cached_data.get(file_path)
        if not row:
            # No cache entry - mark as miss
            result[file_path] = None
            continue

        # Compute hash only for this cached file
        current_hash = _get_file_hash(file_path)

        # Check hash match
        if row["file_hash"] != current_hash:
            result[file_path] = None
            continue

        # Check patterns version
        if patterns_version and row["patterns_version"] and row["patterns_version"] != patterns_version:
            result[file_path] = None
            continue

        # Parse violations
        try:
            result[file_path] = json.loads(row["violations_json"])
        except json.JSONDecodeError:
            result[file_path] = None

    return result


def cache_violations(file_path: str, file_hash: str, violations: list, git_commit: Optional[str] = None, patterns_version: str = None):
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
        (file_path, file_hash, git_commit, patterns_version, violations_json, scanned_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        file_path,
        file_hash,
        git_commit,
        patterns_version,
        violations_json,
        datetime.now(timezone.utc).isoformat(),
    ))
    conn.commit()
    conn.close()


def cache_violations_batch(file_violations: dict[str, list], git_commit: Optional[str] = None, patterns_version: str = None):
    """Cache scan results for multiple files in one transaction.

    Args:
        file_violations: Dict mapping file_path -> list of violations
        git_commit: Current git commit hash
        patterns_version: Current patterns version
    """
    from datetime import datetime, timezone

    if not file_violations:
        return

    conn = sqlite3.connect(str(DB_PATH))
    timestamp = datetime.now(timezone.utc).isoformat()

    rows = []
    for file_path, violations in file_violations.items():
        file_hash = _get_file_hash(file_path)
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
        rows.append((file_path, file_hash, git_commit, patterns_version, violations_json, timestamp))

    conn.executemany("""
        INSERT OR REPLACE INTO scan_cache
        (file_path, file_hash, git_commit, patterns_version, violations_json, scanned_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, rows)
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


def is_cache_empty() -> bool:
    """Check if cache has any entries."""
    conn = sqlite3.connect(str(DB_PATH))
    count = conn.execute("SELECT COUNT(*) FROM scan_cache").fetchone()[0]
    conn.close()
    return count == 0