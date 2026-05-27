"""Interactive labeling tool for component patterns."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from memory.db import get_connection


def show_component(comp_id: int, component_type: str, html_snippet: str,
                   confidence: float, auto_applied: bool) -> None:
    """Display component details."""
    print(f"\n{'='*80}")
    print(f"Component ID: {comp_id}")
    print(f"Type: {component_type}")
    print(f"Confidence: {confidence:.2f}")
    print(f"Auto-applied: {auto_applied}")
    print(f"\nHTML Snippet (first 500 chars):")
    print("-" * 80)
    print(html_snippet[:500])
    if len(html_snippet) > 500:
        print(f"\n... ({len(html_snippet) - 500} more chars)")
    print("=" * 80)


def label_component(comp_id: int, accepted: bool) -> None:
    """Save label to database."""
    conn = get_connection()
    conn.execute('''
        UPDATE component_patterns
        SET user_accepted = ?
        WHERE id = ?
    ''', (1 if accepted else 0, comp_id))
    conn.commit()
    conn.close()


def main():
    """Interactive labeling loop."""
    conn = get_connection()

    # Get unlabeled components
    cursor = conn.execute('''
        SELECT id, component_type, html_snippet, confidence, auto_applied
        FROM component_patterns
        WHERE user_accepted IS NULL
        ORDER BY id
    ''')

    components = cursor.fetchall()
    conn.close()

    if not components:
        print("No unlabeled components found!")
        return

    print(f"Found {len(components)} unlabeled components")
    print("\nInstructions:")
    print("  y = accept (component is correct)")
    print("  n = reject (component is incorrect)")
    print("  s = skip (label later)")
    print("  q = quit")

    labeled_count = 0

    for comp_id, comp_type, html_snippet, confidence, auto_applied in components:
        show_component(comp_id, comp_type, html_snippet, confidence, auto_applied)

        while True:
            choice = input("\nLabel (y/n/s/q): ").strip().lower()

            if choice == 'y':
                label_component(comp_id, True)
                print("Accepted")
                labeled_count += 1
                break
            elif choice == 'n':
                label_component(comp_id, False)
                print("Rejected")
                labeled_count += 1
                break
            elif choice == 's':
                print("Skipped")
                break
            elif choice == 'q':
                print(f"\nLabeled {labeled_count} components")
                return
            else:
                print("Invalid choice. Use y/n/s/q")

    print(f"\n=== Labeling Complete ===")
    print(f"Labeled: {labeled_count}/{len(components)}")

    # Show final stats
    conn = get_connection()
    cursor = conn.execute('''
        SELECT COUNT(*) FROM component_patterns WHERE user_accepted IS NOT NULL
    ''')
    total_labeled = cursor.fetchone()[0]

    cursor = conn.execute('''
        SELECT COUNT(*) FROM component_patterns WHERE user_accepted = 1
    ''')
    accepted = cursor.fetchone()[0]

    conn.close()

    print(f"\nTotal labeled: {total_labeled}")
    print(f"Accepted: {accepted} ({accepted/total_labeled*100:.1f}%)")
    print(f"Rejected: {total_labeled - accepted} ({(1-accepted/total_labeled)*100:.1f}%)")

    if total_labeled >= 20:
        print("\nReady to train ML classifier!")
        print("Run: python ml/train_classifier.py")


if __name__ == '__main__':
    main()
