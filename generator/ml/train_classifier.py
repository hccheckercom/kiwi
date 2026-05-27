"""Train ML classifier for component detection confidence scoring."""
import sys
from pathlib import Path
import numpy as np
import pickle
from typing import Tuple, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from memory.db import get_connection

sys.path.insert(0, str(Path(__file__).parent.parent))
from ml.feature_extractor import FeatureExtractor

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    from sklearn.calibration import CalibratedClassifierCV
except ImportError:
    print("ERROR: scikit-learn not installed. Run: pip install scikit-learn")
    sys.exit(1)


def load_training_data() -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Load training data from database.

    Returns:
        X: Feature matrix (n_samples, n_features)
        y: Labels (n_samples,) - 1 if user_accepted=True, 0 if False
        component_ids: List of component IDs for tracking
    """
    conn = get_connection()
    cursor = conn.execute('''
        SELECT html_snippet, component_type, user_accepted, id
        FROM component_patterns
        WHERE user_accepted IS NOT NULL
    ''')

    rows = cursor.fetchall()
    conn.close()

    if len(rows) == 0:
        raise ValueError("No labeled data found. Run collect_training_data.py first.")

    print(f"Loaded {len(rows)} labeled samples")

    extractor = FeatureExtractor()
    X = []
    y = []
    component_ids = []

    for html_snippet, component_type, user_accepted, comp_id in rows:
        features = extractor.extract_features(html_snippet, component_type)
        X.append(features)
        y.append(1 if user_accepted else 0)
        component_ids.append(comp_id)

    return np.array(X), np.array(y), component_ids


def train_model(X: np.ndarray, y: np.ndarray, model_type: str = 'random_forest') -> object:
    """Train classifier.

    Args:
        X: Feature matrix
        y: Labels
        model_type: 'logistic', 'random_forest', or 'neural_net'

    Returns:
        Trained model
    """
    if model_type == 'logistic':
        from sklearn.linear_model import LogisticRegression
        model = LogisticRegression(max_iter=1000, random_state=42)
    elif model_type == 'random_forest':
        model = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=10)
    elif model_type == 'neural_net':
        from sklearn.neural_network import MLPClassifier
        model = MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=1000, random_state=42)
    else:
        raise ValueError(f"Unknown model type: {model_type}")

    print(f"Training {model_type} model...")
    model.fit(X, y)

    return model


def evaluate_model(model, X_test: np.ndarray, y_test: np.ndarray) -> dict:
    """Evaluate model performance.

    Returns:
        Dict with accuracy, precision, recall, f1
    """
    y_pred = model.predict(X_test)

    metrics = {
        'accuracy': accuracy_score(y_test, y_pred),
        'precision': precision_score(y_test, y_pred, zero_division=0),
        'recall': recall_score(y_test, y_pred, zero_division=0),
        'f1': f1_score(y_test, y_pred, zero_division=0)
    }

    return metrics


def calibrate_model(model, X_train: np.ndarray, y_train: np.ndarray) -> object:
    """Calibrate model probabilities using Platt scaling.

    Returns:
        Calibrated model
    """
    print("Calibrating model probabilities...")
    calibrated = CalibratedClassifierCV(model, method='sigmoid', cv=5)
    calibrated.fit(X_train, y_train)
    return calibrated


def main():
    """Main training pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description='Train ML classifier for component detection')
    parser.add_argument('--model', choices=['logistic', 'random_forest', 'neural_net'],
                        default='random_forest', help='Model type')
    parser.add_argument('--output', default='ml/model.pkl', help='Output path for trained model')
    parser.add_argument('--calibrate', action='store_true', help='Calibrate probabilities')
    parser.add_argument('--test-size', type=float, default=0.2, help='Test set size (0.0-1.0)')

    args = parser.parse_args()

    # Load data
    print("=== Loading Training Data ===")
    X, y, component_ids = load_training_data()

    print(f"Features shape: {X.shape}")
    print(f"Labels shape: {y.shape}")
    print(f"Positive samples: {np.sum(y)} ({np.mean(y)*100:.1f}%)")
    print(f"Negative samples: {len(y) - np.sum(y)} ({(1-np.mean(y))*100:.1f}%)")

    # Check if we have enough data
    if len(y) < 10:
        print("\nWARNING: Very small dataset. Results may not be reliable.")
        print("Recommendation: Collect at least 20+ labeled samples.")

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=42, stratify=y if len(np.unique(y)) > 1 else None
    )

    print(f"\nTrain set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")

    # Train model
    print(f"\n=== Training {args.model} Model ===")
    model = train_model(X_train, y_train, args.model)

    # Calibrate if requested
    if args.calibrate:
        model = calibrate_model(model, X_train, y_train)

    # Evaluate
    print("\n=== Evaluation ===")
    train_metrics = evaluate_model(model, X_train, y_train)
    test_metrics = evaluate_model(model, X_test, y_test)

    print("\nTrain Metrics:")
    for metric, value in train_metrics.items():
        print(f"  {metric}: {value:.3f}")

    print("\nTest Metrics:")
    for metric, value in test_metrics.items():
        print(f"  {metric}: {value:.3f}")

    # Check for overfitting
    if train_metrics['accuracy'] - test_metrics['accuracy'] > 0.15:
        print("\nWARNING: Possible overfitting (train accuracy >> test accuracy)")
        print("Recommendation: Collect more data or use simpler model")

    # Save model
    output_path = Path(__file__).parent.parent / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'wb') as f:
        pickle.dump(model, f)

    print(f"\n=== Model Saved ===")
    print(f"Path: {output_path}")
    print(f"Size: {output_path.stat().st_size / 1024:.1f} KB")

    # Feature importance (if available)
    if hasattr(model, 'feature_importances_'):
        print("\n=== Top 10 Most Important Features ===")
        extractor = FeatureExtractor()
        feature_names = extractor.get_feature_names()

        if hasattr(model, 'estimators_'):  # CalibratedClassifierCV
            importances = model.estimators_[0].feature_importances_
        else:
            importances = model.feature_importances_

        indices = np.argsort(importances)[::-1][:10]
        for i, idx in enumerate(indices, 1):
            print(f"  {i}. {feature_names[idx]}: {importances[idx]:.3f}")

    print("\n=== Training Complete ===")
    print(f"Next step: python ml/optimize_threshold.py --model {args.output}")


if __name__ == '__main__':
    main()