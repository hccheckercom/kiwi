"""R4 — Novel Pattern Detector: find patterns Claude uses that Kiwi doesn't know."""

import time

from .session_logger import _get_conn

MAX_NOVEL_PATTERNS = 200


def _log_err(stage: str, exc: BaseException) -> None:
    """Record failure in learning_health so silent breakage is visible."""
    try:
        conn = _get_conn()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS learning_health ("
            "stage TEXT PRIMARY KEY, fail_count INTEGER DEFAULT 0, "
            "last_failure_at REAL, last_error TEXT)"
        )
        conn.execute(
            "INSERT INTO learning_health (stage, fail_count, last_failure_at, last_error) "
            "VALUES (?, 1, ?, ?) ON CONFLICT(stage) DO UPDATE SET "
            "fail_count = fail_count + 1, last_failure_at = excluded.last_failure_at, "
            "last_error = excluded.last_error",
            (f"novel_detector.{stage}", time.time(), f"{type(exc).__name__}: {exc}"[:500]),
        )
        conn.commit()
    except Exception:
        pass


def detect_novel_bindings(session_bindings: list, task_type: str, theme: str) -> list:
    """Compare session bindings against known binding_knowledge. Return novel ones."""
    conn = _get_conn()
    if not conn:
        return []

    try:
        known_rows = conn.execute(
            "SELECT binding FROM binding_knowledge WHERE task_type = ? AND times_seen >= 3",
            (task_type,),
        ).fetchall()
        known = {r[0] for r in known_rows}
        return [b for b in session_bindings if b not in known]
    except Exception as e:
        _log_err("detect_novel_bindings", e)
        return []


def record_novel_pattern(pattern: str, pattern_type: str, theme: str,
                         task_type: str, source_file: str = ""):
    """Record a novel pattern. Atomic UPSERT — race-safe across hook subprocesses.

    Schema has UNIQUE(pattern, pattern_type, theme) so ON CONFLICT is well-defined.
    """
    conn = _get_conn()
    if not conn:
        return

    now = time.time()
    try:
        conn.execute(
            "INSERT INTO novel_patterns "
            "(pattern, pattern_type, source_file, theme, task_type, "
            " times_seen, first_seen, last_seen) "
            "VALUES (?, ?, ?, ?, ?, 1, ?, ?) "
            "ON CONFLICT(pattern, pattern_type, theme) DO UPDATE SET "
            "times_seen = times_seen + 1, last_seen = excluded.last_seen, "
            "task_type = excluded.task_type",
            (pattern, pattern_type, source_file, theme, task_type, now, now),
        )

        count = conn.execute(
            "SELECT COUNT(*) FROM novel_patterns WHERE promoted = 0"
        ).fetchone()[0]
        if count > MAX_NOVEL_PATTERNS:
            conn.execute(
                "DELETE FROM novel_patterns WHERE id IN ("
                "  SELECT id FROM novel_patterns WHERE promoted = 0 "
                "  ORDER BY last_seen ASC LIMIT ?"
                ")",
                (count - MAX_NOVEL_PATTERNS,),
            )
        conn.commit()
    except Exception as e:
        _log_err("record_novel_pattern", e)


def get_promotable_patterns(min_occurrences: int = 3) -> list[dict]:
    """Find novel patterns seen enough times to suggest as Kiwi lessons."""
    conn = _get_conn()
    if not conn:
        return []

    try:
        rows = conn.execute(
            "SELECT id, pattern, pattern_type, theme, task_type, times_seen, first_seen "
            "FROM novel_patterns "
            "WHERE promoted = 0 AND times_seen >= ? "
            "ORDER BY times_seen DESC LIMIT 10",
            (min_occurrences,),
        ).fetchall()

        return [{
            "id": r[0], "pattern": r[1], "type": r[2], "theme": r[3],
            "task_type": r[4], "times_seen": r[5], "first_seen": r[6],
        } for r in rows]
    except Exception as e:
        _log_err("get_promotable_patterns", e)
        return []


def promote_pattern(pattern_id: int):
    """Mark pattern as promoted (lesson suggestion created)."""
    conn = _get_conn()
    if conn:
        try:
            conn.execute("UPDATE novel_patterns SET promoted = 1 WHERE id = ?", (pattern_id,))
            conn.commit()
        except Exception as e:
            _log_err("promote_pattern", e)