"""ML Pattern Quality Classifier

Trains a classifier to predict pattern quality based on confidence data.
Uses Random Forest or XGBoost to filter low-quality patterns automatically.
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import pickle
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

# Lazy imports
_model = None
_model_path = Path(__file__).parent.parent / 'memory' / 'ml_model.pkl'


def extract_features(pattern: Dict) -> np.ndarray:
    """
    Extract features from pattern for ML training.

    Features:
    - Pattern complexity (length, special chars, groups)
    - False positive rate
    - True positive rate
    - Fix success rate
    - Total hits
    - Severity (encoded)

    Returns: Feature vector (7 dimensions)
    """
    from memory.confidence import get_confidence

    lesson_id = pattern.get('id', '')
    confidence_data = get_confidence(lesson_id) or {}

    # Pattern complexity features
    pattern_str = pattern.get('scan', {}).get('pattern', '')
    pattern_length = len(pattern_str)
    special_chars = sum(1 for c in pattern_str if c in r'.*+?[]{}()|\\^$')
    groups = pattern_str.count('(')

    # Confidence features
    total_hits = confidence_data.get('total_hits', 0)
    tp_count = confidence_data.get('true_positive_count', 0)
    fp_count = confidence_data.get('false_positive_count', 0)
    fix_success = confidence_data.get('fix_success_count', 0)
    fix_failure = confidence_data.get('fix_failure_count', 0)

    # Rates (avoid division by zero)
    fp_rate = fp_count / max(total_hits, 1)
    tp_rate = tp_count / max(total_hits, 1)
    fix_success_rate = fix_success / max(fix_success + fix_failure, 1)

    # Severity encoding
    severity_map = {'CRITICAL': 3, 'HIGH': 2, 'SUGGEST': 1, 'INFO': 0}
    severity = severity_map.get(pattern.get('severity', 'HIGH'), 2)

    return np.array([
        pattern_length,
        special_chars,
        groups,
        fp_rate,
        tp_rate,
        fix_success_rate,
        severity
    ])


def train_pattern_classifier(training_data: List[Dict]) -> object:
    """
    Train classifier for pattern quality.

    Args:
        training_data: List of patterns with confidence scores

    Returns: Trained model (Random Forest or XGBoost)
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report

    if len(training_data) < 10:
        raise ValueError("Need at least 10 patterns with confidence data to train")

    # Extract features and labels
    X = []
    y = []

    for pattern in training_data:
        features = extract_features(pattern)
        X.append(features)

        # Label: high (1) if confidence > 0.7, low (0) otherwise
        from memory.confidence import get_confidence
        confidence_data = get_confidence(pattern.get('id', ''))
        confidence = confidence_data.get('confidence', 0.5) if confidence_data else 0.5
        label = 1 if confidence > 0.7 else 0
        y.append(label)

    X = np.array(X)
    y = np.array(y)

    # Split train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Train Random Forest
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        random_state=42
    )
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    print("\nModel Performance:")
    print(classification_report(y_test, y_pred, target_names=['Low Quality', 'High Quality']))

    # Feature importance
    feature_names = [
        'pattern_length', 'special_chars', 'groups',
        'fp_rate', 'tp_rate', 'fix_success_rate', 'severity'
    ]
    importances = model.feature_importances_
    print("\nFeature Importance:")
    for name, importance in sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True):
        print(f"  {name}: {importance:.3f}")

    return model


def predict_pattern_quality(pattern: Dict, model: Optional[object] = None) -> float:
    """
    Predict quality score (0-1) for a pattern.

    Args:
        pattern: Pattern dict with id, scan, severity
        model: Trained model (loads from disk if None)

    Returns: Quality score (0-1)
    """
    if model is None:
        model = load_model()
        if model is None:
            # No trained model, return default
            return 0.5

    features = extract_features(pattern).reshape(1, -1)
    proba = model.predict_proba(features)[0]

    # Return probability of high quality class
    return float(proba[1])


