"""Optimize confidence threshold for auto-apply decision."""
import sys
from pathlib import Path
import numpy as np
import pickle
from typing import Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from memory.db import get_connection
from ml.feature_extractor import FeatureExtractor

try:
    from sklearn.metrics import precision_recall_curve, f1_score, precision_score, recall_score
except ImportError:
    print("ERROR: scikit-learn not installed. Run: pip install scikit-learn")
    sys.exit(1)


def load_model(model_path: str):
    """Load trained model from disk.

    Security: pickle.load is safe here because model_path is validated
    to be within Kiwi's internal directory, not user-controlled input.
    """
    model_path_obj = Path(model_path).resolve()
    kiwi_root = Path(__file__).parent.parent.parent.resolve()

    # Validate path is within Kiwi directory
    if not str(model_path_obj).startswith(str(kiwi_root)):
        raise ValueError(f"Model path must be within Kiwi directory: {model_path}")

    if not model_path_obj.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    with open(model_path, 'rb') as f:
        model = pickle.load(f)  # nosec: validated internal path
    return model


def load_test_data() -> Tuple[np.ndarray, np.ndarray]:
    """Load test data from database."""
    conn = get_connection()
    cursor = conn.execute('''
        SELECT html_snippet, component_type, user_accepted
        FROM component_patterns
        WHERE user_accepted IS NOT NULL
    ''')

    rows = cursor.fetchall()
    conn.close()

    extractor = FeatureExtractor()
    X = []
    y = []

    for html_snippet, component_type, user_accepted in rows:
        features = extractor.extract_features(html_snippet, component_type)
        X.append(features)
        y.append(1 if user_accepted else 0)

    return np.array(X), np.array(y)


def find_optimal_threshold(model, X: np.ndarray, y: np.ndarray) -> dict:
    """Find optimal threshold using precision-recall curve.

    Returns:
        Dict with best_threshold, precision, recall, f1
    """
    # Get predicted probabilities
    if hasattr(model, 'predict_proba'):
        y_proba = model.predict_proba(X)[:, 1]
    else:
        raise ValueError("Model does not support predict_proba")

    # Try different thresholds
    thresholds = np.arange(0.5, 1.0, 0.05)
    results = []

    for threshold in thresholds:
        y_pred = (y_proba >= threshold).astype(int)

        precision = precision_score(y, y_pred, zero_division=0)
        recall = recall_score(y, y_pred, zero_division=0)
        f1 = f1_score(y, y_pred, zero_division=0)

        results.append({
            'threshold': threshold,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'auto_apply_rate': np.mean(y_pred)
        })

    # Find best threshold by F1 score
    best_result = max(results, key=lambda x: x['f1'])

    return best_result, results


def main():
    """Main optimization pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description='Optimize confidence threshold')
    parser.add_argument('--model', default='ml/model.pkl', help='Path to trained model')
    parser.add_argument('--output', default='ml/best_threshold.txt', help='Output path for threshold')
    parser.add_argument('--min-precision', type=float, default=0.9, help='Minimum precision required')

    args = parser.parse_args()

    # Load model
    model_path = Path(__file__).parent.parent / args.model
    if not model_path.exists():
        print(f"ERROR: Model not found at {model_path}")
        print("Run: python ml/train_classifier.py first")
        sys.exit(1)

    print("=== Loading Model ===")
    model = load_model(model_path)
    print(f"Model loaded from {model_path}")

    # Load test data
    print("\n=== Loading Test Data ===")
    X, y = load_test_data()
    print(f"Test samples: {len(X)}")
    print(f"Positive samples: {np.sum(y)} ({np.mean(y)*100:.1f}%)")

    # Find optimal threshold
    print("\n=== Optimizing Threshold ===")
    best_result, all_results = find_optimal_threshold(model, X, y)

    # Print all results
    print("\nThreshold Analysis:")
    print(f"{'Threshold':<12} {'Precision':<12} {'Recall':<12} {'F1':<12} {'Auto-Apply %':<15}")
    print("-" * 65)
    for result in all_results:
        print(f"{result['threshold']:<12.2f} {result['precision']:<12.3f} {result['recall']:<12.3f} "
              f"{result['f1']:<12.3f} {result['auto_apply_rate']*100:<15.1f}")

    # Print best result
    print("\n=== Best Threshold ===")
    print(f"Threshold: {best_result['threshold']:.2f}")
    print(f"Precision: {best_result['precision']:.3f}")
    print(f"Recall: {best_result['recall']:.3f}")
    print(f"F1 Score: {best_result['f1']:.3f}")
    print(f"Auto-apply rate: {best_result['auto_apply_rate']*100:.1f}%")

    # Check if precision meets requirement
    if best_result['precision'] < args.min_precision:
        print(f"\nWARNING: Best precision ({best_result['precision']:.3f}) is below minimum ({args.min_precision})")
        print("Recommendation: Collect more training data or use a more conservative threshold")

    # Save threshold
    output_path = Path(__file__).parent.parent / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        f.write(f"{best_result['threshold']:.2f}\n")

    print(f"\n=== Threshold Saved ===")
    print(f"Path: {output_path}")

    # Compare to baseline (0.7)
    baseline_threshold = 0.7
    baseline_result = next((r for r in all_results if abs(r['threshold'] - baseline_threshold) < 0.01), None)

    if baseline_result:
        print("\n=== Comparison to Baseline (0.7) ===")
        print(f"Baseline auto-apply rate: {baseline_result['auto_apply_rate']*100:.1f}%")
        print(f"Optimized auto-apply rate: {best_result['auto_apply_rate']*100:.1f}%")
        print(f"Improvement: {(best_result['auto_apply_rate'] - baseline_result['auto_apply_rate'])*100:+.1f}%")

    print("\n=== Optimization Complete ===")
    print(f"Next step: python test_full_mode.py --use-ml true --threshold {best_result['threshold']:.2f}")


if __name__ == '__main__':
    main()
