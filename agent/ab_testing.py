"""P5: A/B Testing Framework.

Test 2 versions của lesson song song để tìm version tốt hơn.
Tự động chọn winner sau N scans dựa trên precision/recall/fix_rate.

A/B Testing rules:
- Create test với 2 versions (baseline vs variant)
- Track metrics cho mỗi version: precision, recall, fix_rate
- Sau N scans (default 100), compare metrics và chọn winner
- Rollback nếu variant worse than baseline
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.db import get_connection


def _now():
    return datetime.now(timezone.utc).isoformat()


def create_ab_test(
    lesson_id: str,
    baseline_pattern: str,
    variant_pattern: str,
    description: str = "",
    target_scans: int = 100
) -> Dict:
    """Create A/B test for a lesson.

    Args:
        lesson_id: Lesson to test
        baseline_pattern: Current pattern (version A)
        variant_pattern: New pattern to test (version B)
        description: Test description
        target_scans: Number of scans before deciding winner (default 100)

    Returns:
        {
            "test_id": int,
            "lesson_id": str,
            "status": "active",
            "created_at": str
        }
    """
    conn = get_connection()
    try:

        # Check if test already exists
        existing = conn.execute("""
            SELECT * FROM ab_tests
            WHERE lesson_id = ?
            AND status = 'active'
        """, (lesson_id,)).fetchone()

        if existing:
            return {
                "error": f"Active A/B test already exists for {lesson_id}",
                "test_id": existing["id"]
            }

        # Create test
        conn.execute("""
            INSERT INTO ab_tests
            (lesson_id, baseline_pattern, variant_pattern, description,
             target_scans, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'active', ?)
        """, (lesson_id, baseline_pattern, variant_pattern, description, target_scans, _now()))

        test_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.commit()
    finally:
        conn.close()

    return {
        "test_id": test_id,
        "lesson_id": lesson_id,
        "status": "active",
        "created_at": _now()
    }


def record_ab_result(
    test_id: int,
    version: str,
    scan_id: int,
    true_positives: int,
    false_positives: int,
    false_negatives: int,
    fix_success: int,
    fix_failure: int
) -> Dict:
    """Record scan result for A/B test version.

    Args:
        test_id: A/B test ID
        version: "baseline" or "variant"
        scan_id: Scan ID from scan_history
        true_positives: TP count
        false_positives: FP count
        false_negatives: FN count
        fix_success: Successful fixes
        fix_failure: Failed fixes

    Returns:
        {
            "result_id": int,
            "test_id": int,
            "version": str
        }
    """
    conn = get_connection()
    try:

        conn.execute("""
            INSERT INTO ab_results
            (test_id, version, scan_id, true_positives, false_positives,
             false_negatives, fix_success, fix_failure, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (test_id, version, scan_id, true_positives, false_positives,
              false_negatives, fix_success, fix_failure, _now()))

        result_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.commit()
    finally:
        conn.close()

    return {
        "result_id": result_id,
        "test_id": test_id,
        "version": version
    }