def retrain_on_feedback(new_data: List[Dict]):
    """
    Incremental retraining with new feedback.

    Args:
        new_data: New patterns with confidence scores
    """
    # Load existing model
    model = load_model()

    if model is None:
        # No existing model, train from scratch
        model = train_pattern_classifier(new_data)
    else:
        # Incremental training (warm start)
        X = []
        y = []

        for pattern in new_data:
            features = extract_features(pattern)
            X.append(features)

            from memory.confidence import get_confidence
            confidence_data = get_confidence(pattern.get('id', ''))
            confidence = confidence_data.get('confidence', 0.5) if confidence_data else 0.5
            label = 1 if confidence > 0.7 else 0
            y.append(label)

        X = np.array(X)
        y = np.array(y)

        # Partial fit (if supported) or retrain
        if hasattr(model, 'n_estimators'):
            # Random Forest: add more trees
            model.n_estimators += 10
            model.fit(X, y)
        else:
            # Retrain from scratch
            model.fit(X, y)

    save_model(model)


def save_model(model: object):
    """Persist model to disk."""
    _model_path.parent.mkdir(exist_ok=True)
    with open(_model_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"Model saved to {_model_path}")


def load_model() -> Optional[object]:
    """Load trained model from disk."""
    global _model

    if _model is not None:
        return _model

    if not _model_path.exists():
        return None

    import json as _json
    try:
        with open(_model_path, 'r', encoding='utf-8') as f:
            _model = _json.load(f)
    except (_json.JSONDecodeError, UnicodeDecodeError):
        with open(_model_path, 'rb') as f:
            _model = pickle.load(f)  # legacy binary format fallback

    return _model


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Train ML pattern classifier')
    parser.add_argument('--train', action='store_true', help='Train model on all lessons')
    parser.add_argument('--predict', type=str, help='Predict quality for lesson ID')
    parser.add_argument('--retrain', action='store_true', help='Retrain with new feedback')

    args = parser.parse_args()

    if args.train:
        from scanner.loader import load_patterns

        print("Loading patterns...")
        patterns = load_patterns(platform=None, scope_type=None)
        print(f"Loaded {len(patterns)} patterns")

        # Filter patterns with confidence data
        from memory.confidence import get_all_confidence
        confidence_data = get_all_confidence()
        lesson_ids_with_data = {c['lesson_id'] for c in confidence_data}

        patterns_with_data = [p for p in patterns if p.get('id') in lesson_ids_with_data]
        print(f"Found {len(patterns_with_data)} patterns with confidence data")

        if len(patterns_with_data) < 10:
            print("ERROR: Need at least 10 patterns with confidence data to train")
            print("Run some scans first to collect confidence data")
            sys.exit(1)

        print("\nTraining model...")
        model = train_pattern_classifier(patterns_with_data)

        print("\nSaving model...")
        save_model(model)

        print("\nDone! Model ready for predictions")

    elif args.predict:
        from scanner.loader import load_patterns

        patterns = load_patterns(platform=None, scope_type=None)
        pattern = next((p for p in patterns if p.get('id') == args.predict), None)

        if not pattern:
            print(f"ERROR: Lesson {args.predict} not found")
            sys.exit(1)

        quality = predict_pattern_quality(pattern)
        print(f"Quality score for {args.predict}: {quality:.3f}")

        if quality > 0.7:
            print("  → High quality pattern")
        elif quality > 0.4:
            print("  → Medium quality pattern")
        else:
            print("  → Low quality pattern (consider refinement)")

    elif args.retrain:
        print("Retraining with new feedback...")
        from scanner.loader import load_patterns
        patterns = load_patterns(platform=None, scope_type=None)

        from memory.confidence import get_all_confidence
        confidence_data = get_all_confidence()
        lesson_ids_with_data = {c['lesson_id'] for c in confidence_data}

        patterns_with_data = [p for p in patterns if p.get('id') in lesson_ids_with_data]

        retrain_on_feedback(patterns_with_data)
        print("Retraining complete")

    else:
        print("Use --train to train model, --predict LESSON_ID to predict quality")