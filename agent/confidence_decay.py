"""P2: Confidence Decay Theo Thời Gian.

Giảm confidence score của lessons không có violation mới trong thời gian dài.
Cảnh báo lessons có thể lỗi thời khi confidence < 0.50.

Decay rules:
- Mỗi 30 ngày không có violation mới → giảm 10% confidence
- Khi có violation mới → reset decay timer
- Confidence < 0.50 → cảnh báo "lesson có thể lỗi thời"
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.db import get_connection


def _now():
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(iso_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO timestamp to datetime with timezone awareness."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        # Ensure timezone aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None


def calculate_decay(lesson_id: str, current_time: datetime = None) -> Dict:
    """Calculate confidence decay for a lesson.

    Returns:
        {
            "lesson_id": str,
            "current_confidence": float,
            "last_hit": datetime | None,
            "days_since_hit": int,
            "decay_periods": int,  # number of 30-day periods
            "decay_amount": float,  # total decay (0.0 - 1.0)
            "new_confidence": float,
            "needs_review": bool,  # True if new_confidence < 0.50
        }
    """
    if current_time is None:
        current_time = datetime.now(timezone.utc)

    conn = get_connection()
    try:

        row = conn.execute("""
            SELECT
                lesson_id,
                confidence,
                last_hit,
                disabled
            FROM lesson_confidence
            WHERE lesson_id = ?
        """, (lesson_id,)).fetchone()

    finally:
        conn.close()

    if not row:
        return {
            "lesson_id": lesson_id,
            "error": "Lesson not found in confidence table"
        }

    if row["disabled"]:
        return {
            "lesson_id": lesson_id,
            "current_confidence": row["confidence"],
            "disabled": True,
            "message": "Lesson is disabled, no decay applied"
        }

    current_confidence = row["confidence"]
    last_hit = _parse_iso(row["last_hit"])

    if not last_hit:
        # No hits yet, no decay
        return {
            "lesson_id": lesson_id,
            "current_confidence": current_confidence,
            "last_hit": None,
            "days_since_hit": 0,
            "decay_periods": 0,
            "decay_amount": 0.0,
            "new_confidence": current_confidence,
            "needs_review": False,
            "message": "No hits recorded yet"
        }

    days_since_hit = (current_time - last_hit).days
    decay_periods = days_since_hit // 30  # integer division

    if decay_periods == 0:
        # Less than 30 days, no decay
        return {
            "lesson_id": lesson_id,
            "current_confidence": current_confidence,
            "last_hit": last_hit,
            "days_since_hit": days_since_hit,
            "decay_periods": 0,
            "decay_amount": 0.0,
            "new_confidence": current_confidence,
            "needs_review": False,
            "message": f"Last hit {days_since_hit} days ago, no decay yet"
        }

    # Each period decays 10% of CURRENT confidence (compound decay)
    decay_amount = 0.0
    new_confidence = current_confidence

    for _ in range(decay_periods):
        decay_this_period = new_confidence * 0.10
        new_confidence -= decay_this_period
        decay_amount += decay_this_period

    new_confidence = max(0.0, new_confidence)  # floor at 0
    needs_review = new_confidence < 0.50

    return {
        "lesson_id": lesson_id,
        "current_confidence": current_confidence,
        "last_hit": last_hit,
        "days_since_hit": days_since_hit,
        "decay_periods": decay_periods,
        "decay_amount": round(decay_amount, 2),
        "new_confidence": round(new_confidence, 2),
        "needs_review": needs_review,
    }


def apply_decay(lesson_id: str, dry_run: bool = False) -> Dict:
    """Apply confidence decay to a lesson.

    Returns:
        Same as calculate_decay() + "applied" field
    """
    result = calculate_decay(lesson_id)

    if "error" in result or result.get("disabled"):
        return result

    if result["decay_periods"] == 0:
        return {**result, "applied": False}

    new_confidence = result["new_confidence"]

    if not dry_run:
        conn = get_connection()
        try:

            conn.execute("""
                UPDATE lesson_confidence
                SET confidence = ?,
                    last_updated = ?
                WHERE lesson_id = ?
            """, (new_confidence, _now(), lesson_id))

            # Log to decay_history
            conn.execute("""
                INSERT INTO decay_history
                (lesson_id, old_confidence, new_confidence, days_since_hit, decay_amount, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                lesson_id,
                result["current_confidence"],
                new_confidence,
                result["days_since_hit"],
                result["decay_amount"],
                _now()
            ))

            conn.commit()
        finally:
            conn.close()

    return {**result, "applied": not dry_run}


def apply_decay_all(min_days: int = 30, dry_run: bool = False) -> List[Dict]:
    """Apply decay to all lessons with last_hit older than min_days.

    Args:
        min_days: Minimum days since last hit to apply decay (default 30)
        dry_run: If True, don't apply changes

    Returns:
        List of decay results
    """
    conn = get_connection()
    try:

        cutoff = (datetime.now(timezone.utc) - timedelta(days=min_days)).isoformat()

        rows = conn.execute("""
            SELECT lesson_id
            FROM lesson_confidence
            WHERE last_hit IS NOT NULL
            AND last_hit < ?
            AND disabled = 0
            ORDER BY last_hit ASC
        """, (cutoff,)).fetchall()

    finally:
        conn.close()

    results = []
    for row in rows:
        result = apply_decay(row["lesson_id"], dry_run=dry_run)
        if result.get("decay_periods", 0) > 0:
            results.append(result)

    return results


