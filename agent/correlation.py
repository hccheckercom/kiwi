"""P3: Cross-Lesson Correlation.

Phát hiện lessons luôn cùng fire trên cùng file/line (duplicate noise).
Gộp hoặc đánh dấu "related" để giảm violations trùng lặp.

Correlation rules:
- Nếu 2 lessons luôn cùng fire trên cùng file/line → tính correlation score
- Correlation > 0.80 → đánh dấu "related" hoặc suggest merge
- Chỉ hiện 1 violation thay vì 2-3 violations trùng lặp
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.db import get_connection


def calculate_correlation(lesson_a: str, lesson_b: str) -> Dict:
    """Calculate correlation between 2 lessons.

    Returns:
        {
            "lesson_a": str,
            "lesson_b": str,
            "co_occurrences": int,  # times both fired on same file:line
            "lesson_a_total": int,  # total times lesson_a fired
            "lesson_b_total": int,  # total times lesson_b fired
            "correlation": float,  # co_occurrences / min(a_total, b_total)
            "jaccard": float,  # co_occurrences / (a_total + b_total - co_occurrences)
        }
    """
    conn = get_connection()
    try:

        # Get all violations for lesson_a
        rows_a = conn.execute("""
            SELECT DISTINCT file, line
            FROM violations
            WHERE lesson_id = ?
        """, (lesson_a,)).fetchall()

        # Get all violations for lesson_b
        rows_b = conn.execute("""
            SELECT DISTINCT file, line
            FROM violations
            WHERE lesson_id = ?
        """, (lesson_b,)).fetchall()

    finally:
        conn.close()

    if not rows_a or not rows_b:
        return {
            "lesson_a": lesson_a,
            "lesson_b": lesson_b,
            "co_occurrences": 0,
            "lesson_a_total": len(rows_a),
            "lesson_b_total": len(rows_b),
            "correlation": 0.0,
            "jaccard": 0.0,
            "message": "One or both lessons have no violations"
        }

    # Convert to sets of (file, line) tuples
    set_a = {(r["file"], r["line"]) for r in rows_a}
    set_b = {(r["file"], r["line"]) for r in rows_b}

    # Calculate co-occurrences (intersection)
    co_occurrences = len(set_a & set_b)

    # Correlation: co_occurrences / min(a_total, b_total)
    # High correlation means one is subset of the other
    correlation = co_occurrences / min(len(set_a), len(set_b)) if min(len(set_a), len(set_b)) > 0 else 0.0

    # Jaccard index: co_occurrences / union
    # More conservative measure
    union_size = len(set_a | set_b)
    jaccard = co_occurrences / union_size if union_size > 0 else 0.0

    return {
        "lesson_a": lesson_a,
        "lesson_b": lesson_b,
        "co_occurrences": co_occurrences,
        "lesson_a_total": len(set_a),
        "lesson_b_total": len(set_b),
        "correlation": round(correlation, 2),
        "jaccard": round(jaccard, 2),
    }


def find_correlated_lessons(min_correlation: float = 0.80, min_co_occurrences: int = 3) -> List[Dict]:
    """Find all pairs of lessons with high correlation.

    Args:
        min_correlation: Minimum correlation threshold (default 0.80)
        min_co_occurrences: Minimum co-occurrences required (default 3)

    Returns:
        List of correlation results sorted by correlation desc
    """
    conn = get_connection()
    try:

        # Get all lessons that have violations
        rows = conn.execute("""
            SELECT DISTINCT lesson_id
            FROM violations
            ORDER BY lesson_id
        """).fetchall()

    finally:
        conn.close()

    lesson_ids = [r["lesson_id"] for r in rows]

    if len(lesson_ids) < 2:
        return []

    results = []

    # Calculate correlation for all pairs
    for i in range(len(lesson_ids)):
        for j in range(i + 1, len(lesson_ids)):
            lesson_a = lesson_ids[i]
            lesson_b = lesson_ids[j]

            corr = calculate_correlation(lesson_a, lesson_b)

            if corr["co_occurrences"] >= min_co_occurrences and corr["correlation"] >= min_correlation:
                results.append(corr)

    # Sort by correlation desc
    results.sort(key=lambda x: x["correlation"], reverse=True)

    return results


def mark_as_related(lesson_a: str, lesson_b: str, reason: str = "") -> Dict:
    """Mark two lessons as related in DB.

    Returns:
        {
            "lesson_a": str,
            "lesson_b": str,
            "action": "marked_related",
            "reason": str
        }
    """
    conn = get_connection()
    try:

        # Check if already marked
        existing = conn.execute("""
            SELECT * FROM lesson_relations
            WHERE (lesson_a = ? AND lesson_b = ?)
            OR (lesson_a = ? AND lesson_b = ?)
        """, (lesson_a, lesson_b, lesson_b, lesson_a)).fetchone()

        if existing:
            return {
                "lesson_a": lesson_a,
                "lesson_b": lesson_b,
                "action": "already_related",
                "message": "Lessons already marked as related"
            }

        # Insert relation
        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).isoformat()

        conn.execute("""
            INSERT INTO lesson_relations
            (lesson_a, lesson_b, relation_type, reason, timestamp)
            VALUES (?, ?, 'related', ?, ?)
        """, (lesson_a, lesson_b, reason, timestamp))

        conn.commit()
    finally:
        conn.close()

    return {
        "lesson_a": lesson_a,
        "lesson_b": lesson_b,
        "action": "marked_related",
        "reason": reason
    }


def get_related_lessons(lesson_id: str) -> List[str]:
    """Get all lessons related to a given lesson.

    Returns:
        List of related lesson IDs
    """
    conn = get_connection()
    try:

        rows = conn.execute("""
            SELECT lesson_a, lesson_b
            FROM lesson_relations
            WHERE lesson_a = ? OR lesson_b = ?
        """, (lesson_id, lesson_id)).fetchall()

    finally:
        conn.close()

    related = set()
    for row in rows:
        if row["lesson_a"] == lesson_id:
            related.add(row["lesson_b"])
        else:
            related.add(row["lesson_a"])

    return sorted(related)


def deduplicate_violations(violations: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Remove duplicate violations from related lessons.

    Args:
        violations: List of {lesson_id, file, line, ...}

    Returns:
        (kept_violations, removed_violations)
    """
    conn = get_connection()
    try:

        # Get all relations
        rows = conn.execute("""
            SELECT lesson_a, lesson_b FROM lesson_relations
        """).fetchall()

    finally:
        conn.close()

    # Build relation map
    relations = defaultdict(set)
    for row in rows:
        relations[row["lesson_a"]].add(row["lesson_b"])
        relations[row["lesson_b"]].add(row["lesson_a"])

    # Group violations by (file, line)
    location_map = defaultdict(list)
    for v in violations:
        key = (v["file"], v.get("line", 0))
        location_map[key].append(v)

    kept = []
    removed = []

    for location, viols in location_map.items():
        if len(viols) == 1:
            # Only 1 violation at this location, keep it
            kept.append(viols[0])
            continue

        # Multiple violations at same location
        # Check if any are related
        lesson_ids = [v["lesson_id"] for v in viols]

        # Find related pairs
        related_pairs = []
        for i in range(len(lesson_ids)):
            for j in range(i + 1, len(lesson_ids)):
                if lesson_ids[j] in relations.get(lesson_ids[i], set()):
                    related_pairs.append((i, j))

        if not related_pairs:
            # No relations, keep all
            kept.extend(viols)
            continue

        # Keep first violation, remove related ones
        kept.append(viols[0])
        for v in viols[1:]:
            if v["lesson_id"] in relations.get(viols[0]["lesson_id"], set()):
                removed.append(v)
            else:
                kept.append(v)

    return kept, removed


