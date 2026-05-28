"""R5 — Auto-Promote Pipeline: novel patterns → Kiwi lesson suggestions."""

import time

from .session_logger import _get_conn
from .novel_detector import get_promotable_patterns, promote_pattern

MAX_PROMOTIONS_PER_SESSION = 2

PATTERN_TYPE_TO_CATEGORY = {
    "binding": "api-usage",
    "style": "layout-consistency",
    "hook": "api-usage",
    "component": "component-pattern",
}

PATTERN_TYPE_TO_SEVERITY = {
    "binding": "SUGGEST",
    "style": "SUGGEST",
    "hook": "SUGGEST",
    "component": "SUGGEST",
}


def auto_promote_check() -> list[dict]:
    """Check for promotable patterns and create lesson suggestions. Max 2 per call."""
    promotable = get_promotable_patterns(min_occurrences=3)
    if not promotable:
        return []

    created = []
    for pattern in promotable[:MAX_PROMOTIONS_PER_SESSION]:
        # R8: validate novel pattern before promoting
        try:
            from .thinker import think
            ctx = {
                'pattern': pattern.get('pattern', ''),
                'pattern_type': pattern.get('type', ''),
                'task_type': pattern.get('task_type', 'generic'),
                'theme': pattern.get('theme', ''),
                'times_seen': pattern.get('times_seen', 0),
            }
            result = think('novel_validation', ctx)
            if result and result.confidence >= 0.7 and result.decision == 'skip':
                continue
        except Exception:
            pass

        suggestion = _create_suggestion(pattern)
        if suggestion:
            promote_pattern(pattern["id"])
            created.append(suggestion)

    return created


def _create_suggestion(pattern: dict) -> dict | None:
    """Create a pending lesson suggestion from a novel pattern."""
    conn = _get_conn()
    if not conn:
        return None

    category = PATTERN_TYPE_TO_CATEGORY.get(pattern["type"], "api-usage")
    severity = PATTERN_TYPE_TO_SEVERITY.get(pattern["type"], "SUGGEST")

    suggestion = {
        "pattern": pattern["pattern"],
        "pattern_type": pattern["type"],
        "category": category,
        "severity": severity,
        "theme": pattern.get("theme", "unknown"),
        "task_type": pattern.get("task_type", "generic"),
        "times_seen": pattern["times_seen"],
        "source": "auto_promote_r5",
    }

    try:
        existing = conn.execute(
            "SELECT id FROM promotion_suggestions WHERE pattern = ? AND pattern_type = ?",
            (suggestion["pattern"], suggestion["pattern_type"]),
        ).fetchone()
        if existing:
            return None

        conn.execute(
            "INSERT INTO promotion_suggestions "
            "(pattern, pattern_type, category, severity, theme, task_type, "
            "times_seen, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
            (
                suggestion["pattern"],
                suggestion["pattern_type"],
                suggestion["category"],
                suggestion["severity"],
                suggestion["theme"],
                suggestion["task_type"],
                suggestion["times_seen"],
                time.time(),
            ),
        )
        conn.commit()
        return suggestion
    except Exception:
        return None


def get_pending_suggestions(limit: int = 10) -> list[dict]:
    """Get pending promotion suggestions for review."""
    conn = _get_conn()
    if not conn:
        return []

    try:
        rows = conn.execute(
            "SELECT id, pattern, pattern_type, category, severity, theme, "
            "task_type, times_seen, created_at "
            "FROM promotion_suggestions WHERE status = 'pending' "
            "ORDER BY times_seen DESC LIMIT ?",
            (limit,),
        ).fetchall()

        return [{
            "id": r[0], "pattern": r[1], "type": r[2], "category": r[3],
            "severity": r[4], "theme": r[5], "task_type": r[6],
            "times_seen": r[7], "created_at": r[8],
        } for r in rows]
    except Exception:
        return []


def approve_suggestion(suggestion_id: int) -> bool:
    conn = _get_conn()
    if not conn:
        return False
    try:
        conn.execute(
            "UPDATE promotion_suggestions SET status = 'approved' WHERE id = ?",
            (suggestion_id,),
        )
        conn.commit()
        return True
    except Exception:
        return False


def reject_suggestion(suggestion_id: int) -> bool:
    conn = _get_conn()
    if not conn:
        return False
    try:
        conn.execute(
            "UPDATE promotion_suggestions SET status = 'rejected' WHERE id = ?",
            (suggestion_id,),
        )
        conn.commit()
        return True
    except Exception:
        return False