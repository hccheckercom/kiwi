"""R5 — Proactive Warnings: detect risky patterns + feedback loop."""

import json
import time

from .session_logger import _get_conn


WARNING_TYPES = {
    "low_data": "Kiwi has < 3 sessions for this task_type+theme. Brief may be incomplete.",
    "high_failure": "This task_type has > 40% failure rate. Consider reading spec carefully.",
    "novel_task": "No prior sessions match this task. Trust score is baseline only.",
    "stale_baseline": "Trust baseline hasn't been calibrated in 14+ days. Patterns may have changed.",
}

MAX_WARNINGS = 500
_SUPPRESS_THRESHOLD = 0.70
_SUPPRESS_SAMPLE_SIZE = 10


def check_warnings(task_type: str, theme: str, trust_score: float) -> list[dict]:
    """Pre-code check: return list of warnings if risky patterns detected."""
    warnings = []
    conn = _get_conn()
    if not conn:
        return warnings

    try:
        suppressed = _get_suppressed_types(conn, task_type)

        any_data = conn.execute(
            "SELECT COUNT(*) FROM context_patterns WHERE task_type = ?",
            (task_type,),
        ).fetchone()[0]

        if any_data == 0:
            if "novel_task" not in suppressed:
                warnings.append({
                    "type": "novel_task",
                    "message": WARNING_TYPES["novel_task"],
                })
        else:
            if "low_data" not in suppressed:
                session_count = conn.execute(
                    "SELECT COUNT(*) FROM context_patterns WHERE task_type = ? AND theme = ?",
                    (task_type, theme),
                ).fetchone()[0]
                if session_count < 3:
                    warnings.append({
                        "type": "low_data",
                        "message": WARNING_TYPES["low_data"],
                        "data": {"sessions": session_count},
                    })

        if "high_failure" not in suppressed:
            cal_events = conn.execute(
                "SELECT signals FROM calibration_events WHERE task_type = ? "
                "ORDER BY created_at DESC LIMIT 10",
                (task_type,),
            ).fetchall()
            if len(cal_events) >= 3:
                failure_count = 0
                for row in cal_events:
                    try:
                        signals = json.loads(row[0])
                        if signals.get("multiple_rewrites") or signals.get("kiwi_violations"):
                            failure_count += 1
                    except (json.JSONDecodeError, TypeError):
                        continue
                rate = failure_count / len(cal_events)
                if rate > 0.4:
                    warnings.append({
                        "type": "high_failure",
                        "message": WARNING_TYPES["high_failure"],
                        "data": {"failure_rate": round(rate, 2)},
                    })

        if "stale_baseline" not in suppressed:
            baseline = conn.execute(
                "SELECT last_calibrated FROM trust_baselines WHERE task_type = ?",
                (task_type,),
            ).fetchone()
            if baseline and (time.time() - baseline[0]) > 14 * 86400:
                warnings.append({
                    "type": "stale_baseline",
                    "message": WARNING_TYPES["stale_baseline"],
                })

        if warnings:
            _save_warnings(conn, task_type, warnings)

    except Exception:
        pass

    return warnings


def _get_suppressed_types(conn, task_type: str) -> set:
    """Warning types with > 70% not-useful rate in last 10 instances → suppress."""
    suppressed = set()
    for wtype in WARNING_TYPES:
        rows = conn.execute(
            "SELECT was_useful FROM warnings_issued "
            "WHERE task_type = ? AND warning_type = ? AND was_useful IS NOT NULL "
            "ORDER BY created_at DESC LIMIT ?",
            (task_type, wtype, _SUPPRESS_SAMPLE_SIZE),
        ).fetchall()
        if len(rows) < 3:
            continue
        not_useful = sum(1 for r in rows if r[0] == 0)
        if not_useful / len(rows) >= _SUPPRESS_THRESHOLD:
            suppressed.add(wtype)
    return suppressed


def _save_warnings(conn, task_type: str, warnings: list):
    try:
        from .session_logger import get_session_id
        session_id = get_session_id()
    except Exception:
        session_id = "unknown"

    now = time.time()
    for w in warnings:
        conn.execute(
            "INSERT INTO warnings_issued (session_id, task_type, warning_type, message, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, task_type, w["type"], w["message"], now),
        )

    # FIFO eviction
    count = conn.execute("SELECT COUNT(*) FROM warnings_issued").fetchone()[0]
    if count > MAX_WARNINGS:
        conn.execute(
            "DELETE FROM warnings_issued WHERE id IN ("
            "  SELECT id FROM warnings_issued ORDER BY created_at ASC LIMIT ?"
            ")",
            (count - MAX_WARNINGS,),
        )
    conn.commit()


def mark_warning_useful(warning_id: int, useful: bool):
    """Feedback: was this warning actually useful?"""
    conn = _get_conn()
    if conn:
        conn.execute(
            "UPDATE warnings_issued SET was_useful = ? WHERE id = ?",
            (1 if useful else 0, warning_id),
        )
        conn.commit()


def evaluate_warnings_post_session(session_id: str, negative_signal_count: int):
    """Auto-evaluate warnings issued in this session based on calibration outcome.

    Rules:
    - 0 negative signals → all warnings were noise (was_useful=0)
    - 2+ negative signals → warnings that predicted failure were useful (was_useful=1)
    - 1 negative signal → ambiguous, leave as NULL
    """
    conn = _get_conn()
    if not conn:
        return

    try:
        rows = conn.execute(
            "SELECT id, warning_type FROM warnings_issued "
            "WHERE session_id = ? AND was_useful IS NULL",
            (session_id,),
        ).fetchall()

        if not rows:
            return

        if negative_signal_count == 0:
            for row in rows:
                conn.execute(
                    "UPDATE warnings_issued SET was_useful = 0 WHERE id = ?",
                    (row[0],),
                )
        elif negative_signal_count >= 2:
            predictive_types = {"high_failure", "stale_baseline", "novel_task"}
            for row in rows:
                useful = 1 if row[1] in predictive_types else 0
                conn.execute(
                    "UPDATE warnings_issued SET was_useful = ? WHERE id = ?",
                    (useful, row[0]),
                )
        conn.commit()
    except Exception:
        pass