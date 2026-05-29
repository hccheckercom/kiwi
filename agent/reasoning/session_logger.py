"""Session Logger — captures tool calls into SQLite for learning."""

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "memory" / "reasoning.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"
SESSION_FILE = Path(__file__).parent.parent.parent / "memory" / ".current_session_id"

_session_id = None
_session_id_set_at = 0.0
_SESSION_ID_TTL = 14400  # 4 hours — match file-based TTL on disk
_conn = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        try:
            _conn.execute("SELECT 1")
            return _conn
        except sqlite3.Error:
            _conn = None

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(str(DB_PATH), timeout=5)
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA busy_timeout=3000")

    if not _table_exists(_conn, "session_log"):
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        _conn.executescript(schema)
    else:
        _migrate(_conn)

    return _conn


def _migrate(conn: sqlite3.Connection):
    """Auto-create tables added in later phases (R3+)."""
    if not _table_exists(conn, "calibration_events"):
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS calibration_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                task_type TEXT NOT NULL,
                signals TEXT,
                trust_before REAL,
                trust_after REAL,
                delta REAL,
                reason TEXT,
                created_at REAL
            );
            CREATE TABLE IF NOT EXISTS brief_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL UNIQUE,
                task_type TEXT NOT NULL,
                files_needed TEXT,
                trust_score REAL,
                recommendation TEXT,
                created_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_ce_session ON calibration_events(session_id);
            CREATE INDEX IF NOT EXISTS idx_ce_task ON calibration_events(task_type);
            CREATE INDEX IF NOT EXISTS idx_bl_session ON brief_log(session_id);
        """)

    # R5: Add layout_hash column to cross_theme_patterns
    if _table_exists(conn, "cross_theme_patterns"):
        cols = [r[1] for r in conn.execute("PRAGMA table_info(cross_theme_patterns)").fetchall()]
        if "layout_hash" not in cols:
            conn.execute("ALTER TABLE cross_theme_patterns ADD COLUMN layout_hash TEXT NOT NULL DEFAULT ''")
            conn.execute("DROP INDEX IF EXISTS idx_ctp_task")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ctp_task_hash ON cross_theme_patterns(task_type, layout_hash)")
            conn.commit()

    # R5: Auto-promote pipeline table
    if not _table_exists(conn, "promotion_suggestions"):
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS promotion_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern TEXT NOT NULL,
                pattern_type TEXT NOT NULL,
                category TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'SUGGEST',
                theme TEXT,
                task_type TEXT,
                times_seen INTEGER DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_ps_status ON promotion_suggestions(status);
        """)

    # R6: Draft outcome tracking for graduated autonomy
    if not _table_exists(conn, "draft_outcomes"):
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS draft_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                task_type TEXT NOT NULL,
                level TEXT NOT NULL,
                outcome TEXT NOT NULL,
                changes_made INTEGER DEFAULT 0,
                created_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_do_task ON draft_outcomes(task_type, level);
        """)

    # R7: Output quality metrics columns
    if _table_exists(conn, "output_quality"):
        cols = [r[1] for r in conn.execute("PRAGMA table_info(output_quality)").fetchall()]
        if "brief_level" not in cols:
            conn.execute("ALTER TABLE output_quality ADD COLUMN brief_level INTEGER DEFAULT 0")
            conn.execute("ALTER TABLE output_quality ADD COLUMN autonomy_level TEXT DEFAULT 'none'")
            conn.execute("ALTER TABLE output_quality ADD COLUMN draft_outcome TEXT")
            conn.execute("ALTER TABLE output_quality ADD COLUMN session_duration_sec REAL DEFAULT 0")

    # R8: Selective Thinking tables
    if not _table_exists(conn, "think_events"):
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS think_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                trigger TEXT NOT NULL,
                task_type TEXT,
                theme TEXT,
                decision TEXT,
                confidence REAL,
                tokens_used INTEGER DEFAULT 0,
                cached INTEGER DEFAULT 0,
                success INTEGER DEFAULT NULL,
                created_at REAL
            );
            CREATE TABLE IF NOT EXISTS think_cache (
                cache_key TEXT PRIMARY KEY,
                trigger TEXT NOT NULL,
                task_type TEXT,
                theme TEXT,
                decision TEXT NOT NULL,
                reasoning TEXT,
                confidence REAL DEFAULT 0.5,
                extra TEXT,
                created_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_te_session ON think_events(session_id);
            CREATE INDEX IF NOT EXISTS idx_te_trigger ON think_events(trigger);
            CREATE INDEX IF NOT EXISTS idx_tc_trigger ON think_cache(trigger);
        """)


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def get_session_id() -> str:
    """Get or create session ID. Persists via file so all hook subprocesses share it.

    Cached `_session_id` expires after `_SESSION_ID_TTL` seconds (4h) so a long-lived
    Python process (e.g. MCP server) does not keep using a stale id from an old session.
    """
    global _session_id, _session_id_set_at
    now = time.time()
    if _session_id is not None and (now - _session_id_set_at) < _SESSION_ID_TTL:
        return _session_id
    if _session_id is not None:
        # cache expired — drop it so we re-resolve from env/file/new
        _session_id = None

    # Priority 1: env var from Claude Code
    conv_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "") or os.environ.get("CLAUDE_CONVERSATION_ID", "")
    if conv_id:
        _session_id = conv_id[:12]
        _session_id_set_at = now
        _ensure_session_file(_session_id)
        _init_session()
        return _session_id

    # Priority 2: read from file (shared across subprocesses)
    if SESSION_FILE.exists():
        try:
            data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
            file_sid = data.get("session_id", "")
            created_at = data.get("created_at", 0)
            # Session expires after 4 hours of inactivity
            if file_sid and (now - created_at) < _SESSION_ID_TTL:
                _session_id = file_sid
                _session_id_set_at = now
                # Update last_active
                data["last_active"] = now
                SESSION_FILE.write_text(json.dumps(data), encoding="utf-8")
                _init_session()
                return _session_id
        except (json.JSONDecodeError, OSError):
            pass

    # Priority 3: create new session
    _session_id = uuid.uuid4().hex[:8]
    _session_id_set_at = now
    _ensure_session_file(_session_id)
    _init_session()
    return _session_id