def auto_mark_correlated(min_correlation: float = 0.80, min_co_occurrences: int = 5, dry_run: bool = False) -> List[Dict]:
    """Automatically mark highly correlated lessons as related.

    Args:
        min_correlation: Minimum correlation threshold (default 0.80)
        min_co_occurrences: Minimum co-occurrences required (default 5)
        dry_run: If True, don't apply changes

    Returns:
        List of marked relations
    """
    correlated = find_correlated_lessons(min_correlation, min_co_occurrences)

    results = []
    for corr in correlated:
        reason = f"Auto-marked: correlation {corr['correlation']:.2f}, {corr['co_occurrences']} co-occurrences"

        if not dry_run:
            result = mark_as_related(corr["lesson_a"], corr["lesson_b"], reason)
        else:
            result = {
                "lesson_a": corr["lesson_a"],
                "lesson_b": corr["lesson_b"],
                "action": "would_mark_related",
                "reason": reason,
                "correlation": corr["correlation"],
                "co_occurrences": corr["co_occurrences"]
            }

        results.append(result)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Cross-lesson correlation analysis")
    parser.add_argument("--find", action="store_true", help="Find correlated lessons")
    parser.add_argument("--min-correlation", type=float, default=0.80, help="Min correlation (default 0.80)")
    parser.add_argument("--min-co-occurrences", type=int, default=3, help="Min co-occurrences (default 3)")
    parser.add_argument("--calculate", nargs=2, metavar=("LESSON_A", "LESSON_B"), help="Calculate correlation between 2 lessons")
    parser.add_argument("--mark", nargs=2, metavar=("LESSON_A", "LESSON_B"), help="Mark 2 lessons as related")
    parser.add_argument("--related", metavar="LESSON_ID", help="Get related lessons")
    parser.add_argument("--auto-mark", action="store_true", help="Auto-mark highly correlated lessons")
    parser.add_argument("--dry-run", action="store_true", help="Preview without applying")

    args = parser.parse_args()

    if args.find:
        results = find_correlated_lessons(args.min_correlation, args.min_co_occurrences)
        if not results:
            print(f"No correlated lessons found (correlation >= {args.min_correlation}, co-occurrences >= {args.min_co_occurrences})")
        else:
            print(f"Found {len(results)} correlated lesson pairs:\n")
            for r in results:
                print(f"{r['lesson_a']} <-> {r['lesson_b']}")
                print(f"  Correlation: {r['correlation']:.2f}")
                print(f"  Jaccard: {r['jaccard']:.2f}")
                print(f"  Co-occurrences: {r['co_occurrences']}")
                print(f"  Total: {r['lesson_a']}: {r['lesson_a_total']}, {r['lesson_b']}: {r['lesson_b_total']}")
                print()

    elif args.calculate:
        lesson_a, lesson_b = args.calculate
        result = calculate_correlation(lesson_a, lesson_b)

        if "message" in result:
            print(f"{result['message']}")
        else:
            print(f"Correlation between {lesson_a} and {lesson_b}:")
            print(f"  Correlation: {result['correlation']:.2f}")
            print(f"  Jaccard: {result['jaccard']:.2f}")
            print(f"  Co-occurrences: {result['co_occurrences']}")
            print(f"  {lesson_a} total: {result['lesson_a_total']}")
            print(f"  {lesson_b} total: {result['lesson_b_total']}")

    elif args.mark:
        lesson_a, lesson_b = args.mark
        result = mark_as_related(lesson_a, lesson_b, reason="Manually marked via CLI")
        print(f"{result['action']}: {lesson_a} <-> {lesson_b}")
        if result.get("message"):
            print(f"  {result['message']}")

    elif args.related:
        related = get_related_lessons(args.related)
        if not related:
            print(f"No related lessons found for {args.related}")
        else:
            print(f"Lessons related to {args.related}:")
            for r in related:
                print(f"  - {r}")

    elif args.auto_mark:
        results = auto_mark_correlated(args.min_correlation, args.min_co_occurrences, args.dry_run)
        if not results:
            print(f"No lessons to mark (correlation >= {args.min_correlation}, co-occurrences >= {args.min_co_occurrences})")
        else:
            print(f"{'DRY RUN: ' if args.dry_run else ''}Marked {len(results)} lesson pairs:\n")
            for r in results:
                print(f"{r['lesson_a']} <-> {r['lesson_b']}")
                print(f"  {r['reason']}")
                if 'correlation' in r:
                    print(f"  Correlation: {r['correlation']:.2f}, Co-occurrences: {r['co_occurrences']}")
                print()

    else:
        parser.print_help()