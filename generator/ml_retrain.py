"""Auto-Retrain ML Classifier with Real-World Labeled Data"""

import pickle
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import json


class MLRetrainer:
    """
    Auto-retrain ML classifier with real-world labeled data from feedback.

    Retrains every 10 generations with feedback to improve accuracy.
    """

    def __init__(self):
        self.model_path = Path(__file__).parent / "ai" / "component_classifier.pkl"
        self.min_samples = 20  # Minimum samples needed to retrain

    def _extract_features(self, html: str, component_type: str) -> List[float]:
        """
        Extract advanced features from HTML.

        Returns 15-dimensional feature vector.
        """
        import re

        # Basic metrics
        html_length = len(html)
        tag_count = html.count("<")
        class_count = html.count("class=")

        # Semantic tags
        semantic_tags = ["header", "nav", "section", "article", "aside", "footer", "main"]
        semantic_count = sum(html.lower().count(f"<{tag}") for tag in semantic_tags)

        # Interactive elements
        interactive_tags = ["button", "a", "input", "select", "textarea"]
        interactive_count = sum(html.lower().count(f"<{tag}") for tag in interactive_tags)

        # Layout indicators
        has_flex = 1 if "flex" in html else 0
        has_grid = 1 if "grid" in html else 0
        has_container = 1 if "container" in html else 0

        # Text content
        text_content = re.sub(r'<[^>]+>', '', html)
        text_length = len(text_content.strip())
        text_ratio = text_length / html_length if html_length > 0 else 0

        # Tailwind classes
        tailwind_classes = re.findall(r'class="([^"]*)"', html)
        avg_classes_per_element = len(' '.join(tailwind_classes).split()) / max(tag_count, 1)

        # Component-specific features
        has_heading = 1 if re.search(r'<h[1-6]', html) else 0
        has_image = 1 if '<img' in html else 0
        has_list = 1 if '<ul' in html or '<ol' in html else 0

        # Nesting depth (approximate)
        max_depth = html.count('<div') + html.count('<section')

        return [
            html_length / 1000,  # Normalize
            tag_count,
            class_count,
            semantic_count,
            interactive_count,
            has_flex,
            has_grid,
            has_container,
            text_ratio,
            avg_classes_per_element,
            has_heading,
            has_image,
            has_list,
            max_depth,
            len(component_type)  # Component type name length
        ]

    def should_retrain(self) -> Tuple[bool, str]:
        """
        Check if classifier should be retrained.

        Returns:
            (should_retrain, reason)
        """
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from memory.db import get_pattern_stats

        stats = get_pattern_stats()
        overall = stats.get("overall", {})
        total = overall.get("total_generations", 0)

        if total < self.min_samples:
            return False, f"Need {self.min_samples - total} more labeled examples (current: {total})"

        # Retrain every 10 generations
        if total % 10 == 0:
            return True, f"Reached {total} generations (retrain every 10)"

        return False, f"Next retrain at {(total // 10 + 1) * 10} generations (current: {total})"

    def export_training_data(self) -> Tuple[List[Dict], List[int]]:
        """
        Export labeled examples from component_patterns table.

        Returns:
            (features, labels) where features are component dicts and labels are 0/1
        """
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from memory.db import get_component_patterns

        # Get all patterns with user feedback
        patterns = get_component_patterns(limit=1000)
        with_feedback = [p for p in patterns if p["user_accepted"] is not None]

        if not with_feedback:
            raise ValueError("No labeled examples found in database")

        features = []
        labels = []

        for p in with_feedback:
            # Extract features from HTML snippet
            html = p["html_snippet"]

            feature_dict = {
                "type": p["component_type"],
                "html": html,
                "confidence": p["confidence"],
                # Add more features as needed
            }

            features.append(feature_dict)
            labels.append(1 if p["user_accepted"] else 0)

        return features, labels

    def retrain_classifier(self, features: List[Dict], labels: List[int]) -> Dict[str, Any]:
        """
        Retrain RandomForest classifier with new data.

        Args:
            features: List of feature dicts
            labels: List of 0/1 labels

        Returns:
            Training report with accuracy metrics
        """
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
        except ImportError:
            raise ImportError("scikit-learn not installed. Run: pip install scikit-learn")

        # Convert features to numerical format with improved feature extraction
        X = []
        for f in features:
            html = f["html"]
            comp_type = f["type"]

            # Extract advanced features
            features_vector = self._extract_features(html, comp_type)
            X.append(features_vector)

        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, labels, test_size=0.2, random_state=42
        )

        # Train model
        clf = RandomForestClassifier(n_estimators=100, random_state=42)
        clf.fit(X_train, y_train)

        # Evaluate
        y_pred = clf.predict(X_test)

        report = {
            "samples_total": len(features),
            "samples_train": len(X_train),
            "samples_test": len(X_test),
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall": recall_score(y_test, y_pred, zero_division=0),
            "f1_score": f1_score(y_test, y_pred, zero_division=0),
        }

        # Save model
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.model_path, "wb") as f:
            pickle.dump(clf, f)

        return report

    def run_retrain(self) -> Dict[str, Any]:
        """
        Full retrain workflow: check, export, train, save.

        Returns:
            Retrain report
        """
        should, reason = self.should_retrain()

        if not should:
            return {
                "retrained": False,
                "reason": reason,
            }

        # Export data
        features, labels = self.export_training_data()

        # Retrain
        train_report = self.retrain_classifier(features, labels)

        return {
            "retrained": True,
            "reason": reason,
            **train_report,
        }


def format_retrain_report(report: Dict[str, Any]) -> str:
    """Format retrain report for MCP tool output."""
    if not report.get("retrained"):
        return f"ML Classifier Retrain — Skipped\n\n{report['reason']}"

    lines = [
        "ML Classifier Retrain — Complete",
        "",
        f"Reason: {report['reason']}",
        "",
        f"Training Data:",
        f"  Total samples: {report['samples_total']}",
        f"  Train samples: {report['samples_train']}",
        f"  Test samples: {report['samples_test']}",
        "",
        f"Model Performance:",
        f"  Accuracy: {report['accuracy']:.1%}",
        f"  Precision: {report['precision']:.1%}",
        f"  Recall: {report['recall']:.1%}",
        f"  F1 Score: {report['f1_score']:.2f}",
        "",
        f"Model saved to: .claude/kiwi/generator/ai/component_classifier.pkl",
        "",
        f"Next retrain: After 10 more generations with feedback",
    ]

    return "\n".join(lines)


def auto_retrain_check() -> Optional[str]:
    """
    Check if auto-retrain should trigger and run if needed.

    Called automatically after each feedback submission.

    Returns:
        Retrain report if triggered, None otherwise
    """
    retrainer = MLRetrainer()
    should, reason = retrainer.should_retrain()

    if not should:
        return None

    report = retrainer.run_retrain()
    return format_retrain_report(report)