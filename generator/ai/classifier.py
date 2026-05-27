"""AI Component Classifier — ML model for component type classification"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Any
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib


class ComponentClassifier:
    """
    ML classifier for component type prediction.

    Uses RandomForest (lightweight, no GPU needed) instead of BERT for MVP.
    Can upgrade to BERT later if needed.

    Usage:
        classifier = ComponentClassifier()
        classifier.train(features, labels)
        pred_type, confidence = classifier.predict(feature_vector)
    """

    def __init__(self, model_path: str = None):
        self.model = None
        self.label_encoder = {}
        self.label_decoder = {}

        if model_path and Path(model_path).exists():
            self.load(model_path)

    def train(self, features: np.ndarray, labels: List[str], test_size: float = 0.2):
        """
        Train classifier on labeled data.

        Args:
            features: Feature matrix (N × 315)
            labels: Component type labels (N,)
            test_size: Test set ratio

        Returns:
            Training report with accuracy, metrics
        """
        # Encode labels to integers
        unique_labels = sorted(set(labels))
        self.label_encoder = {label: idx for idx, label in enumerate(unique_labels)}
        self.label_decoder = {idx: label for label, idx in self.label_encoder.items()}

        y = np.array([self.label_encoder[label] for label in labels])

        # Check if stratify is possible (need at least 2 samples per class)
        from collections import Counter
        class_counts = Counter(y)
        min_samples = min(class_counts.values())

        # Train/test split (stratify only if possible)
        if min_samples >= 2:
            X_train, X_test, y_train, y_test = train_test_split(
                features, y, test_size=test_size, random_state=42, stratify=y
            )
        else:
            print(f"WARNING: {sum(1 for c in class_counts.values() if c == 1)} classes have only 1 sample")
            print("Disabling stratified split (may result in imbalanced train/test sets)")
            X_train, X_test, y_train, y_test = train_test_split(
                features, y, test_size=test_size, random_state=42
            )

        print(f"Training set: {len(X_train)} examples")
        print(f"Test set: {len(X_test)} examples")
        print(f"Classes: {len(unique_labels)}")

        # Train RandomForest
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=20,
            min_samples_split=2,
            random_state=42,
            n_jobs=-1
        )

        print("\nTraining model...")
        self.model.fit(X_train, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        print(f"\nTest Accuracy: {accuracy:.2%}")

        # Classification report
        report = classification_report(
            y_test, y_pred,
            target_names=[self.label_decoder[i] for i in sorted(self.label_decoder.keys())],
            zero_division=0
        )

        print("\nClassification Report:")
        print(report)

        return {
            'accuracy': accuracy,
            'train_size': len(X_train),
            'test_size': len(X_test),
            'n_classes': len(unique_labels),
            'report': report
        }

    def predict(self, features: np.ndarray) -> Tuple[str, float]:
        """
        Predict component type and confidence.

        Args:
            features: Feature vector (315,)

        Returns:
            (predicted_type, confidence)
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        # Reshape if needed
        if features.ndim == 1:
            features = features.reshape(1, -1)

        # Predict probabilities
        probs = self.model.predict_proba(features)[0]

        # Get top prediction
        pred_idx = np.argmax(probs)
        confidence = probs[pred_idx]
        pred_type = self.label_decoder[pred_idx]

        return pred_type, confidence

    def predict_batch(self, features: np.ndarray) -> List[Tuple[str, float]]:
        """Predict for multiple components."""
        results = []
        for feature_vec in features:
            pred_type, confidence = self.predict(feature_vec)
            results.append((pred_type, confidence))
        return results

    def save(self, model_path: str):
        """Save trained model to disk."""
        model_dir = Path(model_path).parent
        model_dir.mkdir(parents=True, exist_ok=True)

        joblib.dump({
            'model': self.model,
            'label_encoder': self.label_encoder,
            'label_decoder': self.label_decoder
        }, model_path)

        print(f"Model saved to {model_path}")

    def load(self, model_path: str):
        """Load trained model from disk."""
        data = joblib.load(model_path)
        self.model = data['model']
        self.label_encoder = data['label_encoder']
        self.label_decoder = data['label_decoder']

        print(f"Model loaded from {model_path}")


def main():
    """CLI for training classifier."""
    import sys
    from class_groups import group_labels

    ai_dir = Path(__file__).parent

    # Load features and labels
    features_path = ai_dir / "features.npy"
    labels_path = ai_dir / "labels.json"

    if not features_path.exists() or not labels_path.exists():
        print("ERROR: Training data not found")
        print("Run data_labeler.py and feature_extractor.py first")
        sys.exit(1)

    features = np.load(features_path)
    with open(labels_path, 'r', encoding='utf-8') as f:
        specific_labels = json.load(f)

    # Group to broad categories
    labels = group_labels(specific_labels)

    print(f"Loaded {len(features)} training examples")
    print(f"Feature shape: {features.shape}")
    print(f"Grouped {len(set(specific_labels))} specific types -> {len(set(labels))} broad categories")

    # Train classifier
    classifier = ComponentClassifier()
    report = classifier.train(features, labels, test_size=0.2)

    # Save model
    model_path = ai_dir / "models" / "component_classifier.pkl"
    classifier.save(str(model_path))

    # Test prediction on first example
    print("\n" + "="*60)
    print("Testing prediction on first example:")
    pred_type, confidence = classifier.predict(features[0])
    print(f"  True label: {labels[0]}")
    print(f"  Predicted: {pred_type} (confidence: {confidence:.2%})")


if __name__ == "__main__":
    main()