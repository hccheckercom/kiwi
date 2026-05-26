"""P4: User Feedback Loop.

Tích hợp user feedback (dismiss, approve) vào scoring system.
Auto-tune regex khi user dismiss > 5 lần với cùng pattern.

Feedback rules:
- Mỗi lần user dismiss → ghi vào false_positives với reason
- Nếu 1 lesson bị dismiss > 5 lần với cùng pattern → suggest regex tune
- Nếu user approve fix → tăng confidence score
- Track feedback history để học từ user behavior
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter
import re

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.db import get_connection


def analyze_dismiss_patterns(lesson_id: str, min_occurrences: int = 5) -> List[Dict]:
    """Analyze dismiss reasons to find recurring patterns.

    Args:
        lesson_id: Lesson to analyze
        min_occurrences: Minimum times a pattern must occur (default 5)

    Returns:
        List of {pattern, count, example_reasons, suggestion}
    """
    conn = get_connection()
    try:

        rows = conn.execute("""
            SELECT reason, file, match_text
            FROM false_positives
            WHERE lesson_id = ?
            AND active = 1
            ORDER BY dismissed_at DESC
        """, (lesson_id,)).fetchall()

    finally:
        conn.close()

    if not rows:
        return []

    # Extract common phrases from reasons
    reason_counter = Counter()
    reason_examples = defaultdict(list)

    for row in rows:
        reason = row["reason"].lower()

        # Extract key phrases (3+ words)
        words = reason.split()
        for i in range(len(words) - 2):
            phrase = " ".join(words[i:i+3])
            reason_counter[phrase] += 1
            if len(reason_examples[phrase]) < 3:
                reason_examples[phrase].append({
                    "reason": row["reason"],
                    "file": row["file"],
                    "match_text": row["match_text"]
                })

    # Filter patterns with min_occurrences
    patterns = []
    for phrase, count in reason_counter.most_common():
        if count < min_occurrences:
            break

        # Generate suggestion based on pattern
        suggestion = _generate_tune_suggestion(phrase, reason_examples[phrase])

        patterns.append({
            "pattern": phrase,
            "count": count,
            "example_reasons": reason_examples[phrase],
            "suggestion": suggestion
        })

    return patterns


def _generate_tune_suggestion(phrase: str, examples: List[Dict]) -> str:
    """Generate regex tune suggestion based on dismiss pattern."""

    # Common patterns and their fixes
    if "already" in phrase and "called" in phrase:
        return "Add negative lookahead to exclude cases where function already called in parent scope"

    if "false positive" in phrase and "comment" in phrase:
        return "Exclude commented code from pattern matching"

    if "test" in phrase or "mock" in phrase:
        return "Add exclusion for test files (test_*.php, *Test.php, tests/)"

    if "third party" in phrase or "vendor" in phrase:
        return "Add exclusion for vendor/ and third-party code"

    if "intentional" in phrase or "by design" in phrase:
        return "Pattern may be too strict - consider relaxing constraints"

    # Check if examples have common file patterns
    files = [e["file"] for e in examples]
    if all("test" in f.lower() for f in files):
        return "All dismissals in test files - add test file exclusion"

    if all("vendor" in f for f in files):
        return "All dismissals in vendor code - add vendor exclusion"

    return "Review pattern - recurring dismissals suggest false positive issue"


def suggest_regex_tune(lesson_id: str, min_dismissals: int = 5) -> Optional[Dict]:
    """Suggest regex tune for a lesson with many dismissals.

    Args:
        lesson_id: Lesson to analyze
        min_dismissals: Minimum dismissals to trigger suggestion (default 5)

    Returns:
        {
            "lesson_id": str,
            "total_dismissals": int,
            "patterns": List[Dict],
            "recommended_action": str
        }
        or None if no tune needed
    """
    conn = get_connection()
    try:

        # Get total dismissals
        row = conn.execute("""
            SELECT COUNT(*) as total
            FROM false_positives
            WHERE lesson_id = ?
            AND active = 1
        """, (lesson_id,)).fetchone()

    finally:
        conn.close()

    total_dismissals = row["total"]

    if total_dismissals < min_dismissals:
        return None

    # Analyze patterns
    patterns = analyze_dismiss_patterns(lesson_id, min_occurrences=3)

    if not patterns:
        return {
            "lesson_id": lesson_id,
            "total_dismissals": total_dismissals,
            "patterns": [],
            "recommended_action": f"{total_dismissals} dismissals but no clear pattern - manual review needed"
        }

    # Determine recommended action
    if len(patterns) == 1 and patterns[0]["count"] >= total_dismissals * 0.8:
        # Single dominant pattern
        action = f"Strong pattern detected: '{patterns[0]['pattern']}' ({patterns[0]['count']}/{total_dismissals} dismissals). {patterns[0]['suggestion']}"
    else:
        # Multiple patterns
        action = f"Multiple patterns detected ({len(patterns)} patterns). Review top patterns and consider multiple exclusions."

    return {
        "lesson_id": lesson_id,
        "total_dismissals": total_dismissals,
        "patterns": patterns,
        "recommended_action": action
    }


def apply_feedback_to_confidence(lesson_id: str) -> Dict:
    """Update lesson confidence based on feedback (dismissals + approvals).

    Returns:
        {
            "lesson_id": str,
            "old_confidence": float,
            "new_confidence": float,
            "dismissals": int,
            "approvals": int,
            "adjustment": float
        }
    """
    conn = get_connection()
    try:

        # Get current confidence
        row = conn.execute("""
            SELECT confidence, false_positive_count, fix_success_count
            FROM lesson_confidence
            WHERE lesson_id = ?
        """, (lesson_id,)).fetchone()

        if not row:
            return {
                "lesson_id": lesson_id,
                "error": "Lesson not found in confidence table"
            }

        old_confidence = row["confidence"]
        dismissals = row["false_positive_count"]
        approvals = row["fix_success_count"]

        # Calculate adjustment
        # Each dismissal: -0.02 confidence
        # Each approval: +0.01 confidence
        adjustment = (approvals * 0.01) - (dismissals * 0.02)
        new_confidence = max(0.0, min(1.0, old_confidence + adjustment))

        # Update DB
        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).isoformat()

        conn.execute("""
            UPDATE lesson_confidence
            SET confidence = ?,
                last_updated = ?
            WHERE lesson_id = ?
        """, (new_confidence, timestamp, lesson_id))

        # Log to feedback_adjustments
        conn.execute("""
            INSERT INTO feedback_adjustments
            (lesson_id, old_confidence, new_confidence, dismissals, approvals, adjustment, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (lesson_id, old_confidence, new_confidence, dismissals, approvals, adjustment, timestamp))

        conn.commit()
    finally:
        conn.close()

    return {
        "lesson_id": lesson_id,
        "old_confidence": round(old_confidence, 2),
        "new_confidence": round(new_confidence, 2),
        "dismissals": dismissals,
        "approvals": approvals,
        "adjustment": round(adjustment, 2)
    }


