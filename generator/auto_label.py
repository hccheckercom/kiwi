"""Auto-label components using heuristics for quick ML training."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from memory.db import get_connection


def auto_label_high_confidence() -> int:
    """Auto-label components with high confidence as accepted.

    Heuristic: confidence >= 0.85 AND auto_applied = True → likely correct

    Returns:
        Number of components labeled
    """
    conn = get_connection()

    cursor = conn.execute('''
        UPDATE component_patterns
        SET user_accepted = 1
        WHERE user_accepted IS NULL
          AND confidence >= 0.85
          AND auto_applied = 1
    ''')

    high_conf_count = cursor.rowcount
    conn.commit()

    return high_conf_count


def auto_label_low_confidence() -> int:
    """Auto-label components with low confidence as rejected.

    Heuristic: confidence < 0.7 AND auto_applied = False → likely incorrect

    Returns:
        Number of components labeled
    """
    conn = get_connection()

    cursor = conn.execute('''
        UPDATE component_patterns
        SET user_accepted = 0
        WHERE user_accepted IS NULL
          AND confidence < 0.7
          AND auto_applied = 0
    ''')

    low_conf_count = cursor.rowcount
    conn.commit()

    return low_conf_count


def main():
    """Auto-label components using heuristics."""
    print("=== Auto-Labeling Components ===\n")

    # Get current stats
    conn = get_connection()
    cursor = conn.execute('SELECT COUNT(*) FROM component_patterns WHERE user_accepted IS NULL')
    unlabeled_before = cursor.fetchone()[0]

    print(f"Unlabeled components: {unlabeled_before}")

    # Auto-label high confidence
    print("\nLabeling high-confidence components (conf >= 0.85, auto_applied = True)...")
    high_count = auto_label_high_confidence()
    print(f"  Labeled as ACCEPTED: {high_count}")

    # Auto-label low confidence
    print("\nLabeling low-confidence components (conf < 0.6, auto_applied = False)...")
    low_count = auto_label_low_confidence()
    print(f"  Labeled as REJECTED: {low_count}")

    # Final stats
    cursor = conn.execute('SELECT COUNT(*) FROM component_patterns WHERE user_accepted IS NULL')
    unlabeled_after = cursor.fetchone()[0]

    cursor = conn.execute('SELECT COUNT(*) FROM component_patterns WHERE user_accepted IS NOT NULL')
    total_labeled = cursor.fetchone()[0]

    cursor = conn.execute('SELECT COUNT(*) FROM component_patterns WHERE user_accepted = 1')
    accepted = cursor.fetchone()[0]

    conn.close()

    print(f"\n=== Results ===")
    print(f"Total labeled: {high_count + low_count}")
    print(f"Remaining unlabeled: {unlabeled_after}")
    print(f"\nOverall stats:")
    print(f"  Total labeled: {total_labeled}")
    print(f"  Accepted: {accepted} ({accepted/total_labeled*100:.1f}%)")
    print(f"  Rejected: {total_labeled - accepted} ({(1-accepted/total_labeled)*100:.1f}%)")

    if total_labeled >= 20:
        print("\nReady to train ML classifier!")
        print("Run: python ml/train_classifier.py")
    else:
        print(f"\nNeed {20 - total_labeled} more labeled samples")
        print("Run: python label_components.py for manual labeling")


if __name__ == '__main__':
    main()