def calculate_ab_metrics(test_id: int) -> Dict:
    """Calculate metrics for both versions of A/B test.

    Returns:
        {
            "test_id": int,
            "baseline": {
                "scans": int,
                "precision": float,
                "recall": float,
                "fix_rate": float,
                "f1_score": float
            },
            "variant": {...},
            "winner": "baseline" | "variant" | "tie" | None,
            "confidence": float  # 0-1, how confident we are in winner
        }
    """
    conn = get_connection()
    try:

        # Get test info
        test = conn.execute("""
            SELECT * FROM ab_tests WHERE id = ?
        """, (test_id,)).fetchone()

        if not test:
            return {"error": f"Test {test_id} not found"}

        # Get results for baseline
        baseline_rows = conn.execute("""
            SELECT * FROM ab_results
            WHERE test_id = ? AND version = 'baseline'
        """, (test_id,)).fetchall()

        # Get results for variant
        variant_rows = conn.execute("""
            SELECT * FROM ab_results
            WHERE test_id = ? AND version = 'variant'
        """, (test_id,)).fetchall()

    finally:
        conn.close()

    def calc_metrics(rows):
        if not rows:
            return {
                "scans": 0,
                "precision": 0.0,
                "recall": 0.0,
                "fix_rate": 0.0,
                "f1_score": 0.0
            }

        tp = sum(r["true_positives"] for r in rows)
        fp = sum(r["false_positives"] for r in rows)
        fn = sum(r["false_negatives"] for r in rows)
        fix_success = sum(r["fix_success"] for r in rows)
        fix_failure = sum(r["fix_failure"] for r in rows)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        fix_rate = fix_success / (fix_success + fix_failure) if (fix_success + fix_failure) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        return {
            "scans": len(rows),
            "precision": round(precision, 2),
            "recall": round(recall, 2),
            "fix_rate": round(fix_rate, 2),
            "f1_score": round(f1_score, 2)
        }

    baseline_metrics = calc_metrics(baseline_rows)
    variant_metrics = calc_metrics(variant_rows)

    # Determine winner based on F1 score (balanced precision + recall)
    winner = None
    confidence = 0.0

    if baseline_metrics["scans"] >= test["target_scans"] and variant_metrics["scans"] >= test["target_scans"]:
        baseline_f1 = baseline_metrics["f1_score"]
        variant_f1 = variant_metrics["f1_score"]

        diff = abs(baseline_f1 - variant_f1)

        if diff < 0.05:
            winner = "tie"
            confidence = 1.0 - diff / 0.05
        elif variant_f1 > baseline_f1:
            winner = "variant"
            confidence = min(1.0, diff / 0.2)
        else:
            winner = "baseline"
            confidence = min(1.0, diff / 0.2)

    return {
        "test_id": test_id,
        "lesson_id": test["lesson_id"],
        "baseline": baseline_metrics,
        "variant": variant_metrics,
        "winner": winner,
        "confidence": round(confidence, 2),
        "target_scans": test["target_scans"]
    }


def finalize_ab_test(test_id: int, force_winner: Optional[str] = None) -> Dict:
    """Finalize A/B test and apply winner.

    Args:
        test_id: Test ID
        force_winner: Force specific winner ("baseline" or "variant"), or None for auto

    Returns:
        {
            "test_id": int,
            "winner": str,
            "action": "applied" | "rolled_back" | "no_change",
            "metrics": dict
        }
    """
    metrics = calculate_ab_metrics(test_id)

    if "error" in metrics:
        return metrics

    # Determine winner
    if force_winner:
        winner = force_winner
    else:
        winner = metrics.get("winner")

    if not winner or winner == "tie":
        return {
            "test_id": test_id,
            "winner": "tie",
            "action": "no_change",
            "message": "No clear winner - keeping baseline",
            "metrics": metrics
        }

    conn = get_connection()
    try:

        # Get test info
        test = conn.execute("""
            SELECT * FROM ab_tests WHERE id = ?
        """, (test_id,)).fetchone()

        # Update test status
        conn.execute("""
            UPDATE ab_tests
            SET status = 'completed',
                winner = ?,
                completed_at = ?
            WHERE id = ?
        """, (winner, _now(), test_id))

        conn.commit()
    finally:
        conn.close()

    action = "applied" if winner == "variant" else "rolled_back"

    return {
        "test_id": test_id,
        "lesson_id": test["lesson_id"],
        "winner": winner,
        "action": action,
        "metrics": metrics,
        "message": f"Winner: {winner} - {action} pattern"
    }


def get_active_tests() -> List[Dict]:
    """Get all active A/B tests."""
    conn = get_connection()
    try:

        rows = conn.execute("""
            SELECT * FROM ab_tests
            WHERE status = 'active'
            ORDER BY created_at DESC
        """).fetchall()

    finally:
        conn.close()

    results = []
    for row in rows:
        metrics = calculate_ab_metrics(row["id"])
        results.append({
            "test_id": row["id"],
            "lesson_id": row["lesson_id"],
            "description": row["description"],
            "target_scans": row["target_scans"],
            "created_at": row["created_at"],
            "metrics": metrics
        })

    return results


