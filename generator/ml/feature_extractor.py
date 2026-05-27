"""Extract features from HTML snippets for ML training."""
from bs4 import BeautifulSoup
import numpy as np
import re
from typing import Dict, List


class FeatureExtractor:
    """Extract numerical features from HTML snippets for component classification."""

    COMPONENT_TYPES = [
        'hero', 'header', 'footer', 'button', 'product-card',
        'category-card', 'trust-badge', 'flash-sale', 'carousel',
        'tabs', 'accordion', 'modal', 'form', 'search-bar'
    ]

    def extract_features(self, html_snippet: str, component_type: str) -> np.ndarray:
        """Extract feature vector from HTML snippet.

        Returns:
            numpy array of shape (n_features,)
        """
        soup = BeautifulSoup(html_snippet, 'html.parser')
        root = soup.find()

        if not root:
            return np.zeros(50)

        features = []

        # Structural features (10)
        features.extend(self._structural_features(root))

        # Content features (10)
        features.extend(self._content_features(root))

        # Style features (15)
        features.extend(self._style_features(root))

        # Context features (10)
        features.extend(self._context_features(root, html_snippet))

        # Component type one-hot encoding (5 most common types)
        features.extend(self._component_type_features(component_type))

        return np.array(features, dtype=np.float32)

    def _structural_features(self, element) -> List[float]:
        """Extract structural features from element."""
        features = []

        # Tag name encoding (top 5 tags)
        tag_map = {'div': 1, 'section': 2, 'header': 3, 'footer': 4, 'button': 5}
        features.append(tag_map.get(element.name, 0))

        # Number of children
        children = list(element.children)
        features.append(len([c for c in children if hasattr(c, 'name')]))

        # Depth in DOM tree
        depth = 0
        parent = element.parent
        while parent and depth < 10:
            depth += 1
            parent = parent.parent
        features.append(depth)

        # Has ID
        features.append(1.0 if element.get('id') else 0.0)

        # Has class
        features.append(1.0 if element.get('class') else 0.0)

        # Number of classes
        classes = element.get('class', [])
        features.append(len(classes))

        # Has data attributes
        data_attrs = [k for k in element.attrs.keys() if k.startswith('data-')]
        features.append(len(data_attrs))

        # Has inline style
        features.append(1.0 if element.get('style') else 0.0)

        # Number of siblings
        siblings = element.find_next_siblings() + element.find_previous_siblings()
        features.append(len(siblings))

        # Is first child
        features.append(1.0 if element.parent and element == list(element.parent.children)[0] else 0.0)

        return features

    def _content_features(self, element) -> List[float]:
        """Extract content features from element."""
        features = []

        # Text length
        text = element.get_text(strip=True)
        features.append(len(text))

        # Has images
        images = element.find_all('img')
        features.append(len(images))

        # Has links
        links = element.find_all('a')
        features.append(len(links))

        # Has buttons
        buttons = element.find_all('button')
        features.append(len(buttons))

        # Has form elements
        forms = element.find_all(['form', 'input', 'textarea', 'select'])
        features.append(len(forms))

        # Has headings
        headings = element.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        features.append(len(headings))

        # Has lists
        lists = element.find_all(['ul', 'ol'])
        features.append(len(lists))

        # Has SVG
        svgs = element.find_all('svg')
        features.append(len(svgs))

        # Text to HTML ratio
        html_len = len(str(element))
        features.append(len(text) / html_len if html_len > 0 else 0.0)

        # Has price indicators (₫, $, VND)
        has_price = bool(re.search(r'[₫$]|VND', text))
        features.append(1.0 if has_price else 0.0)

        return features

    def _style_features(self, element) -> List[float]:
        """Extract style-related features from element."""
        features = []

        classes = ' '.join(element.get('class', []))

        # Common component keywords
        keywords = [
            'hero', 'banner', 'header', 'footer', 'nav',
            'card', 'product', 'category', 'badge', 'sale',
            'carousel', 'slider', 'tab', 'accordion', 'modal',
            'btn', 'button', 'cta', 'form', 'search'
        ]

        for keyword in keywords[:15]:
            features.append(1.0 if keyword in classes.lower() else 0.0)

        return features

    def _context_features(self, element, html_snippet: str) -> List[float]:
        """Extract context features from element position."""
        features = []

        # Position in page (estimated by HTML position)
        snippet_len = len(html_snippet)
        element_pos = html_snippet.find(str(element)[:50])
        position_ratio = element_pos / snippet_len if snippet_len > 0 else 0.5
        features.append(position_ratio)

        # Is at top (first 20%)
        features.append(1.0 if position_ratio < 0.2 else 0.0)

        # Is at bottom (last 20%)
        features.append(1.0 if position_ratio > 0.8 else 0.0)

        # Parent tag encoding
        parent_map = {'body': 1, 'main': 2, 'div': 3, 'section': 4, 'article': 5}
        parent_tag = element.parent.name if element.parent else None
        features.append(parent_map.get(parent_tag, 0))

        # Has container class in parents
        has_container = False
        parent = element.parent
        depth = 0
        while parent and depth < 5:
            parent_classes = ' '.join(parent.get('class', []))
            if 'container' in parent_classes.lower():
                has_container = True
                break
            parent = parent.parent
            depth += 1
        features.append(1.0 if has_container else 0.0)

        # Has wrapper class in parents
        has_wrapper = False
        parent = element.parent
        depth = 0
        while parent and depth < 5:
            parent_classes = ' '.join(parent.get('class', []))
            if 'wrapper' in parent_classes.lower():
                has_wrapper = True
                break
            parent = parent.parent
            depth += 1
        features.append(1.0 if has_wrapper else 0.0)

        # Element size (HTML length)
        features.append(len(str(element)))

        # Normalized size (log scale)
        features.append(np.log1p(len(str(element))))

        # Has role attribute
        features.append(1.0 if element.get('role') else 0.0)

        # Has aria attributes
        aria_attrs = [k for k in element.attrs.keys() if k.startswith('aria-')]
        features.append(len(aria_attrs))

        return features

    def _component_type_features(self, component_type: str) -> List[float]:
        """One-hot encode component type (top 5 types)."""
        top_types = ['hero', 'button', 'header', 'footer', 'product-card']
        features = [1.0 if component_type == t else 0.0 for t in top_types]
        return features

    def get_feature_names(self) -> List[str]:
        """Return feature names for debugging."""
        names = []

        # Structural (10)
        names.extend([
            'tag_name', 'num_children', 'depth', 'has_id', 'has_class',
            'num_classes', 'num_data_attrs', 'has_style', 'num_siblings', 'is_first_child'
        ])

        # Content (10)
        names.extend([
            'text_length', 'num_images', 'num_links', 'num_buttons', 'num_forms',
            'num_headings', 'num_lists', 'num_svgs', 'text_html_ratio', 'has_price'
        ])

        # Style (15)
        keywords = [
            'hero', 'banner', 'header', 'footer', 'nav',
            'card', 'product', 'category', 'badge', 'sale',
            'carousel', 'slider', 'tab', 'accordion', 'modal'
        ]
        names.extend([f'class_{k}' for k in keywords])

        # Context (10)
        names.extend([
            'position_ratio', 'is_top', 'is_bottom', 'parent_tag',
            'has_container_parent', 'has_wrapper_parent', 'element_size',
            'element_size_log', 'has_role', 'num_aria_attrs'
        ])

        # Component type (5)
        names.extend(['type_hero', 'type_button', 'type_header', 'type_footer', 'type_product_card'])

        return names
