"""R6 — Approval Tracker: track Claude's approval/rejection of drafts."""

import time

from .session_logger import _get_conn
from .calibrator import _get_trust_baseline, _set_trust_baseline


def record_draft_outcome(session_id: str, task_type: str, level: str,
                         outcome: str, changes_made: int = 0):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO draft_outcomes "
        "(session_id, task_type, level, outcome, changes_made, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, task_type, level, outcome, changes_made, time.time()),
    )
    conn.commit()

    current = _get_trust_baseline(task_type)
    if outcome == "approved":
        _set_trust_baseline(task_type, min(current + 0.08, 0.95))
    elif outcome == "rejected":
        _set_trust_baseline(task_type, max(current - 0.12, 0.4))


def get_draft_success_rate(task_type: str, level: str) -> float:
    conn = _get_conn()
    row = conn.execute(
        "SELECT "
        "  SUM(CASE WHEN outcome IN ('approved', 'modified') THEN 1 ELSE 0 END), "
        "  COUNT(*) "
        "FROM draft_outcomes WHERE task_type = ? AND level = ?",
        (task_type, level),
    ).fetchone()

    if not row or row[1] == 0:
        return 0.0
    return row[0] / row[1]


def should_attempt_level(task_type: str, level: str) -> bool:
    conn = _get_conn()
    count = conn.execute(
        "SELECT COUNT(*) FROM draft_outcomes WHERE task_type = ? AND level = ?",
        (task_type, level),
    ).fetchone()[0]

    if count < 3:
        return True

    thresholds = {'skeleton': 0.3, 'draft': 0.5, 'ready': 0.7}
    threshold = thresholds.get(level, 0.5)
    return get_draft_success_rate(task_type, level) >= threshold
