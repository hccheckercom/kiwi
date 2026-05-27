#!/usr/bin/env python3
"""
Hyperparameter tuning for ML classifier.
Try multiple algorithms and find best performer.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.db import get_connection
from ml_retrain import MLRetrainer
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score


def export_training_data():
    """Export labeled samples from DB."""
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
    print("=== Hyperparameter Tuning ===\n")

    # Export data
    samples, labels = export_training_data()
    print(f"Loaded {len(samples)} labeled samples")
    print(f"  Positive: {sum(labels)}")
    print(f"  Negative: {len(labels) - sum(labels)}")
    print()

    # Extract features
    retrainer = MLRetrainer()
    X = []
    for html, comp_type in samples:
        features = retrainer._extract_features(html, comp_type)
        X.append(features)

    X = np.array(X)
    y = np.array(labels)

    print(f"Feature matrix: {X.shape}")
    print()

    # Define classifiers to test
    classifiers = {
        'RandomForest (default)': RandomForestClassifier(random_state=42),
        'RandomForest (tuned)': RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            min_samples_split=5,
            random_state=42
        ),
        'GradientBoosting': GradientBoostingClassifier(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        ),
        'SVM (RBF)': SVC(kernel='rbf', C=1.0, gamma='scale', random_state=42),
        'SVM (Linear)': SVC(kernel='linear', C=1.0, random_state=42),
        'Neural Net (small)': MLPClassifier(
            hidden_layer_sizes=(50,),
            max_iter=1000,
            random_state=42
        ),
        'Neural Net (deep)': MLPClassifier(
            hidden_layer_sizes=(100, 50),
            max_iter=1000,
            random_state=42
        )
    }

    # Cross-validation
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    results = []

    for name, clf in classifiers.items():
        print(f"Testing {name}...")

        # Cross-validation scores
        cv_scores = cross_val_score(clf, X, y, cv=cv, scoring='accuracy')

        # Train on full dataset for detailed metrics
        clf.fit(X, y)
        y_pred = clf.predict(X)

        accuracy = accuracy_score(y, y_pred)
        precision = precision_score(y, y_pred, zero_division=0)
        recall = recall_score(y, y_pred, zero_division=0)
        f1 = f1_score(y, y_pred, zero_division=0)

        results.append({
            'name': name,
            'cv_mean': cv_scores.mean(),
            'cv_std': cv_scores.std(),
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1': f1
        })

        print(f"  CV Accuracy: {cv_scores.mean():.2%} (+/- {cv_scores.std():.2%})")
        print(f"  Train Accuracy: {accuracy:.2%}")
        print(f"  Precision: {precision:.2%}")
        print(f"  Recall: {recall:.2%}")
        print(f"  F1 Score: {f1:.2%}")
        print()

    # Sort by CV accuracy
    results.sort(key=lambda x: x['cv_mean'], reverse=True)

    print("=== Results Summary ===")
    print(f"{'Classifier':<30} {'CV Acc':<12} {'Train Acc':<12} {'F1':<12}")
    print("-" * 66)

    for r in results:
        print(f"{r['name']:<30} {r['cv_mean']:>10.2%}  {r['accuracy']:>10.2%}  {r['f1']:>10.2%}")

    print()
    print(f"Best performer: {results[0]['name']}")
    print(f"  CV Accuracy: {results[0]['cv_mean']:.2%}")
    print(f"  F1 Score: {results[0]['f1']:.2%}")

    # Check if best is better than current (83.33%)
    if results[0]['cv_mean'] > 0.8333:
        print(f"\nImprovement: {(results[0]['cv_mean'] - 0.8333) * 100:.1f} percentage points")
        print("Recommendation: Retrain with best classifier")
    else:
        print("\nNo improvement over current RandomForest (83.33%)")
        print("Recommendation: Collect more training data")


if __name__ == '__main__':
    main()
