"""Component Detector — Detect component types from HTML structure using heuristic patterns"""

import re
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup, Tag


class ComponentDetector:
    """
    Detect component types from HTML structure using heuristic patterns.

    Usage:
        detector = ComponentDetector()
        components = detector.detect_components(html_content)
    """

    # Component patterns with scoring rules
    PATTERNS = {
        'header': {
            'tags': ['header', 'nav'],
            'classes': ['sticky', 'fixed', 'top-0', 'z-50', 'z-40'],
            'structure': 'contains_nav_or_logo',
            'position': 'top',
            'min_score': 0.7
        },
        'hero': {
            'tags': ['section'],
            'classes': ['h-screen', 'h-[600px]', 'h-[500px]', 'hero', 'banner'],
            'structure': 'has_h1_and_button',
            'position': 'first_section',
            'min_score': 0.7
        },
        'card': {
            'tags': ['div', 'article'],
            'classes': ['rounded-', 'shadow-', 'p-', 'card', 'bg-'],
            'structure': 'icon_title_text',
            'min_score': 0.6
        },
        'button': {
            'tags': ['button', 'a'],
            'classes': ['px-', 'py-', 'rounded-', 'btn', 'button'],
            'structure': 'clickable',
            'min_score': 0.5
        },
        'badge': {
            'tags': ['span', 'div'],
            'classes': ['rounded-full', 'text-xs', 'text-sm', 'inline-flex', 'badge'],
            'structure': 'small_inline',
            'min_score': 0.6
        },
        'carousel': {
            'tags': ['div', 'section'],
            'classes': ['overflow-hidden', 'flex', 'animate-', 'carousel', 'slider'],
            'structure': 'scrollable_items',
            'min_score': 0.7
        },
        'grid': {
            'tags': ['div', 'section'],
            'classes': ['grid', 'grid-cols-'],
            'structure': 'multiple_children',
            'min_score': 0.6
        },
        'icon': {
            'tags': ['span', 'i'],
            'classes': ['material-symbols-outlined', 'icon', 'fa-'],
            'min_score': 0.8
        },
        'image': {
            'tags': ['img'],
            'classes': ['object-cover', 'object-contain'],
            'min_score': 0.5
        },
        'section': {
            'tags': ['section'],
            'classes': ['py-', 'max-w-'],
            'structure': 'has_heading',
            'min_score': 0.5
        },
        'container': {
            'tags': ['div'],
            'classes': ['max-w-', 'mx-auto', 'px-', 'container'],
            'min_score': 0.6
        },
        'nav-link': {
            'tags': ['a'],
            'classes': ['hover:', 'transition-'],
            'structure': 'in_nav',
            'min_score': 0.6
        },
        'input': {
            'tags': ['input', 'textarea', 'select'],
            'classes': ['border', 'rounded-'],
            'min_score': 0.7
        },
        'modal': {
            'tags': ['div'],
            'classes': ['fixed', 'inset-0', 'z-50', 'modal'],
            'min_score': 0.8
        },
        'dropdown': {
            'tags': ['div'],
            'classes': ['absolute', 'top-full', 'shadow-', 'dropdown'],
            'min_score': 0.7
        },
        'tabs': {
            'tags': ['div'],
            'classes': ['flex', 'border-b', 'gap-', 'tabs'],
            'structure': 'multiple_clickable',
            'min_score': 0.7
        },
        'accordion': {
            'tags': ['div'],
            'classes': ['collapsible', 'transition-', 'accordion'],
            'structure': 'expandable',
            'min_score': 0.7
        },
        'breadcrumb': {
            'tags': ['nav', 'div'],
            'classes': ['flex', 'gap-', 'text-sm', 'breadcrumb'],
            'structure': 'has_separators',
            'min_score': 0.7
        },
        'footer': {
            'tags': ['footer'],
            'classes': ['bg-', 'py-'],
            'position': 'bottom',
            'min_score': 0.7
        },
        'form': {
            'tags': ['form'],
            'structure': 'has_inputs',
            'min_score': 0.8
        }
    }

    def __init__(self):
        self.detected = []

    def detect_components(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Scan HTML tree and detect component instances.

        Args:
            html_content: HTML string

        Returns:
            List of detected components with type, element, confidence, location
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        self.detected = []

        # Scan all elements
        for element in soup.find_all(True):
            if not isinstance(element, Tag):
                continue

            # Score against all patterns
            for component_type, pattern in self.PATTERNS.items():
                score = self._score_element(element, pattern, soup)

                if score >= pattern['min_score']:
                    self.detected.append({
                        'type': component_type,
                        'element': element,
                        'confidence': score,
                        'location': self._get_location(element),
                        'classes': element.get('class', []),
                        'text_preview': self._get_text_preview(element)
                    })

        # Sort by confidence (highest first)
        self.detected.sort(key=lambda x: x['confidence'], reverse=True)

        # Remove duplicates (same element detected as multiple types)
        self.detected = self._deduplicate()

        return self.detected

    def _score_element(self, element: Tag, pattern: Dict, soup: BeautifulSoup) -> float:
        """Score element against pattern with enhanced confidence rules."""
        score = 0.0
        component_type = None

        # Find component type from pattern
        for ctype, cpat in self.PATTERNS.items():
            if cpat == pattern:
                component_type = ctype
                break

        # Tag match: +0.3
        if 'tags' in pattern and element.name in pattern['tags']:
            score += 0.3

        # Class match: +0.1 per class (max +0.4)
        if 'classes' in pattern:
            element_classes = ' '.join(element.get('class', []))
            matched = sum(1 for c in pattern['classes'] if c in element_classes)
            score += min(matched * 0.1, 0.4)

        # Structure match: +0.3
        if 'structure' in pattern:
            if self._matches_structure(element, pattern['structure'], soup):
                score += 0.3

        # Position match: +0.2
        if 'position' in pattern:
            if self._matches_position(element, pattern['position'], soup):
                score += 0.2

        # Enhanced confidence rules per component type
        if component_type:
            score += self._apply_confidence_boost(element, component_type, soup)

        return min(score, 1.0)

    def _matches_structure(self, element: Tag, structure: str, soup: BeautifulSoup) -> bool:
        """Check if element matches structural pattern."""
        if structure == 'contains_nav_or_logo':
            return bool(element.find('nav') or element.find(class_=re.compile(r'logo')))

        elif structure == 'has_h1_and_button':
            return bool(element.find('h1') and element.find('button'))

        elif structure == 'icon_title_text':
            has_icon = bool(element.find(class_=re.compile(r'icon|material-symbols')))
            has_title = bool(element.find(['h1', 'h2', 'h3', 'h4']))
            has_text = bool(element.find('p'))
            return has_icon and has_title and has_text

        elif structure == 'clickable':
            return element.name in ['button', 'a']

        elif structure == 'small_inline':
            classes = ' '.join(element.get('class', []))
            return 'inline' in classes or 'flex' in classes

        elif structure == 'scrollable_items':
            return len(element.find_all(recursive=False)) >= 3

        elif structure == 'multiple_children':
            return len(element.find_all(recursive=False)) >= 2

        elif structure == 'has_heading':
            return bool(element.find(['h1', 'h2', 'h3']))

        elif structure == 'in_nav':
            return bool(element.find_parent('nav'))

        elif structure == 'multiple_clickable':
            return len(element.find_all(['a', 'button'])) >= 2

        elif structure == 'expandable':
            return 'transition' in ' '.join(element.get('class', []))

        elif structure == 'has_separators':
            text = element.get_text()
            return '/' in text or '>' in text or '›' in text

        elif structure == 'has_inputs':
            return len(element.find_all(['input', 'textarea', 'select'])) >= 1

        return False

    def _matches_position(self, element: Tag, position: str, soup: BeautifulSoup) -> bool:
        """Check if element matches position pattern."""
        if position == 'top':
            # First 3 elements in body
            body = soup.find('body')
            if body:
                top_elements = list(body.find_all(recursive=False))[:3]
                return element in top_elements
            return False

        elif position == 'first_section':
            sections = soup.find_all('section')
            return sections and element == sections[0]

        elif position == 'bottom':
            # Last 3 elements in body
            body = soup.find('body')
            if body:
                bottom_elements = list(body.find_all(recursive=False))[-3:]
                return element in bottom_elements
            return False

        return False

    def _get_location(self, element: Tag) -> Dict[str, Any]:
        """Get element location info."""
        return {
            'tag': element.name,
            'id': element.get('id'),
            'depth': len(list(element.parents))
        }

    def _get_text_preview(self, element: Tag, max_length: int = 50) -> str:
        """Get text preview from element."""
        text = element.get_text(strip=True)
        if len(text) > max_length:
            return text[:max_length] + '...'
        return text

    def _deduplicate(self) -> List[Dict[str, Any]]:
        """Remove duplicate detections (same element, keep highest confidence)."""
        seen = {}
        result = []

        for item in self.detected:
            element_id = id(item['element'])

            if element_id not in seen or item['confidence'] > seen[element_id]['confidence']:
                seen[element_id] = item

        return list(seen.values())

    def _apply_confidence_boost(self, element: Tag, component_type: str, soup: BeautifulSoup) -> float:
        """Apply component-specific confidence boosts based on semantic signals.

        Returns additional confidence score (0.0 to 0.3) based on component-specific rules.
        """
        boost = 0.0
        element_classes = ' '.join(element.get('class', []))

        if component_type == 'hero':
            # Hero-specific signals
            if element.find('h1'):  # Has main heading
                boost += 0.10
            if element.find('button') or element.find('a', class_=re.compile(r'btn|button')):  # Has CTA
                boost += 0.05
            if element.find('img') or 'background' in element_classes:  # Has visual
                boost += 0.05
            # Only one hero per page (uniqueness)
            heroes = soup.find_all(class_=re.compile(r'hero|banner'))
            if len(heroes) == 1:
                boost += 0.05

        elif component_type == 'button':
            # Button-specific signals
            text = element.get_text(strip=True)
            if len(text) < 50:  # Short text (typical for buttons)
                boost += 0.10
            if element.find('svg') or element.find(class_=re.compile(r'icon')):  # Has icon
                boost += 0.05
            # Is inside hero/CTA section
            parent_classes = ' '.join(element.parent.get('class', [])) if element.parent else ''
            if 'hero' in parent_classes or 'cta' in parent_classes:
                boost += 0.05

        elif component_type == 'header':
            # Header-specific signals
            if element.find('nav'):  # Has navigation
                boost += 0.10
            if element.find(class_=re.compile(r'logo')):  # Has logo
                boost += 0.05
            # Is at very top of page
            body = soup.find('body')
            if body and body.find() == element:
                boost += 0.05

        elif component_type == 'footer':
            # Footer-specific signals
            if element.find('nav') or len(element.find_all('a')) >= 5:  # Has links
                boost += 0.10
            # Is at very bottom of page
            body = soup.find('body')
            if body:
                children = list(body.find_all(recursive=False))
                if children and children[-1] == element:
                    boost += 0.05

        elif component_type == 'card':
            # Card-specific signals
            has_image = bool(element.find('img'))
            has_title = bool(element.find(['h1', 'h2', 'h3', 'h4']))
            has_text = bool(element.find('p'))
            if has_image and has_title:
                boost += 0.10
            if has_text:
                boost += 0.05

        elif component_type == 'grid':
            # Grid-specific signals
            children = element.find_all(recursive=False)
            if len(children) >= 3:  # Has multiple items
                boost += 0.10
            # Children have similar structure (likely grid items)
            if len(children) >= 2:
                first_child_tags = {c.name for c in children[0].find_all(recursive=False)}
                similar = sum(1 for child in children[1:]
                            if {c.name for c in child.find_all(recursive=False)} == first_child_tags)
                if similar >= len(children) - 1:  # All children similar
                    boost += 0.05

        elif component_type == 'carousel':
            # Carousel-specific signals
            if 'overflow' in element_classes:
                boost += 0.05
            if len(element.find_all(recursive=False)) >= 3:  # Multiple slides
                boost += 0.10

        elif component_type == 'modal':
            # Modal-specific signals
            if 'fixed' in element_classes and 'z-' in element_classes:
                boost += 0.10
            if element.find(class_=re.compile(r'backdrop|overlay')):
                boost += 0.05

        elif component_type == 'form':
            # Form-specific signals
            inputs = element.find_all(['input', 'textarea', 'select'])
            if len(inputs) >= 2:  # Multiple inputs
                boost += 0.10
            if element.find('button', type='submit'):  # Has submit button
                boost += 0.05

        return min(boost, 0.3)  # Cap at +0.3

    def get_summary(self) -> Dict[str, int]:
        """Get summary of detected components by type."""
        summary = {}
        for item in self.detected:
            component_type = item['type']
            summary[component_type] = summary.get(component_type, 0) + 1
        return summary


def main():
    """CLI for testing component detection."""
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print("Usage: python component_detector.py <html_file>")
        sys.exit(1)

    html_path = Path(sys.argv[1])
    html_content = html_path.read_text(encoding='utf-8')

    detector = ComponentDetector()
    components = detector.detect_components(html_content)

    print(f"\nDetected {len(components)} components:\n")

    for i, comp in enumerate(components[:20], 1):  # Show top 20
        print(f"{i}. {comp['type']} (confidence: {comp['confidence']:.2f})")
        print(f"   Tag: <{comp['location']['tag']}> | Classes: {', '.join(comp['classes'][:3])}")
        # Encode text preview to avoid Unicode errors
        text = comp['text_preview'].encode('ascii', 'replace').decode('ascii')
        print(f"   Text: {text}")
        print()

    print("\nSummary by type:")
    summary = detector.get_summary()
    for comp_type, count in sorted(summary.items(), key=lambda x: x[1], reverse=True):
        print(f"  {comp_type}: {count}")


if __name__ == "__main__":
    main()