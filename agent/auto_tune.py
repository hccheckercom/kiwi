"""P1: Auto-tune Noisy Lessons.

Automatically adjust lesson severity or disable lessons when they produce too many false positives.

Triggers:
- precision < 0.70 AND false_positive_rate > 0.30 → demote severity
- precision < 0.50 → disable lesson temporarily
- Logs all actions to memory DB for audit trail
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.db import get_connection


def _now():
    return datetime.now(timezone.utc).isoformat()


def calculate_lesson_metrics(lesson_id: str) -> Optional[Dict]:
    """Calculate precision, recall, fix_rate, fp_rate for a lesson."""
    conn = get_connection()
    try:

        row = conn.execute("""
            SELECT
                total_hits,
                true_positive_count,
                false_positive_count,
                fix_success_count,
                fix_failure_count,
                confidence,
                effective_severity,
                disabled
            FROM lesson_confidence
            WHERE lesson_id = ?
        """, (lesson_id,)).fetchone()

    finally:
        conn.close()

    if not row or row["total_hits"] == 0:
        return None

    tp = row["true_positive_count"]
    fp = row["false_positive_count"]
    total = row["total_hits"]
    fix_success = row["fix_success_count"]
    fix_failure = row["fix_failure_count"]

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / total if total > 0 else 0.0
    fix_rate = fix_success / (fix_success + fix_failure) if (fix_success + fix_failure) > 0 else 0.0
    fp_rate = fp / total if total > 0 else 0.0

    return {
        "lesson_id": lesson_id,
        "precision": round(precision, 2),
        "recall": round(recall, 2),
        "fix_rate": round(fix_rate, 2),
        "false_positive_rate": round(fp_rate, 2),
        "total_hits": total,
        "true_positives": tp,
        "false_positives": fp,
        "confidence": row["confidence"],
        "effective_severity": row["effective_severity"],
        "disabled": bool(row["disabled"]),
    }


def get_severity_demotion(current_severity: str) -> Optional[str]:
    """Get next lower severity level."""
    severity_order = ["CRITICAL", "HIGH", "SUGGEST"]
    try:
        idx = severity_order.index(current_severity)
        if idx < len(severity_order) - 1:
            return severity_order[idx + 1]
    except ValueError:
        pass
    return None


def auto_tune_lesson(lesson_id: str, dry_run: bool = False) -> Dict:
    """Auto-tune a single lesson based on metrics.

    Returns:
        {
            "action": "demote" | "disable" | "none",
            "old_severity": str,
            "new_severity": str | None,
            "reason": str,
            "metrics": dict
        }
    """
    metrics = calculate_lesson_metrics(lesson_id)

    if not metrics:
        return {
            "action": "none",
            "reason": "No metrics available",
            "metrics": None
        }

    if metrics["disabled"]:
        return {
            "action": "none",
            "reason": "Already disabled",
            "metrics": metrics
        }

    precision = metrics["precision"]
    fp_rate = metrics["false_positive_rate"]
    current_severity = metrics["effective_severity"]

    # Rule 1: precision < 0.50 → disable
    if precision < 0.50:
        if not dry_run:
            _disable_lesson(lesson_id, f"Auto-disabled: precision {precision:.2f} < 0.50")

        return {
            "action": "disable",
            "old_severity": current_severity,
            "new_severity": None,
            "reason": f"Precision {precision:.2f} < 0.50 threshold",
            "metrics": metrics
        }

    # Rule 2: precision < 0.70 AND fp_rate > 0.30 → demote severity
    if precision < 0.70 and fp_rate > 0.30:
        new_severity = get_severity_demotion(current_severity)

        if not new_severity:
            return {
                "action": "none",
                "reason": f"Already at lowest severity ({current_severity})",
                "metrics": metrics
            }

        if not dry_run:
            _demote_lesson(lesson_id, current_severity, new_severity,
                          f"Auto-demoted: precision {precision:.2f}, fp_rate {fp_rate:.2f}")

        return {
            "action": "demote",
            "old_severity": current_severity,
            "new_severity": new_severity,
            "reason": f"Precision {precision:.2f} < 0.70 AND fp_rate {fp_rate:.2f} > 0.30",
            "metrics": metrics
        }

    # No action needed
    return {
        "action": "none",
        "reason": "Metrics within acceptable range",
        "metrics": metrics
    }


def _demote_lesson(lesson_id: str, old_severity: str, new_severity: str, reason: str):
    """Demote lesson severity in DB."""
    conn = get_connection()
    try:

        conn.execute("""
            UPDATE lesson_confidence
            SET effective_severity = ?,
                last_updated = ?
            WHERE lesson_id = ?
        """, (new_severity, _now(), lesson_id))

        # Log to auto_tune_history
        conn.execute("""
            INSERT INTO auto_tune_history
            (lesson_id, action, old_severity, new_severity, reason, timestamp)
            VALUES (?, 'demote', ?, ?, ?, ?)
        """, (lesson_id, old_severity, new_severity, reason, _now()))

        conn.commit()
    finally:
        conn.close()


def _disable_lesson(lesson_id: str, reason: str):
    """Disable lesson in DB."""
    conn = get_connection()
    try:

        conn.execute("""
            UPDATE lesson_confidence
            SET disabled = 1,
                disabled_reason = ?,
                disabled_at = ?,
                last_updated = ?
            WHERE lesson_id = ?
        """, (reason, _now(), _now(), lesson_id))

        # Log to auto_tune_history
        conn.execute("""
            INSERT INTO auto_tune_history
            (lesson_id, action, reason, timestamp)
            VALUES (?, 'disable', ?, ?)
        """, (lesson_id, reason, _now()))

        conn.commit()
    finally:
        conn.close()


def auto_tune_all(min_hits: int = 10, dry_run: bool = False) -> List[Dict]:
    """Auto-tune all lessons with sufficient data.

    Args:
        min_hits: Minimum total_hits required to tune (default 10)
        dry_run: If True, don't apply changes, just report

    Returns:
        List of tune results
    """
    conn = get_connection()
    try:

        rows = conn.execute("""
            SELECT lesson_id
            FROM lesson_confidence
            WHERE total_hits >= ?
            AND disabled = 0
            ORDER BY false_positive_count DESC
        """, (min_hits,)).fetchall()

    finally:
        conn.close()

    results = []
    for row in rows:
        result = auto_tune_lesson(row["lesson_id"], dry_run=dry_run)
        if result["action"] != "none":
            results.append(result)

    return results


def get_tune_history(lesson_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
    """Get auto-tune history."""
    conn = get_connection()
    try:

        if lesson_id:
            rows = conn.execute("""
                SELECT * FROM auto_tune_history
                WHERE lesson_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (lesson_id, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM auto_tune_history
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,)).fetchall()

    finally:
        conn.close()

    return [dict(row) for row in rows]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Auto-tune noisy lessons")
    parser.add_argument("--lesson", help="Tune specific lesson")
    parser.add_argument("--all", action="store_true", help="Tune all lessons")
    parser.add_argument("--min-hits", type=int, default=10, help="Min hits required (default 10)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without applying")
    parser.add_argument("--history", action="store_true", help="Show tune history")

    args = parser.parse_args()

    if args.history:
        history = get_tune_history(args.lesson)
        if not history:
            print("No tune history found")
        else:
            for h in history:
                print(f"{h['timestamp']}: {h['lesson_id']} - {h['action']}")
                if h.get('old_severity'):
                    print(f"  {h['old_severity']} → {h['new_severity']}")
                print(f"  Reason: {h['reason']}")
                print()

    elif args.lesson:
        result = auto_tune_lesson(args.lesson, dry_run=args.dry_run)
        print(f"Lesson: {args.lesson}")
        print(f"Action: {result['action']}")
        if result['action'] != 'none':
            print(f"Old severity: {result.get('old_severity')}")
            print(f"New severity: {result.get('new_severity')}")
        print(f"Reason: {result['reason']}")
        if result['metrics']:
            m = result['metrics']
            print(f"\nMetrics:")
            print(f"  Precision: {m['precision']:.2f}")
            print(f"  FP Rate: {m['false_positive_rate']:.2f}")
            print(f"  Total hits: {m['total_hits']}")

    elif args.all:
        results = auto_tune_all(min_hits=args.min_hits, dry_run=args.dry_run)
        if not results:
            print("No lessons need tuning")
        else:
            print(f"{'DRY RUN: ' if args.dry_run else ''}Tuned {len(results)} lessons:\n")
            for r in results:
                print(f"{r['metrics']['lesson_id']}: {r['action']}")
                if r['action'] == 'demote':
                    print(f"  {r['old_severity']} → {r['new_severity']}")
                print(f"  {r['reason']}")
                print()

    else:
        parser.print_help()