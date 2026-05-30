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


def _log_err(stage: str, exc: BaseException) -> None:
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
            (f"auto_promoter.{stage}", time.time(), f"{type(exc).__name__}: {exc}"[:500]),
        )
        conn.commit()
    except Exception:
        pass


def _ensure_promotion_unique_index(conn):
    """Promote SELECT-then-INSERT to atomic UPSERT by adding a unique index."""
    try:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_ps_pattern_type "
            "ON promotion_suggestions(pattern, pattern_type)"
        )
    except Exception as e:
        _log_err("ensure_unique_index", e)


def auto_promote_check(use_llm_validation: bool = True) -> list[dict]:
    """Check for promotable patterns and create lesson suggestions. Max 2 per call.

    use_llm_validation: when True, run the Haiku `novel_validation` think pass to
    filter low-value patterns. The post-edit hook calls this with False to keep
    the edit path 0-token and fast — suggestions are pending-review anyway, so a
    human filters them at the dashboard.
    """
    promotable = get_promotable_patterns(min_occurrences=3)
    if not promotable:
        return []

    created = []
    for pattern in promotable[:MAX_PROMOTIONS_PER_SESSION]:
        if use_llm_validation:
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
            except Exception as e:
                _log_err("think_validation", e)

        suggestion = _create_suggestion(pattern)
        if suggestion:
            promote_pattern(pattern["id"])
            created.append(suggestion)

    return created


def _create_suggestion(pattern: dict) -> dict | None:
    """Create a pending lesson suggestion. Atomic UPSERT — race-safe."""
    conn = _get_conn()
    if not conn:
        return None

    _ensure_promotion_unique_index(conn)

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
        cursor = conn.execute(
            "INSERT INTO promotion_suggestions "
            "(pattern, pattern_type, category, severity, theme, task_type, "
            "times_seen, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?) "
            "ON CONFLICT(pattern, pattern_type) DO NOTHING",
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
        if cursor.rowcount == 0:
            return None
        return suggestion
    except Exception as e:
        _log_err("create_suggestion", e)
        return None


def auto_bless_mature(min_seen: int = 10) -> int:
    """Auto-bless conventions a developer has repeated enough to be intentional.

    The manual approve path (`approve_suggestion`) blesses one convention at a
    time and requires a human at the dashboard — which never happened, so
    `total_blessed_conventions` sat at 0 despite bindings seen 36x. A binding
    used >= min_seen times in real theme work IS the project's convention by
    definition; we promote it automatically so kiwi_context/kiwi_reason inject
    it as enforced knowledge. Excludes the 'unknown' theme (scratch work).

    Returns the number of bindings + styles newly blessed.
    """
    conn = _get_conn()
    if not conn:
        return 0
    try:
        b = conn.execute(
            "UPDATE binding_knowledge SET blessed = 1 "
            "WHERE times_seen >= ? AND blessed = 0 "
            "AND theme IS NOT NULL AND theme NOT IN ('', 'unknown')",
            (min_seen,),
        )
        s = conn.execute(
            "UPDATE style_knowledge SET blessed = 1 "
            "WHERE times_seen >= ? AND blessed = 0 "
            "AND theme IS NOT NULL AND theme NOT IN ('', 'unknown')",
            (min_seen,),
        )
        conn.commit()
        return (b.rowcount or 0) + (s.rowcount or 0)
    except Exception as e:
        _log_err("auto_bless_mature", e)
        return 0


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
    except Exception as e:
        _log_err("get_pending_suggestions", e)
        return []


def approve_suggestion(suggestion_id: int) -> bool:
    """Approve a suggestion = BLESS its underlying convention.

    A human reviewer confirming a suggestion means "this pattern is a real
    convention for the project." We deliberately do NOT generate a scannable
    lesson from it: a binding like ``wp:wp_insert_post`` is correct usage, not a
    bug — turning it into a presence-scan rule would flag every correct call as a
    violation (a false-positive generator). Instead we set ``blessed = 1`` on the
    matching binding_knowledge / style_knowledge row so kiwi_context ALWAYS
    injects it, regardless of times_seen. We also stamp approved_at so health
    reporting reflects when a human actually acted (BUG: created_at = suggested,
    not approved).
    """
    conn = _get_conn()
    if not conn:
        return False
    try:
        row = conn.execute(
            "SELECT pattern, pattern_type, theme, task_type "
            "FROM promotion_suggestions WHERE id = ?",
            (suggestion_id,),
        ).fetchone()
        conn.execute(
            "UPDATE promotion_suggestions SET status = 'approved', approved_at = ? WHERE id = ?",
            (time.time(), suggestion_id),
        )
        if row:
            _bless_convention(conn, row[0], row[1], row[2], row[3])
        conn.commit()
        return True
    except Exception as e:
        _log_err("approve_suggestion", e)
        return False


def _bless_convention(conn, pattern, pattern_type, theme, task_type) -> None:
    """Pin a learned convention so kiwi_context always injects it.

    Best-effort: a missing matching row (e.g. theme recorded as 'unknown' on the
    suggestion but concrete in binding_knowledge) just blesses nothing — the
    status flip already recorded the human decision, so this never raises.
    """
    if pattern_type in ("binding", "hook"):
        cur = conn.execute(
            "UPDATE binding_knowledge SET blessed = 1 "
            "WHERE binding = ? AND task_type = ? AND theme = ?",
            (pattern, task_type, theme),
        )
        if cur.rowcount == 0:
            # Theme didn't match (e.g. 'unknown'); bless the convention task-wide.
            conn.execute(
                "UPDATE binding_knowledge SET blessed = 1 "
                "WHERE binding = ? AND task_type = ?",
                (pattern, task_type),
            )
    elif pattern_type == "style":
        conn.execute(
            "UPDATE style_knowledge SET blessed = 1 WHERE theme = ? AND pattern_key = ?",
            (theme, pattern),
        )


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
    except Exception as e:
        _log_err("reject_suggestion", e)
        return False