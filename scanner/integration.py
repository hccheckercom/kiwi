"""Scanner integration for P1-P5 features.

This module provides hooks to integrate P1-P5 features into the scanner workflow:
1. Reset decay timer when violation detected
2. Deduplicate violations from correlated lessons
3. Record A/B test results during scans
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))


def reset_decay_on_violation(lesson_id: str) -> None:
    """P2: Reset decay timer when violation detected.

    Called automatically when a violation is found during scan.
    """
    try:
        from agent.confidence_decay import reset_decay
        reset_decay(lesson_id)
    except Exception as e:
        # Don't break scanner if decay fails
        import sys
        print(f"[kiwi] reset_decay error: {e}", file=sys.stderr)


def deduplicate_violations(violations: List[Dict]) -> tuple:
    """P3: Remove duplicate violations from correlated lessons.

    Args:
        violations: List of violation dicts

    Returns:
        (kept_violations, removed_violations)
    """
    try:
        from agent.correlation import deduplicate_violations as dedup
        return dedup(violations)
    except Exception as e:
        # If dedup fails, return all violations
        import sys
        print(f"[kiwi] deduplicate_violations error: {e}", file=sys.stderr)
        return violations, []


def record_ab_test_results(scan_id: int, lesson_violations: Dict[str, Dict]) -> None:
    """P5: Record A/B test results for active tests.

    Args:
        scan_id: Scan ID from scan_history
        lesson_violations: Dict mapping lesson_id to violation stats
            {
                "LES-001": {
                    "true_positives": 10,
                    "false_positives": 2,
                    "false_negatives": 1,
                    "fix_success": 8,
                    "fix_failure": 2
                }
            }
    """
    try:
        from agent.ab_testing import get_active_tests, record_ab_result

        active_tests = get_active_tests()

        for test in active_tests:
            lesson_id = test['lesson_id']

            if lesson_id in lesson_violations:
                stats = lesson_violations[lesson_id]

                # Record for both baseline and variant
                # In real implementation, you'd run both patterns and compare
                # For now, we record the same stats for both (placeholder)
                record_ab_result(
                    test['test_id'],
                    'baseline',
                    scan_id,
                    stats.get('true_positives', 0),
                    stats.get('false_positives', 0),
                    stats.get('false_negatives', 0),
                    stats.get('fix_success', 0),
                    stats.get('fix_failure', 0)
                )

                # TODO: Run variant pattern and record actual variant stats
                # For now, using same stats as placeholder
                record_ab_result(
                    test['test_id'],
                    'variant',
                    scan_id,
                    stats.get('true_positives', 0),
                    stats.get('false_positives', 0),
                    stats.get('false_negatives', 0),
                    stats.get('fix_success', 0),
                    stats.get('fix_failure', 0)
                )
    except Exception as e:
        # Don't break scanner if A/B recording fails
        import sys
        print(f"[kiwi] record_ab_test error: {e}", file=sys.stderr)


def apply_scanner_integrations(violations: List[Dict], scan_id: Optional[int] = None) -> List[Dict]:
    """Apply all scanner integrations.

    This is the main entry point called by the scanner after collecting violations.

    Args:
        violations: List of violation dicts
        scan_id: Optional scan ID for A/B test recording

    Returns:
        Deduplicated violations list
    """
    # P2: Reset decay timer for each lesson that fired
    lesson_ids = set(v.get('lesson_id') for v in violations if v.get('lesson_id'))
    for lesson_id in lesson_ids:
        reset_decay_on_violation(lesson_id)

    # P3: Deduplicate violations from correlated lessons
    kept, removed = deduplicate_violations(violations)

    # P5: Record A/B test results (if scan_id provided)
    if scan_id:
        # Build lesson_violations dict
        lesson_violations = {}
        for v in kept:
            lesson_id = v.get('lesson_id')
            if lesson_id:
                if lesson_id not in lesson_violations:
                    lesson_violations[lesson_id] = {
                        'true_positives': 0,
                        'false_positives': 0,
                        'false_negatives': 0,
                        'fix_success': 0,
                        'fix_failure': 0
                    }
                # Increment TP (assuming all violations are TP for now)
                lesson_violations[lesson_id]['true_positives'] += 1

        record_ab_test_results(scan_id, lesson_violations)

    return kept
