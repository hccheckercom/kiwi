"""Confidence scoring for Kiwi lessons."""

import sys
from pathlib import Path
from .db import get_connection, _now

KIWI_DIR = Path(__file__).parent.parent


def recalculate_confidence(lesson_id: str) -> float:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM lesson_confidence WHERE lesson_id=?", (lesson_id,)
        ).fetchone()

        if not row:
            return 1.0

        total = max(row["total_hits"], 1)
        fp_rate = row["false_positive_count"] / total
        base_confidence = 1.0 - fp_rate

        fix_success = row["fix_success_count"]
        fix_failure = row["fix_failure_count"]
        if fix_success + fix_failure > 0:
            fix_rate = fix_success / (fix_success + fix_failure)
            confidence = base_confidence * 0.7 + fix_rate * 0.3
        else:
            confidence = base_confidence

        original_severity = _get_lesson_severity(lesson_id)
        if confidence < 0.3:
            effective = "SUGGEST"
        elif confidence < 0.5 and original_severity == "HIGH":
            effective = "SUGGEST"
        else:
            effective = original_severity

        conn.execute("""
            UPDATE lesson_confidence
            SET confidence=?, effective_severity=?, last_updated=?
            WHERE lesson_id=?
        """, (round(confidence, 3), effective, _now(), lesson_id))
        conn.commit()
    finally:
        conn.close()

    # Auto-disable if too noisy
    auto_disable_noisy_patterns()

    return confidence


def auto_disable_noisy_patterns(threshold: float = 0.2, min_hits: int = 10) -> list:
    """Auto-disable lessons with confidence below threshold.

    Args:
        threshold: Confidence threshold (default 0.2 = 80% FP rate)
        min_hits: Minimum total hits before considering disable

    Returns:
        List of disabled lesson IDs
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Find noisy patterns
        cursor.execute("""
            SELECT lesson_id, confidence, total_hits, false_positive_count
            FROM lesson_confidence
            WHERE confidence < ?
              AND total_hits >= ?
              AND disabled = 0
        """, (threshold, min_hits))

        disabled = []
        for row in cursor.fetchall():
            lesson_id, conf, total, fps = row
            fp_rate = fps / total if total > 0 else 0
            reason = f"FP rate {fp_rate:.0%} (confidence {conf:.2f})"

            cursor.execute("""
                UPDATE lesson_confidence
                SET disabled = 1,
                    disabled_reason = ?,
                    disabled_at = ?
                WHERE lesson_id = ?
            """, (reason, _now(), lesson_id))

            disabled.append(lesson_id)

        conn.commit()
    finally:
        conn.close()
    return disabled


def get_disabled_lessons() -> list:
    """Get list of disabled lesson IDs."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT lesson_id FROM lesson_confidence WHERE disabled = 1")
        result = [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()
    return result


def update_hit(lesson_id: str, is_true_positive: bool = True):
    tp = 1 if is_true_positive else 0
    fp = 0 if is_true_positive else 1
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO lesson_confidence (lesson_id, total_hits, true_positive_count, false_positive_count, last_hit)
            VALUES (?, 1, ?, ?, ?)
            ON CONFLICT(lesson_id) DO UPDATE SET
                total_hits = total_hits + 1,
                true_positive_count = true_positive_count + ?,
                false_positive_count = false_positive_count + ?,
                last_hit = ?
        """, (lesson_id, tp, fp, _now(), tp, fp, _now()))
        conn.commit()
    finally:
        conn.close()


def record_fix_outcome(lesson_id: str, success: bool, file: str = None, line: int = None):
    """Record fix success/failure for confidence calculation.

    Args:
        lesson_id: Lesson ID
        success: True if fix succeeded, False if failed
        file: Optional file path where fix was applied
        line: Optional line number where fix was applied
    """
    conn = get_connection()
    try:
        if success:
            conn.execute("""
                INSERT INTO lesson_confidence (lesson_id, fix_success_count, total_hits)
                VALUES (?, 1, 0)
                ON CONFLICT(lesson_id) DO UPDATE SET
                    fix_success_count = fix_success_count + 1
            """, (lesson_id,))
        else:
            conn.execute("""
                INSERT INTO lesson_confidence (lesson_id, fix_failure_count, total_hits)
                VALUES (?, 1, 0)
                ON CONFLICT(lesson_id) DO UPDATE SET
                    fix_failure_count = fix_failure_count + 1
            """, (lesson_id,))
        conn.commit()
    finally:
        conn.close()
    recalculate_confidence(lesson_id)


def get_confidence(lesson_id: str) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM lesson_confidence WHERE lesson_id=?", (lesson_id,)
        ).fetchone()
    finally:
        conn.close()
    if row:
        return dict(row)
    return {"lesson_id": lesson_id, "confidence": 1.0, "total_hits": 0}


def get_noisy_lessons(min_fps: int = 3) -> list:
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT lesson_id, total_hits, false_positive_count, confidence, effective_severity
            FROM lesson_confidence
            WHERE false_positive_count >= ?
            ORDER BY confidence ASC
            LIMIT 20
        """, (min_fps,)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def get_all_confidence() -> list:
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT lesson_id, total_hits, true_positive_count, false_positive_count,
                   fix_success_count, fix_failure_count, confidence, effective_severity
            FROM lesson_confidence
            ORDER BY total_hits DESC
            LIMIT 50
        """).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def _get_lesson_severity(lesson_id: str) -> str:
    try:
        sys.path.insert(0, str(KIWI_DIR))
        from scanner.loader import load_patterns
        patterns = load_patterns(str(KIWI_DIR / "lessons"))
        for p in patterns:
            if p.get("id") == lesson_id:
                return p.get("severity", "HIGH")
    except Exception as e:
        import sys
        print(f"[kiwi] confidence check error: {e}", file=sys.stderr)
    return "HIGH"