def get_lessons_needing_tune(min_dismissals: int = 5) -> List[Dict]:
    """Get all lessons that need regex tuning based on dismissals.

    Args:
        min_dismissals: Minimum dismissals to flag (default 5)

    Returns:
        List of lessons with tune suggestions
    """
    conn = get_connection()
    try:

        rows = conn.execute("""
            SELECT lesson_id, COUNT(*) as dismissals
            FROM false_positives
            WHERE active = 1
            GROUP BY lesson_id
            HAVING dismissals >= ?
            ORDER BY dismissals DESC
        """, (min_dismissals,)).fetchall()

    finally:
        conn.close()

    results = []
    for row in rows:
        suggestion = suggest_regex_tune(row["lesson_id"], min_dismissals)
        if suggestion:
            results.append(suggestion)

    return results


def auto_apply_feedback(min_dismissals: int = 10, dry_run: bool = False) -> List[Dict]:
    """Automatically apply feedback adjustments to all lessons.

    Args:
        min_dismissals: Minimum dismissals to process (default 10)
        dry_run: If True, don't apply changes

    Returns:
        List of adjustment results
    """
    conn = get_connection()
    try:

        rows = conn.execute("""
            SELECT lesson_id
            FROM lesson_confidence
            WHERE false_positive_count >= ?
            OR fix_success_count >= 5
            ORDER BY false_positive_count DESC
        """, (min_dismissals,)).fetchall()

    finally:
        conn.close()

    results = []
    for row in rows:
        if not dry_run:
            result = apply_feedback_to_confidence(row["lesson_id"])
        else:
            # Calculate without applying
            conn = get_connection()
            try:
                conf_row = conn.execute("""
                    SELECT confidence, false_positive_count, fix_success_count
                    FROM lesson_confidence
                    WHERE lesson_id = ?
                """, (row["lesson_id"],)).fetchone()
            finally:
                conn.close()

            if conf_row:
                dismissals = conf_row["false_positive_count"]
                approvals = conf_row["fix_success_count"]
                adjustment = (approvals * 0.01) - (dismissals * 0.02)
                new_confidence = max(0.0, min(1.0, conf_row["confidence"] + adjustment))

                result = {
                    "lesson_id": row["lesson_id"],
                    "old_confidence": round(conf_row["confidence"], 2),
                    "new_confidence": round(new_confidence, 2),
                    "dismissals": dismissals,
                    "approvals": approvals,
                    "adjustment": round(adjustment, 2),
                    "dry_run": True
                }
            else:
                continue

        if result.get("adjustment", 0) != 0:
            results.append(result)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="User feedback loop management")
    parser.add_argument("--analyze", metavar="LESSON_ID", help="Analyze dismiss patterns for lesson")
    parser.add_argument("--suggest", metavar="LESSON_ID", help="Suggest regex tune for lesson")
    parser.add_argument("--apply", metavar="LESSON_ID", help="Apply feedback to lesson confidence")
    parser.add_argument("--needing-tune", action="store_true", help="List lessons needing regex tune")
    parser.add_argument("--auto-apply", action="store_true", help="Auto-apply feedback to all lessons")
    parser.add_argument("--min-dismissals", type=int, default=5, help="Min dismissals (default 5)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without applying")

    args = parser.parse_args()

    if args.analyze:
        patterns = analyze_dismiss_patterns(args.analyze, min_occurrences=3)
        if not patterns:
            print(f"No recurring patterns found for {args.analyze}")
        else:
            print(f"Dismiss patterns for {args.analyze}:\n")
            for p in patterns:
                print(f"Pattern: '{p['pattern']}' ({p['count']} occurrences)")
                print(f"  Suggestion: {p['suggestion']}")
                print(f"  Examples:")
                for ex in p['example_reasons'][:2]:
                    print(f"    - {ex['reason']}")
                print()

    elif args.suggest:
        suggestion = suggest_regex_tune(args.suggest, args.min_dismissals)
        if not suggestion:
            print(f"No tune needed for {args.suggest} (< {args.min_dismissals} dismissals)")
        else:
            print(f"Regex tune suggestion for {suggestion['lesson_id']}:")
            print(f"  Total dismissals: {suggestion['total_dismissals']}")
            print(f"  Recommended action: {suggestion['recommended_action']}")
            if suggestion['patterns']:
                print(f"\n  Top patterns:")
                for p in suggestion['patterns'][:3]:
                    print(f"    - '{p['pattern']}' ({p['count']} times)")
                    print(f"      {p['suggestion']}")

    elif args.apply:
        result = apply_feedback_to_confidence(args.apply)
        if "error" in result:
            print(f"Error: {result['error']}")
        else:
            print(f"Applied feedback to {result['lesson_id']}:")
            print(f"  Confidence: {result['old_confidence']:.2f} -> {result['new_confidence']:.2f}")
            print(f"  Dismissals: {result['dismissals']}, Approvals: {result['approvals']}")
            print(f"  Adjustment: {result['adjustment']:+.2f}")

    elif args.needing_tune:
        lessons = get_lessons_needing_tune(args.min_dismissals)
        if not lessons:
            print(f"No lessons need tuning (min {args.min_dismissals} dismissals)")
        else:
            print(f"Found {len(lessons)} lessons needing tune:\n")
            for l in lessons:
                print(f"{l['lesson_id']}: {l['total_dismissals']} dismissals")
                print(f"  {l['recommended_action']}")
                print()

    elif args.auto_apply:
        results = auto_apply_feedback(args.min_dismissals, args.dry_run)
        if not results:
            print(f"No lessons to adjust (min {args.min_dismissals} dismissals)")
        else:
            print(f"{'DRY RUN: ' if args.dry_run else ''}Applied feedback to {len(results)} lessons:\n")
            for r in results:
                print(f"{r['lesson_id']}: {r['old_confidence']:.2f} -> {r['new_confidence']:.2f}")
                print(f"  Dismissals: {r['dismissals']}, Approvals: {r['approvals']}, Adjustment: {r['adjustment']:+.2f}")
                print()

    else:
        parser.print_help()