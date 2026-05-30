"""Compute learning health snapshot for the kiwi_learning_health MCP tool.

Reads only — never mutates DB. Safe to call at any frequency.
"""

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

KIWI_DIR = Path(__file__).resolve().parent.parent
DB_PATH = KIWI_DIR / "memory" / "reasoning.db"
KIWI_DB_PATH = KIWI_DIR / "kiwi.db"


def _kiwi_db_counts() -> dict:
    """Counts from kiwi.db/suggested_lessons (the bug-pattern suggestion table).

    Health historically read only reasoning.db/promotion_suggestions, so it
    reported total_suggestions_promoted=0 even when suggested_lessons had real
    approved lessons (LES-545…). Surfacing both tables removes that blind spot.
    """
    out = {
        "lesson_suggestions_pending": 0,
        "lesson_suggestions_approved": 0,
        "lesson_suggestions_auto_approved": 0,
    }
    if not KIWI_DB_PATH.exists():
        return out
    try:
        kconn = sqlite3.connect(str(KIWI_DB_PATH))
        try:
            out["lesson_suggestions_pending"] = _count(kconn, "suggested_lessons", "status='pending'")
            out["lesson_suggestions_approved"] = _count(kconn, "suggested_lessons", "status='approved'")
            out["lesson_suggestions_auto_approved"] = _count(kconn, "suggested_lessons", "status='auto_approved'")
        finally:
            kconn.close()
    except sqlite3.Error:
        pass
    return out


def _count(conn: sqlite3.Connection, table: str, where: str = "") -> int:
    q = f"SELECT COUNT(*) FROM {table}"
    if where:
        q += f" WHERE {where}"
    try:
        return conn.execute(q).fetchone()[0]
    except sqlite3.Error:
        return 0


def _last_ts(conn: sqlite3.Connection, table: str, col: str, where: str = "") -> str | None:
    q = f"SELECT MAX({col}) FROM {table}"
    if where:
        q += f" WHERE {where}"
    try:
        ts = conn.execute(q).fetchone()[0]
        if ts is None:
            return None
        if isinstance(ts, (int, float)):
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
        return str(ts)
    except sqlite3.Error:
        return None


def _learning_disabled() -> bool:
    flag = os.environ.get("KIWI_LEARNING_DISABLED", "").strip().lower()
    if flag in ("1", "true", "yes"):
        return True
    return (KIWI_DIR / "memory" / ".learning_disabled").exists()


def get_health() -> dict:
    if not DB_PATH.exists():
        return {
            "status": "stalled",
            "reason": "no_db",
            "db_path": str(DB_PATH),
            "learning_disabled": _learning_disabled(),
        }

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        stats = {
            "total_sessions": _count(conn, "sessions"),
            "total_writes_logged": _count(conn, "session_log", "tool IN ('Write','Edit')"),
            "total_bindings_learned": _count(conn, "binding_knowledge"),
            "total_styles_learned": _count(conn, "style_knowledge"),
            "total_context_patterns": _count(conn, "context_patterns"),
            "total_suggestions_pending": _count(conn, "promotion_suggestions", "status='pending'"),
            "total_suggestions_promoted": _count(conn, "promotion_suggestions", "status='approved'"),
            "total_blessed_conventions": (
                _count(conn, "binding_knowledge", "blessed=1")
                + _count(conn, "style_knowledge", "blessed=1")
            ),
            "last_session_at": _last_ts(conn, "sessions", "started_at"),
            "last_promotion_at": _last_ts(
                conn, "promotion_suggestions", "approved_at", "status='approved'"
            ),
        }
        # Surface the OTHER suggestion table (kiwi.db/suggested_lessons) so the
        # snapshot isn't blind to lessons that were actually promoted there.
        stats.update(_kiwi_db_counts())

        fail_counts: dict[str, int] = {}
        try:
            # fail_count is monotonic (never reset), so a counter whose last
            # failure is >7 days old is almost always a bug that's since been
            # fixed — reporting it as a live failure is misleading. Filter it
            # out of the snapshot (read-only; we never mutate here).
            stale_cutoff = time.time() - 86400 * 7
            for row in conn.execute(
                "SELECT stage, fail_count, last_failure_at FROM learning_health"
            ):
                last_at = row["last_failure_at"]
                if last_at and last_at < stale_cutoff:
                    continue
                fail_counts[row["stage"]] = row["fail_count"]
        except sqlite3.Error:
            pass

        learning_disabled = _learning_disabled()

        themes: list[str] = []
        try:
            themes = [
                r[0]
                for r in conn.execute(
                    "SELECT DISTINCT theme FROM binding_knowledge "
                    "WHERE theme IS NOT NULL AND theme NOT IN ('','unknown')"
                ).fetchall()
                if r[0]
            ]
        except sqlite3.Error:
            pass

        top_bindings: list[dict] = []
        try:
            top_bindings = [
                {"binding": r[0], "times_seen": r[1]}
                for r in conn.execute(
                    "SELECT binding, SUM(times_seen) FROM binding_knowledge "
                    "GROUP BY binding ORDER BY 2 DESC LIMIT 10"
                ).fetchall()
            ]
        except sqlite3.Error:
            pass

        recent_sessions = 0
        try:
            recent_sessions = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE started_at > ?",
                (time.time() - 86400 * 7,),
            ).fetchone()[0]
        except sqlite3.Error:
            pass

        if learning_disabled:
            status = "disabled"
        elif sum(fail_counts.values()) > 50:
            status = "degraded"
        elif recent_sessions == 0 and stats["total_sessions"] > 0:
            status = "stalled"
        elif stats["total_sessions"] == 0:
            status = "stalled"
        else:
            status = "healthy"

        stale_sessions = 0
        try:
            stale_sessions = conn.execute(
                "SELECT COUNT(*) FROM sessions "
                "WHERE processed = 0 AND started_at < ?",
                (time.time() - 86400 * 7,),
            ).fetchone()[0]
        except sqlite3.Error:
            pass

        return {
            "status": status,
            "stats": stats,
            "health_signals": {
                "learning_disabled": learning_disabled,
                "fail_counts": fail_counts,
                "stale_sessions": stale_sessions,
                "recent_sessions_7d": recent_sessions,
                "db_size_mb": round(DB_PATH.stat().st_size / 1024 / 1024, 2),
            },
            "themes_learned": themes,
            "top_bindings": top_bindings,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(get_health(), indent=2, ensure_ascii=False))