def get_stale_lessons(confidence_threshold: float = 0.50) -> List[Dict]:
    """Get lessons with confidence below threshold (potentially stale).

    Returns:
        List of {lesson_id, confidence, last_hit, days_since_hit}
    """
    conn = get_connection()
    try:

        rows = conn.execute("""
            SELECT
                lesson_id,
                confidence,
                last_hit
            FROM lesson_confidence
            WHERE confidence < ?
            AND disabled = 0
            ORDER BY confidence ASC
        """, (confidence_threshold,)).fetchall()

    finally:
        conn.close()

    results = []
    now = datetime.now(timezone.utc)

    for row in rows:
        last_hit = _parse_iso(row["last_hit"])
        days_since_hit = (now - last_hit).days if last_hit else None

        results.append({
            "lesson_id": row["lesson_id"],
            "confidence": round(row["confidence"], 2),
            "last_hit": last_hit.isoformat() if last_hit else None,
            "days_since_hit": days_since_hit,
        })

    return results


def reset_decay(lesson_id: str) -> Dict:
    """Reset decay timer when lesson gets a new hit.

    Called automatically when a violation is detected.
    """
    conn = get_connection()
    try:

        conn.execute("""
            UPDATE lesson_confidence
            SET last_hit = ?,
                last_updated = ?
            WHERE lesson_id = ?
        """, (_now(), _now(), lesson_id))

        conn.commit()
    finally:
        conn.close()

    return {
        "lesson_id": lesson_id,
        "action": "reset_decay",
        "last_hit": _now(),
    }


def get_decay_history(lesson_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
    """Get decay history."""
    conn = get_connection()
    try:

        if lesson_id:
            rows = conn.execute("""
                SELECT * FROM decay_history
                WHERE lesson_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (lesson_id, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM decay_history
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,)).fetchall()

    finally:
        conn.close()

    return [dict(row) for row in rows]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Confidence decay management")
    parser.add_argument("--lesson", help="Calculate/apply decay for specific lesson")
    parser.add_argument("--all", action="store_true", help="Apply decay to all eligible lessons")
    parser.add_argument("--min-days", type=int, default=30, help="Min days since last hit (default 30)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without applying")
    parser.add_argument("--stale", action="store_true", help="List stale lessons (confidence < 0.50)")
    parser.add_argument("--history", action="store_true", help="Show decay history")
    parser.add_argument("--reset", help="Reset decay timer for lesson (when new hit detected)")

    args = parser.parse_args()

    if args.history:
        history = get_decay_history(args.lesson)
        if not history:
            print("No decay history found")
        else:
            for h in history:
                print(f"{h['timestamp']}: {h['lesson_id']}")
                print(f"  {h['old_confidence']:.2f} -> {h['new_confidence']:.2f} (decay: {h['decay_amount']:.2f})")
                print(f"  Days since hit: {h['days_since_hit']}")
                print()

    elif args.stale:
        stale = get_stale_lessons()
        if not stale:
            print("No stale lessons found (all confidence >= 0.50)")
        else:
            print(f"Found {len(stale)} stale lessons (confidence < 0.50):\n")
            for s in stale:
                print(f"{s['lesson_id']}: confidence {s['confidence']:.2f}")
                if s['days_since_hit']:
                    print(f"  Last hit: {s['days_since_hit']} days ago")
                else:
                    print(f"  Last hit: never")
                print()

    elif args.reset:
        result = reset_decay(args.reset)
        print(f"Reset decay timer for {result['lesson_id']}")
        print(f"Last hit: {result['last_hit']}")

    elif args.lesson:
        result = apply_decay(args.lesson, dry_run=args.dry_run)

        if "error" in result:
            print(f"Error: {result['error']}")
        elif result.get("disabled"):
            print(f"{result['lesson_id']}: {result['message']}")
        elif result.get("decay_periods", 0) == 0:
            print(f"{result['lesson_id']}: {result.get('message', 'No decay')}")
        else:
            print(f"Lesson: {result['lesson_id']}")
            print(f"Current confidence: {result['current_confidence']:.2f}")
            print(f"Days since last hit: {result['days_since_hit']}")
            print(f"Decay periods: {result['decay_periods']} (x30 days)")
            print(f"Decay amount: {result['decay_amount']:.2f}")
            print(f"New confidence: {result['new_confidence']:.2f}")
            if result['needs_review']:
                print("WARNING: Confidence < 0.50 - lesson may be outdated, needs review")
            if args.dry_run:
                print("\n(Dry run - not applied)")

    elif args.all:
        results = apply_decay_all(min_days=args.min_days, dry_run=args.dry_run)
        if not results:
            print(f"No lessons need decay (all last_hit within {args.min_days} days)")
        else:
            print(f"{'DRY RUN: ' if args.dry_run else ''}Applied decay to {len(results)} lessons:\n")
            for r in results:
                print(f"{r['lesson_id']}: {r['current_confidence']:.2f} -> {r['new_confidence']:.2f}")
                print(f"  {r['days_since_hit']} days since hit, {r['decay_periods']} periods")
                if r['needs_review']:
                    print(f"  WARNING: Needs review (confidence < 0.50)")
                print()

    else:
        parser.print_help()