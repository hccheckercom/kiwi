#!/usr/bin/env python3
"""
A/B test: Rule-based detector vs ML classifier.
Compare metrics to determine which approach is better.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.db import get_connection
from ml_retrain import MLRetrainer
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix


def rule_based_detector(html: str, component_type: str) -> bool:
    """
    Rule-based component detection using heuristics.

    Returns True if component should be accepted.
    """
    import re

    # Rule 1: High-confidence component types
    high_confidence_types = ['header', 'footer', 'hero', 'nav']
    if component_type in high_confidence_types:
        return True

    # Rule 2: Has semantic tags
    semantic_tags = ['header', 'nav', 'section', 'article', 'footer']
    if any(f'<{tag}' in html.lower() for tag in semantic_tags):
        return True

    # Rule 3: Has interactive elements
    interactive_tags = ['button', 'a', 'input']
    if any(f'<{tag}' in html.lower() for tag in interactive_tags):
        return True

    # Rule 4: Has Tailwind layout classes
    layout_classes = ['flex', 'grid', 'container']
    if any(cls in html for cls in layout_classes):
        return True

    # Rule 5: Reasonable size (not too small, not too large)
    html_length = len(html)
    if 100 < html_length < 5000:
        return True

    # Default: reject
    return False


def export_test_data():
    """Export labeled samples for testing."""
    conn = get_connection()
    cursor = conn.execute('''
        SELECT html_snippet, component_type, user_accepted
        FROM component_patterns
        WHERE user_accepted IS NOT NULL
    ''')

    samples = []
    labels = []

    for row in cursor.fetchall():
        html = row[0]
        comp_type = row[1]
        accepted = row[2]

        samples.append((html, comp_type))
        labels.append(1 if accepted == 1 else 0)

    conn.close()
    return samples, labels


def main():
    print("=== A/B Test: Rule-Based vs ML Classifier ===\n")

    # Load test data
    samples, y_true = export_test_data()
    print(f"Test set: {len(samples)} labeled samples")
    print(f"  Positive: {sum(y_true)}")
    print(f"  Negative: {len(y_true) - sum(y_true)}")
    print()

    # Test 1: Rule-based detector
    print("Testing Rule-Based Detector...")
    y_pred_rules = []
    for html, comp_type in samples:
        prediction = rule_based_detector(html, comp_type)
        y_pred_rules.append(1 if prediction else 0)

    acc_rules = accuracy_score(y_true, y_pred_rules)
    prec_rules = precision_score(y_true, y_pred_rules, zero_division=0)
    rec_rules = recall_score(y_true, y_pred_rules, zero_division=0)
    f1_rules = f1_score(y_true, y_pred_rules, zero_division=0)
    cm_rules = confusion_matrix(y_true, y_pred_rules)

    print(f"  Accuracy: {acc_rules:.2%}")
    print(f"  Precision: {prec_rules:.2%}")
    print(f"  Recall: {rec_rules:.2%}")
    print(f"  F1 Score: {f1_rules:.2%}")
    print(f"  Confusion Matrix:")
    print(f"    TN={cm_rules[0,0]}, FP={cm_rules[0,1]}")
    print(f"    FN={cm_rules[1,0]}, TP={cm_rules[1,1]}")
    print()

    # Test 2: ML classifier
    print("Testing ML Classifier...")
    retrainer = MLRetrainer()
    X = []
    for html, comp_type in samples:
        features = retrainer._extract_features(html, comp_type)
        X.append(features)

    X = np.array(X)
    y_true_np = np.array(y_true)

    # Train classifier
    clf = RandomForestClassifier(random_state=42)
    clf.fit(X, y_true_np)
    y_pred_ml = clf.predict(X)

    acc_ml = accuracy_score(y_true_np, y_pred_ml)
    prec_ml = precision_score(y_true_np, y_pred_ml, zero_division=0)
    rec_ml = recall_score(y_true_np, y_pred_ml, zero_division=0)
    f1_ml = f1_score(y_true_np, y_pred_ml, zero_division=0)
    cm_ml = confusion_matrix(y_true_np, y_pred_ml)

    print(f"  Accuracy: {acc_ml:.2%}")
    print(f"  Precision: {prec_ml:.2%}")
    print(f"  Recall: {rec_ml:.2%}")
    print(f"  F1 Score: {f1_ml:.2%}")
    print(f"  Confusion Matrix:")
    print(f"    TN={cm_ml[0,0]}, FP={cm_ml[0,1]}")
    print(f"    FN={cm_ml[1,0]}, TP={cm_ml[1,1]}")
    print()

    # Comparison
    print("=== Comparison ===")
    print(f"{'Metric':<15} {'Rule-Based':<15} {'ML Classifier':<15} {'Winner':<15}")
    print("-" * 60)

    metrics = [
        ('Accuracy', acc_rules, acc_ml),
        ('Precision', prec_rules, prec_ml),
        ('Recall', rec_rules, rec_ml),
        ('F1 Score', f1_rules, f1_ml)
    ]

    for name, rule_val, ml_val in metrics:
        winner = 'Rule-Based' if rule_val > ml_val else ('ML' if ml_val > rule_val else 'Tie')
        print(f"{name:<15} {rule_val:>13.2%}  {ml_val:>13.2%}  {winner:<15}")

    print()

    # False positive/negative analysis
    print("=== Error Analysis ===")

    # Rule-based errors
    fp_rules = cm_rules[0,1]
    fn_rules = cm_rules[1,0]
    print(f"Rule-Based:")
    print(f"  False Positives: {fp_rules} (accepted but should reject)")
    print(f"  False Negatives: {fn_rules} (rejected but should accept)")

    # ML errors
    fp_ml = cm_ml[0,1]
    fn_ml = cm_ml[1,0]
    print(f"\nML Classifier:")
    print(f"  False Positives: {fp_ml} (accepted but should reject)")
    print(f"  False Negatives: {fn_ml} (rejected but should accept)")

    print()

    # Recommendation
    print("=== Recommendation ===")
    if f1_rules > f1_ml:
        print("Winner: Rule-Based Detector")
        print(f"  F1 Score: {f1_rules:.2%} vs {f1_ml:.2%}")
        print("  Reason: Simpler, faster, more interpretable, better performance")
        print("\nAction: Use rule-based detector for production")
    elif f1_ml > f1_rules:
        print("Winner: ML Classifier")
        print(f"  F1 Score: {f1_ml:.2%} vs {f1_rules:.2%}")
        print("  Reason: Better performance with learned patterns")
        print("\nAction: Use ML classifier for production")
    else:
        print("Result: Tie")
        print(f"  Both achieve F1 Score: {f1_rules:.2%}")
        print("  Recommendation: Use rule-based (simpler, faster, more maintainable)")


if __name__ == '__main__':
    main()
