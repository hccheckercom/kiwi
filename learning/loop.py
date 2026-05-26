"""Learning Loop — Hook integration for active pattern learning"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from .miner import mine_patterns
from .anomaly import detect_anomalies
from .generator import generate_lesson
from memory.db import get_recent_violations, get_suggested_lessons


def on_scan_complete(scan_id: int, path: str, violations_count: int):
    """
    Hook called after scan completion.

    Triggers pattern mining if violations > threshold.
    """
    # Mine patterns after every scan (user chose this option)
    if violations_count >= 1:
        patterns = mine_patterns(
            min_occurrences=2,
            similarity_threshold=0.8,
            lookback_days=30,
            path=path
        )

        # Auto-promote high confidence suggestions
        promoted = promote_high_confidence_lessons(min_confidence=0.8)

        return {
            'patterns_mined': len(patterns),
            'suggestions_created': len(patterns),
            'auto_promoted': len(promoted)
        }

    return {'patterns_mined': 0}


def on_fix_applied(lesson_id: str, file: str, success: bool):
    """
    Hook called after fix is applied.

    Updates confidence and triggers pattern refinement if needed.
    """
    from memory.confidence import record_fix_outcome, get_confidence
    from .refiner import refine_noisy_pattern

    # Record fix outcome
    record_fix_outcome(lesson_id, success)

    # Trigger pattern refinement if FP rate high
    confidence = get_confidence(lesson_id)
    if confidence and confidence['confidence'] < 0.5:
        refined = refine_noisy_pattern(lesson_id, fp_threshold=0.3)
        if refined:
            return {'fix_recorded': True, 'pattern_refined': True, 'new_pattern': refined}

    return {'fix_recorded': True}


def promote_high_confidence_lessons(min_confidence: float = 0.7):
    """
    Auto-promote suggested lessons with high confidence.

    User chose auto-promote at confidence > 0.7.
    """
    suggestions = get_suggested_lessons(status='pending')
    promoted = []

    for suggestion in suggestions:
        confidence = suggestion.get('confidence', 0.0)

        # Auto-promote if confidence > threshold
        if confidence >= min_confidence:
            lesson_id = generate_lesson(suggestion['id'])
            if lesson_id:
                promoted.append(lesson_id)

    # Run dedup after 10 new lessons
    if len(promoted) >= 10:
        from .dedup import find_duplicate_lessons, merge_lessons
        clusters = find_duplicate_lessons(similarity_threshold=0.9)
        for cluster in clusters:
            merge_lessons(cluster)

    return promoted


def detect_and_suggest_anomalies(lookback_days: int = 7):
    """
    Detect anomalies in recent violations and create suggestions.

    User chose high recall mode.
    """
    violations = get_recent_violations(lookback_days)

    if not violations:
        return []

    # Detect anomalies with high recall (min_confidence=0.5)
    anomalies = detect_anomalies(violations, min_confidence=0.5)

    # Insert anomalies as suggested lessons
    from memory.db import get_connection
    from datetime import datetime, timezone

    conn = get_connection()
    try:
        inserted = []

        for anomaly in anomalies:
            cursor = conn.execute("""
                INSERT INTO suggested_lessons
                (pattern, scope, category, severity, example_file, example_line, example_code, suggested_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (
                anomaly.pattern,
                '**/*.php',  # Default scope
                anomaly.suggested_category,
                anomaly.suggested_severity,
                anomaly.example_file,
                anomaly.example_line,
                anomaly.match_text,
                datetime.now(timezone.utc).isoformat()
            ))
            inserted.append(cursor.lastrowid)

        conn.commit()
    finally:
        conn.close()

    return inserted
