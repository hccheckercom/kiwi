"""Rollback history tracking for Kiwi."""

from pathlib import Path
from .db import get_connection, _now


def record_rollback(lesson_id: str, file: str, reason: str) -> None:
    """
    Record a rollback event in confidence tracking.

    Args:
        lesson_id: Lesson ID that was rolled back
        file: File path that was rolled back
        reason: Reason for rollback (e.g., "Tests failed", "Syntax error")
    """
    conn = get_connection()
    try:
        # Update lesson_confidence
        conn.execute("""
            INSERT INTO lesson_confidence (lesson_id, rollback_count, last_rollback_at, last_updated)
            VALUES (?, 1, ?, ?)
            ON CONFLICT(lesson_id) DO UPDATE SET
                rollback_count = rollback_count + 1,
                last_rollback_at = excluded.last_rollback_at,
                last_updated = excluded.last_updated
        """, (lesson_id, _now(), _now()))

        # Update fix_outcomes to mark as rolled back
        # SQLite doesn't support ORDER BY in UPDATE, so we need to find the ID first
        row = conn.execute("""
            SELECT id FROM fix_outcomes
            WHERE lesson_id = ? AND file = ?
            ORDER BY applied_at DESC
            LIMIT 1
        """, (lesson_id, file)).fetchone()

        if row:
            conn.execute("""
                UPDATE fix_outcomes
                SET rolled_back = 1
                WHERE id = ?
            """, (row["id"],))

        conn.commit()
    finally:
        conn.close()


def get_rollback_stats(lesson_id: str = None) -> dict:
    """
    Get rollback statistics.

    Args:
        lesson_id: Optional lesson ID to filter by

    Returns:
        Dict with rollback stats
    """
    conn = get_connection()
    try:
        if lesson_id:
            # Stats for specific lesson
            row = conn.execute("""
                SELECT
                    lesson_id,
                    rollback_count,
                    last_rollback_at,
                    fix_success_count,
                    fix_failure_count
                FROM lesson_confidence
                WHERE lesson_id = ?
            """, (lesson_id,)).fetchone()

            if not row:
                return {
                    "lesson_id": lesson_id,
                    "rollback_count": 0,
                    "last_rollback_at": None,
                    "fix_success_count": 0,
                    "fix_failure_count": 0,
                    "rollback_rate": 0.0
                }

            total_fixes = row["fix_success_count"] + row["fix_failure_count"]
            rollback_rate = row["rollback_count"] / total_fixes if total_fixes > 0 else 0.0

            return {
                "lesson_id": row["lesson_id"],
                "rollback_count": row["rollback_count"],
                "last_rollback_at": row["last_rollback_at"],
                "fix_success_count": row["fix_success_count"],
                "fix_failure_count": row["fix_failure_count"],
                "rollback_rate": round(rollback_rate, 3)
            }
        else:
            # Overall stats
            row = conn.execute("""
                SELECT
                    COUNT(*) as lessons_with_rollbacks,
                    SUM(rollback_count) as total_rollbacks,
                    AVG(rollback_count) as avg_rollbacks_per_lesson,
                    MAX(rollback_count) as max_rollbacks
                FROM lesson_confidence
                WHERE rollback_count > 0
            """).fetchone()

            return {
                "lessons_with_rollbacks": row["lessons_with_rollbacks"] or 0,
                "total_rollbacks": row["total_rollbacks"] or 0,
                "avg_rollbacks_per_lesson": round(row["avg_rollbacks_per_lesson"] or 0, 2),
                "max_rollbacks": row["max_rollbacks"] or 0
            }
    finally:
        conn.close()


def get_high_rollback_lessons(min_rollbacks: int = 3) -> list:
    """
    Get lessons with high rollback rates.

    Args:
        min_rollbacks: Minimum rollback count to include

    Returns:
        List of lessons with high rollback rates
    """
    conn = get_connection()
    try:
        cursor = conn.execute("""
            SELECT
                lesson_id,
                rollback_count,
                fix_success_count,
                fix_failure_count,
                last_rollback_at,
                CAST(rollback_count AS FLOAT) / NULLIF(fix_success_count + fix_failure_count, 0) as rollback_rate
            FROM lesson_confidence
            WHERE rollback_count >= ?
            ORDER BY rollback_rate DESC, rollback_count DESC
            LIMIT 20
        """, (min_rollbacks,))

        results = []
        for row in cursor.fetchall():
            results.append({
                "lesson_id": row["lesson_id"],
                "rollback_count": row["rollback_count"],
                "fix_success_count": row["fix_success_count"],
                "fix_failure_count": row["fix_failure_count"],
                "rollback_rate": round(row["rollback_rate"] or 0, 3),
                "last_rollback_at": row["last_rollback_at"]
            })

        return results
    finally:
        conn.close()