def get_test_history(lesson_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
    """Get A/B test history."""
    conn = get_connection()
    try:

        if lesson_id:
            rows = conn.execute("""
                SELECT * FROM ab_tests
                WHERE lesson_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (lesson_id, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM ab_tests
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()

    finally:
        conn.close()

    return [dict(row) for row in rows]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="A/B testing framework")
    parser.add_argument("--create", metavar="LESSON_ID", help="Create A/B test for lesson")
    parser.add_argument("--baseline", help="Baseline pattern (for --create)")
    parser.add_argument("--variant", help="Variant pattern (for --create)")
    parser.add_argument("--description", default="", help="Test description")
    parser.add_argument("--target-scans", type=int, default=100, help="Target scans (default 100)")
    parser.add_argument("--metrics", type=int, metavar="TEST_ID", help="Show metrics for test")
    parser.add_argument("--finalize", type=int, metavar="TEST_ID", help="Finalize test and apply winner")
    parser.add_argument("--force-winner", choices=["baseline", "variant"], help="Force specific winner")
    parser.add_argument("--active", action="store_true", help="List active tests")
    parser.add_argument("--history", action="store_true", help="Show test history")
    parser.add_argument("--lesson", help="Filter history by lesson")

    args = parser.parse_args()

    if args.create:
        if not args.baseline or not args.variant:
            print("Error: --baseline and --variant required for --create")
            parser.print_help()
        else:
            result = create_ab_test(
                args.create,
                args.baseline,
                args.variant,
                args.description,
                args.target_scans
            )
            if "error" in result:
                print(f"Error: {result['error']}")
            else:
                print(f"Created A/B test {result['test_id']} for {result['lesson_id']}")
                print(f"Target: {args.target_scans} scans per version")

    elif args.metrics is not None:
        metrics = calculate_ab_metrics(args.metrics)
        if "error" in metrics:
            print(f"Error: {metrics['error']}")
        else:
            print(f"A/B Test {metrics['test_id']}: {metrics['lesson_id']}")
            print(f"\nBaseline:")
            print(f"  Scans: {metrics['baseline']['scans']}/{metrics['target_scans']}")
            print(f"  Precision: {metrics['baseline']['precision']:.2f}")
            print(f"  Recall: {metrics['baseline']['recall']:.2f}")
            print(f"  Fix rate: {metrics['baseline']['fix_rate']:.2f}")
            print(f"  F1 score: {metrics['baseline']['f1_score']:.2f}")
            print(f"\nVariant:")
            print(f"  Scans: {metrics['variant']['scans']}/{metrics['target_scans']}")
            print(f"  Precision: {metrics['variant']['precision']:.2f}")
            print(f"  Recall: {metrics['variant']['recall']:.2f}")
            print(f"  Fix rate: {metrics['variant']['fix_rate']:.2f}")
            print(f"  F1 score: {metrics['variant']['f1_score']:.2f}")
            if metrics['winner']:
                print(f"\nWinner: {metrics['winner']} (confidence: {metrics['confidence']:.2f})")

    elif args.finalize is not None:
        result = finalize_ab_test(args.finalize, args.force_winner)
        if "error" in result:
            print(f"Error: {result['error']}")
        else:
            print(f"Finalized test {result['test_id']}: {result['lesson_id']}")
            print(f"Winner: {result['winner']}")
            print(f"Action: {result['action']}")
            print(f"Message: {result['message']}")

    elif args.active:
        tests = get_active_tests()
        if not tests:
            print("No active A/B tests")
        else:
            print(f"Active A/B tests ({len(tests)}):\n")
            for t in tests:
                print(f"Test {t['test_id']}: {t['lesson_id']}")
                print(f"  Description: {t['description']}")
                print(f"  Progress: baseline {t['metrics']['baseline']['scans']}/{t['target_scans']}, variant {t['metrics']['variant']['scans']}/{t['target_scans']}")
                if t['metrics']['winner']:
                    print(f"  Current leader: {t['metrics']['winner']}")
                print()

    elif args.history:
        history = get_test_history(args.lesson)
        if not history:
            print("No test history found")
        else:
            print(f"A/B test history ({len(history)}):\n")
            for h in history:
                print(f"Test {h['id']}: {h['lesson_id']}")
                print(f"  Status: {h['status']}")
                if h['winner']:
                    print(f"  Winner: {h['winner']}")
                print(f"  Created: {h['created_at']}")
                print()

    else:
        parser.print_help()