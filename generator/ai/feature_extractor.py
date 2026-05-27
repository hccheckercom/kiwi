"""Feature Extractor — Extract ML features from HTML components"""

import json
import re
import numpy as np
from pathlib import Path
from typing import Dict, List, Any
from bs4 import BeautifulSoup
from collections import Counter


class FeatureExtractor:
    """
    Extract feature vectors from HTML components for ML classification.

    Features:
    - Tailwind class embeddings (300-dim)
    - Text content features (10-dim)
    - DOM structure features (5-dim)

    Total: 315-dim feature vector
    """

    def __init__(self):
        self.class_vocab = self._build_class_vocab()
        self.tag_vocab = ['div', 'section', 'header', 'footer', 'nav', 'article', 'aside', 'main', 'span', 'a', 'button', 'input', 'form', 'img', 'ul', 'li', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']

    def _build_class_vocab(self) -> Dict[str, int]:
        """Build vocabulary of common Tailwind classes."""
        # Common Tailwind prefixes
        common_classes = [
            # Layout
            'flex', 'grid', 'block', 'inline', 'hidden',
            # Spacing
            'p-', 'm-', 'px-', 'py-', 'mx-', 'my-', 'gap-', 'space-',
            # Sizing
            'w-', 'h-', 'max-w-', 'max-h-', 'min-w-', 'min-h-',
            # Colors
            'bg-', 'text-', 'border-',
            # Typography
            'font-', 'text-', 'leading-', 'tracking-',
            # Borders
            'rounded-', 'border-',
            # Effects
            'shadow-', 'opacity-', 'hover:', 'transition-',
            # Position
            'absolute', 'relative', 'fixed', 'sticky', 'top-', 'bottom-', 'left-', 'right-',
            # Display
            'items-', 'justify-', 'content-', 'self-',
        ]

        return {cls: idx for idx, cls in enumerate(common_classes)}

    def extract(self, component: Dict[str, Any]) -> np.ndarray:
        """
        Extract feature vector from component.

        Args:
            component: Component dict with keys: html, classes, text, type

        Returns:
            315-dim numpy array
        """
        features = []

        # 1. Tailwind class embeddings (300-dim)
        class_features = self._extract_class_features(component.get('classes', []))
        features.extend(class_features)

        # 2. Text content features (10-dim)
        text_features = self._extract_text_features(component.get('text', ''))
        features.extend(text_features)

        # 3. DOM structure features (5-dim)
        structure_features = self._extract_structure_features(component.get('html', ''))
        features.extend(structure_features)

        return np.array(features, dtype=np.float32)

    def _extract_class_features(self, classes: List[str]) -> List[float]:
        """Extract Tailwind class embeddings (300-dim)."""
        # Count class prefix occurrences
        class_counts = Counter()

        for cls in classes:
            # Match against vocabulary
            for prefix in self.class_vocab.keys():
                if cls.startswith(prefix):
                    class_counts[prefix] += 1
                    break

        # Create feature vector (one-hot + counts)
        features = [0.0] * 300

        for i, (prefix, idx) in enumerate(self.class_vocab.items()):
            if idx < 300:
                features[idx] = min(class_counts.get(prefix, 0), 5) / 5.0  # Normalize to [0, 1]

        return features

    def _extract_text_features(self, text: str) -> List[float]:
        """Extract text content features (10-dim)."""
        if not text:
            return [0.0] * 10

        # 1. Character count (normalized)
        char_count = min(len(text), 1000) / 1000.0

        # 2. Word count (normalized)
        word_count = min(len(text.split()), 100) / 100.0

        # 3. Has Vietnamese characters
        has_vietnamese = 1.0 if re.search(r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', text.lower()) else 0.0

        # 4. Has numbers
        has_numbers = 1.0 if re.search(r'\d', text) else 0.0

        # 5. Has special chars
        has_special = 1.0 if re.search(r'[!@#$%^&*(),.?":{}|<>]', text) else 0.0

        # 6-10. Keyword presence (common UI text)
        keywords = ['button', 'click', 'submit', 'login', 'register']
        keyword_features = [1.0 if kw in text.lower() else 0.0 for kw in keywords]

        return [char_count, word_count, has_vietnamese, has_numbers, has_special] + keyword_features

    def _extract_structure_features(self, html: str) -> List[float]:
        """Extract DOM structure features (5-dim)."""
        if not html:
            return [0.0] * 5

        soup = BeautifulSoup(html, 'html.parser')
        root = soup.find()

        if not root:
            return [0.0] * 5

        # 1. Depth (number of parent elements, normalized)
        depth = min(len(list(root.parents)), 10) / 10.0

        # 2. Children count (normalized)
        children_count = min(len(list(root.find_all(recursive=False))), 20) / 20.0

        # 3. Total descendants (normalized)
        descendants_count = min(len(list(root.descendants)), 100) / 100.0

        # 4. Tag encoding (one-hot for common tags)
        tag_idx = self.tag_vocab.index(root.name) if root.name in self.tag_vocab else -1
        tag_feature = tag_idx / len(self.tag_vocab) if tag_idx >= 0 else 0.0

        # 5. Has icon (material-symbols-outlined class)
        has_icon = 1.0 if root.find(class_='material-symbols-outlined') else 0.0

        return [depth, children_count, descendants_count, tag_feature, has_icon]

    def extract_batch(self, components: List[Dict]) -> np.ndarray:
        """Extract features for multiple components."""
        features = [self.extract(comp) for comp in components]
        return np.array(features)


def main():
    """CLI for testing feature extraction."""
    import sys

    # Load training data
    training_data_path = Path(__file__).parent / "training_data.json"

    if not training_data_path.exists():
        print(f"ERROR: Training data not found at {training_data_path}")
        print("Run data_labeler.py first to collect training data")
        sys.exit(1)

    with open(training_data_path, 'r', encoding='utf-8') as f:
        training_data = json.load(f)

    print(f"Loaded {len(training_data)} training examples")

    # Extract features
    extractor = FeatureExtractor()

    print("\nExtracting features for first 5 examples:")
    for i, component in enumerate(training_data[:5], 1):
        features = extractor.extract(component)
        print(f"\n{i}. {component['type']} ({component['id']})")
        print(f"   Feature vector shape: {features.shape}")
        print(f"   Non-zero features: {np.count_nonzero(features)}")
        print(f"   Feature range: [{features.min():.3f}, {features.max():.3f}]")

    # Extract all features
    print(f"\nExtracting features for all {len(training_data)} examples...")
    all_features = extractor.extract_batch(training_data)

    print(f"Feature matrix shape: {all_features.shape}")
    print(f"Feature statistics:")
    print(f"  Mean: {all_features.mean():.3f}")
    print(f"  Std: {all_features.std():.3f}")
    print(f"  Min: {all_features.min():.3f}")
    print(f"  Max: {all_features.max():.3f}")

    # Save features
    features_path = Path(__file__).parent / "features.npy"
    np.save(features_path, all_features)
    print(f"\nSaved features to {features_path}")

    # Save labels
    labels = [comp['type'] for comp in training_data]
    labels_path = Path(__file__).parent / "labels.json"
    with open(labels_path, 'w', encoding='utf-8') as f:
        json.dump(labels, f, indent=2)
    print(f"Saved labels to {labels_path}")


if __name__ == "__main__":
    main()