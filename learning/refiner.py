"""Pattern Refinement Engine — Tự động cải thiện patterns khi FP rate cao"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Set, Optional
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.db import get_connection
from memory.confidence import get_confidence


def refine_noisy_pattern(lesson_id: str, fp_threshold: float = 0.3) -> Optional[str]:
    """
    Refine pattern khi FP rate > threshold.

    Algorithm:
    1. Get false positives from memory
    2. Extract common tokens from FPs
    3. Add negative lookahead to pattern
    4. Test refined pattern on history
    5. Update lesson if accuracy improves

    Args:
        lesson_id: Lesson ID to refine
        fp_threshold: FP rate threshold (default 0.3 = 30%)

    Returns: refined_pattern if successful, None if failed
    """
    confidence = get_confidence(lesson_id)
    if not confidence:
        return None

    fp_rate = confidence['false_positive_count'] / max(confidence['total_hits'], 1)
    if fp_rate < fp_threshold:
        return None

    fps = _get_false_positives(lesson_id)
    if len(fps) < 3:
        return None

    current_pattern = _get_lesson_pattern(lesson_id)
    if not current_pattern:
        return None

    exclude_tokens = extract_fp_tokens(fps)
    if not exclude_tokens:
        return None

    refined_pattern = add_negative_lookahead(current_pattern, exclude_tokens)

    accuracy_before = 1.0 - fp_rate
    accuracy_after = test_pattern_accuracy(refined_pattern, lesson_id)

    if accuracy_after > accuracy_before + 0.1:
        update_lesson_pattern(
            lesson_id,
            refined_pattern,
            f"Auto-refined: FP rate {fp_rate:.1%} → {1-accuracy_after:.1%}"
        )
        return refined_pattern

    return None


def extract_fp_tokens(fps: List[Dict]) -> Set[str]:
    """
    Extract common tokens from false positives.

    Returns: Set of tokens that appear in ≥50% of FPs
    """
    if not fps:
        return set()

    all_tokens = []
    for fp in fps:
        match_text = fp.get('match_text', '')
        tokens = re.findall(r'\b\w+\b', match_text.lower())
        all_tokens.extend(tokens)

    token_counts = Counter(all_tokens)
    threshold = len(fps) * 0.5

    common_tokens = {token for token, count in token_counts.items() if count >= threshold}
    return common_tokens


def add_negative_lookahead(pattern: str, exclude_tokens: Set[str]) -> str:
    """
    Add negative lookahead to pattern.

    Example:
    pattern: "echo\s+\$"
    exclude_tokens: {"esc_html", "sanitize"}
    result: "echo\s+\$(?!.*(?:esc_html|sanitize))"
    """
    if not exclude_tokens:
        return pattern

    lookahead = '(?!.*(?:' + '|'.join(re.escape(t) for t in exclude_tokens) + '))'

    # Add lookahead after the main pattern
    refined = pattern + lookahead
    return refined


def test_pattern_accuracy(pattern: str, lesson_id: str) -> float:
    """
    Test refined pattern on scan history.

    Returns: Accuracy score (0-1)
    """
    conn = get_connection()
    try:

        # Get all violations for this lesson
        cursor = conn.execute('''
            SELECT match_text FROM violations WHERE lesson_id = ?
        ''', (lesson_id,))

        violations = [row[0] for row in cursor.fetchall()]

        # Get false positives
        cursor = conn.execute('''
            SELECT match_text FROM false_positives WHERE lesson_id = ? AND active = 1
        ''', (lesson_id,))

        fps = [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()

    if not violations:
        return 0.0

    # Test pattern against violations
    try:
        regex = re.compile(pattern)

        # Count true positives (violations that still match)
        tp = sum(1 for v in violations if v and regex.search(v))

        # Count false positives (FPs that still match)
        fp = sum(1 for f in fps if f and regex.search(f))

        # Calculate accuracy
        total = len(violations) + len(fps)
        if total == 0:
            return 0.0

        accuracy = (tp + (len(fps) - fp)) / total
        return accuracy

    except re.error:
        return 0.0


def update_lesson_pattern(lesson_id: str, new_pattern: str, reason: str):
    """
    Update lesson file with refined pattern.

    Also tracks refinement in database.
    """
    kiwi_dir = Path(__file__).parent.parent
    lessons_dir = kiwi_dir / 'lessons'

    # Find lesson file
    lesson_file = _find_lesson_file(lessons_dir, lesson_id)
    if not lesson_file:
        return

    # Read current content
    content = lesson_file.read_text(encoding='utf-8')

    # Extract old pattern
    old_pattern = _extract_pattern(content)
    if not old_pattern:
        return

    # Update pattern in content
    updated_content = re.sub(
        r'(pattern:\s*)["\']?[^"\'\n]+["\']?',
        f'pattern: "{new_pattern}"',
        content
    )

    # Add refinement note
    refinement_note = f"\n<!-- Refined: {reason} -->\n"
    updated_content += refinement_note

    # Write updated content
    lesson_file.write_text(updated_content, encoding='utf-8')

    # Track refinement in database
    _track_refinement(lesson_id, old_pattern, new_pattern, reason)


def _get_false_positives(lesson_id: str) -> List[Dict]:
    """Get false positives from database"""
    conn = get_connection()
    try:
        cursor = conn.execute('''
            SELECT file, line, match_text, reason
            FROM false_positives
            WHERE lesson_id = ? AND active = 1
        ''', (lesson_id,))

        fps = []
        for row in cursor.fetchall():
            fps.append({
                'file': row[0],
                'line': row[1],
                'match_text': row[2],
                'reason': row[3]
            })

    finally:
        conn.close()
    return fps


def _get_lesson_pattern(lesson_id: str) -> Optional[str]:
    """Get current pattern from lesson file"""
    kiwi_dir = Path(__file__).parent.parent
    lessons_dir = kiwi_dir / 'lessons'

    lesson_file = _find_lesson_file(lessons_dir, lesson_id)
    if not lesson_file:
        return None

    content = lesson_file.read_text(encoding='utf-8')
    return _extract_pattern(content)


def _find_lesson_file(lessons_dir: Path, lesson_id: str) -> Optional[Path]:
    """Find lesson file by ID"""
    for category_dir in lessons_dir.iterdir():
        if category_dir.is_dir() and not category_dir.name.startswith('_'):
            lesson_file = category_dir / f'{lesson_id}.md'
            if lesson_file.exists():
                return lesson_file
    return None


def _extract_pattern(content: str) -> Optional[str]:
    """Extract pattern from lesson content"""
    match = re.search(r'pattern:\s*["\']?([^"\'\n]+)["\']?', content)
    if match:
        return match.group(1).strip()
    return None


def _track_refinement(lesson_id: str, old_pattern: str, new_pattern: str, reason: str):
    """Track refinement in database"""
    conn = get_connection()
    try:

        # Get FP rates
        confidence = get_confidence(lesson_id)
        fp_rate_before = confidence['false_positive_count'] / max(confidence['total_hits'], 1) if confidence else 0.0

        # Insert refinement record
        conn.execute('''
            INSERT INTO pattern_refinements
            (lesson_id, old_pattern, new_pattern, reason, fp_rate_before, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            lesson_id,
            old_pattern,
            new_pattern,
            reason,
            fp_rate_before,
            datetime.now(timezone.utc).isoformat()
        ))

        conn.commit()
    finally:
        conn.close()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Refine noisy patterns')
    parser.add_argument('lesson_id', help='Lesson ID to refine')
    parser.add_argument('--threshold', type=float, default=0.3, help='FP rate threshold')

    args = parser.parse_args()

    print(f'Refining {args.lesson_id} with threshold {args.threshold}...')

    refined = refine_noisy_pattern(args.lesson_id, args.threshold)

    if refined:
        print(f'✓ Pattern refined: {refined}')
    else:
        print('✗ No refinement needed or failed')