def _ensure_session_file(sid: str):
    """Write session ID to file for cross-subprocess sharing."""
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "session_id": sid,
        "created_at": time.time(),
        "last_active": time.time(),
    }
    try:
        SESSION_FILE.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def _init_session():
    conn = _get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO sessions (session_id, started_at) VALUES (?, ?)",
        (get_session_id(), time.time()),
    )
    conn.commit()


def log_tool_call(tool: str, file_path: str = None, metadata: dict = None):
    """Log a tool call. ~1ms overhead."""
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO session_log (session_id, tool, file_path, action, metadata, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                get_session_id(),
                tool,
                file_path,
                _infer_action(tool),
                json.dumps(metadata, ensure_ascii=False) if metadata else None,
                time.time(),
            ),
        )

        if tool == "Read":
            conn.execute(
                "UPDATE sessions SET files_read = files_read + 1 WHERE session_id = ?",
                (get_session_id(),),
            )
        elif tool in ("Write", "Edit"):
            conn.execute(
                "UPDATE sessions SET files_written = files_written + 1 WHERE session_id = ?",
                (get_session_id(),),
            )

        conn.commit()
    except Exception:
        pass


def _infer_action(tool: str) -> str:
    return {
        "Read": "read",
        "Write": "write",
        "Edit": "edit",
        "Grep": "search",
        "Glob": "search",
        "Bash": "shell",
        "PowerShell": "shell",
    }.get(tool, "other")


def get_session_reads(session_id: str = None) -> list:
    sid = session_id or get_session_id()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT file_path, timestamp FROM session_log "
        "WHERE session_id = ? AND tool = 'Read' ORDER BY timestamp",
        (sid,),
    ).fetchall()
    return [{"file": r[0], "timestamp": r[1]} for r in rows]


def get_session_writes(session_id: str = None) -> list:
    sid = session_id or get_session_id()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT file_path, tool, timestamp FROM session_log "
        "WHERE session_id = ? AND tool IN ('Write', 'Edit') ORDER BY timestamp",
        (sid,),
    ).fetchall()
    return [{"file": r[0], "tool": r[1], "timestamp": r[2]} for r in rows]


def get_read_order_before_write(session_id: str, write_path: str) -> list:
    conn = _get_conn()
    write_time = conn.execute(
        "SELECT MIN(timestamp) FROM session_log "
        "WHERE session_id = ? AND file_path = ? AND tool IN ('Write', 'Edit')",
        (session_id, write_path),
    ).fetchone()[0]

    if not write_time:
        return []

    rows = conn.execute(
        "SELECT file_path FROM session_log "
        "WHERE session_id = ? AND tool = 'Read' AND timestamp < ? ORDER BY timestamp",
        (session_id, write_time),
    ).fetchall()
    return [r[0] for r in rows if r[0]]


def get_unprocessed_sessions(min_writes: int = 1) -> list:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT session_id, started_at, files_read, files_written, theme_path "
        "FROM sessions WHERE processed = 0 AND files_written >= ?",
        (min_writes,),
    ).fetchall()
    return [
        {
            "session_id": r[0],
            "started_at": r[1],
            "files_read": r[2],
            "files_written": r[3],
            "theme_path": r[4],
        }
        for r in rows
    ]


def mark_session_processed(session_id: str):
    conn = _get_conn()
    conn.execute(
        "UPDATE sessions SET processed = 1, ended_at = ? WHERE session_id = ?",
        (time.time(), session_id),
    )
    conn.commit()


def save_brief_output(session_id: str, brief):
    """Store brief output for later calibration by R3."""
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO brief_log "
        "(session_id, task_type, files_needed, trust_score, recommendation, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            session_id,
            brief.content.get("target", "generic"),
            json.dumps(brief.content.get("files_needed", []), ensure_ascii=False),
            brief.trust_score,
            brief.recommendation,
            time.time(),
        ),
    )
    conn.commit()


def get_brief_for_session(session_id: str) -> dict | None:
    """Retrieve stored brief for calibration."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT task_type, files_needed, trust_score, recommendation "
        "FROM brief_log WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "task_type": row[0],
        "files_needed": json.loads(row[1]) if row[1] else [],
        "trust_score": row[2],
        "recommendation": row[3],
    }


def get_session_log_entries(session_id: str) -> list[dict]:
    """Get all log entries for a session, ordered by timestamp."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT tool, file_path, action, metadata, timestamp FROM session_log "
        "WHERE session_id = ? ORDER BY timestamp",
        (session_id,),
    ).fetchall()
    return [
        {
            "tool": r[0],
            "file": r[1],
            "action": r[2],
            "metadata": json.loads(r[3]) if r[3] else {},
            "timestamp": r[4],
        }
        for r in rows
    ]