"""HTML to PHP Converter — Convert detected HTML components to PHP templates"""

import re
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup, Tag, NavigableString


class HTMLToPHPConverter:
    """
    Convert HTML components to PHP templates with Wezone data bindings.

    Usage:
        converter = HTMLToPHPConverter()
        php_code = converter.convert_component(component)
    """

    # Data source mappings
    DATA_SOURCES = {
        'product-card': {
            'source': 'wz_get_products()',
            'loop_var': '$product',
            'fields': {
                'image': '$product["thumbnail"]',
                'title': '$product["name"]',
                'price': '$product["price"]',
                'sale_price': '$product["sale_price"]',
                'on_sale': '$product["on_sale"]',
                'permalink': 'wz_get_permalink($product)',
            }
        },
        'category-grid': {
            'source': 'wz_get_categories()',
            'loop_var': '$category',
            'fields': {
                'name': '$category["name"]',
                'icon': '$category["icon"]',
                'permalink': 'wz_get_category_link($category)',
            }
        },
        'hero': {
            'source': 'wz_config("hero")',
            'fields': {
                'title': 'wz_config("hero.title")',
                'subtitle': 'wz_config("hero.subtitle")',
                'cta_text': 'wz_config("hero.cta_text")',
                'cta_link': 'wz_config("hero.cta_link")',
            }
        },
        'trust-badges': {
            'source': 'wz_config("trust_badges")',
            'loop_var': '$badge',
            'fields': {
                'icon': '$badge["icon"]',
                'text': '$badge["text"]',
            }
        },
        'footer-links': {
            'source': 'wz_config("footer.links")',
            'loop_var': '$link',
            'fields': {
                'text': '$link["text"]',
                'url': '$link["url"]',
            }
        }
    }

    def __init__(self):
        pass

    def convert_component(self, component: Dict[str, Any]) -> str:
        """
        Convert detected component to PHP template code.

        Args:
            component: Component dict from ComponentDetector

        Returns:
            PHP template code string
        """
        element = component['element']
        component_type = component['type']

        # Get HTML string
        html = str(element)

        # Apply transformations
        php = self._transform_html_to_php(html, component_type, element)

        return php

    def _transform_html_to_php(self, html: str, component_type: str, element: Tag) -> str:
        """Apply transformation rules to convert HTML to PHP."""

        # Parse HTML
        soup = BeautifulSoup(html, 'html.parser')
        root = soup.find()

        if not root:
            return html

        # Apply transformations based on component type
        if component_type == 'card':
            self._transform_card(root)
        elif component_type == 'button':
            self._transform_button(root)
        elif component_type == 'hero':
            self._transform_hero(root)
        elif component_type == 'carousel':
            self._transform_carousel(root)
        elif component_type == 'grid':
            self._transform_grid(root)

        # Generic transformations
        self._replace_hardcoded_text(root)
        self._replace_icons(root)
        self._replace_images(root)
        self._replace_links(root)

        # Convert to string and unescape PHP tags
        import html
        output = str(root)
        output = html.unescape(output)  # &lt;?php → <?php
        return output

    def _transform_card(self, element: Tag):
        """Transform card component."""
        # Find title (h1-h6)
        title = element.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        if title and title.string:
            title.string.replace_with('<?php echo wz_config("card.title"); ?>')

        # Find description (p)
        description = element.find('p')
        if description and description.string:
            description.string.replace_with('<?php echo wz_config("card.description"); ?>')

    def _transform_button(self, element: Tag):
        """Transform button component."""
        # Replace button text
        if element.string:
            element.string.replace_with('<?php echo wz_config("button.text"); ?>')

        # Replace href if <a>
        if element.name == 'a' and element.get('href'):
            element['href'] = '<?php echo wz_config("button.link"); ?>'

    def _transform_hero(self, element: Tag):
        """Transform hero section."""
        # Find h1
        h1 = element.find('h1')
        if h1 and h1.string:
            h1.string.replace_with('<?php echo wz_config("hero.title"); ?>')

        # Find subtitle (p after h1)
        if h1:
            subtitle = h1.find_next_sibling('p')
            if subtitle and subtitle.string:
                subtitle.string.replace_with('<?php echo wz_config("hero.subtitle"); ?>')

        # Find CTA button
        button = element.find('button')
        if button and button.string:
            button.string.replace_with('<?php echo wz_config("hero.cta_text"); ?>')

    def _transform_carousel(self, element: Tag):
        """Transform carousel/slider."""
        # Find repeating items
        items = element.find_all(recursive=False)
        if len(items) >= 2:
            # Wrap in PHP loop
            first_item = items[0]
            loop_html = f'<?php foreach (wz_config("carousel.items") as $item): ?>\n{first_item}\n<?php endforeach; ?>'

            # Remove other items (they're duplicates)
            for item in items[1:]:
                item.decompose()

    def _transform_grid(self, element: Tag):
        """Transform grid layout."""
        # Check if grid contains cards
        cards = element.find_all(class_=re.compile(r'rounded-.*shadow-'))
        if len(cards) >= 2:
            # Wrap in PHP loop
            first_card = cards[0]
            # Keep first card, remove duplicates
            for card in cards[1:]:
                card.decompose()

    def _replace_hardcoded_text(self, element: Tag):
        """Replace hardcoded Vietnamese text with wz_config() calls."""
        # Find all text nodes
        for text_node in element.find_all(string=True):
            if isinstance(text_node, NavigableString):
                text = str(text_node).strip()

                # Skip if already PHP code
                if '<?php' in text:
                    continue

                # Skip if empty or whitespace
                if not text or text.isspace():
                    continue

                # Skip if only symbols/numbers
                if re.match(r'^[\d\s\W]+$', text):
                    continue

                # Replace with wz_config placeholder
                # Use sanitized text as key
                key = self._sanitize_key(text)
                text_node.replace_with(f'<?php echo wz_config("{key}"); ?>')

    def _replace_icons(self, element: Tag):
        """Replace Material Symbols icons with wz_icon() calls."""
        icons = element.find_all(class_='material-symbols-outlined')
        for icon in icons:
            if icon.string and '<?php' not in str(icon.string):
                icon_name = str(icon.string).strip()
                icon.string.replace_with(f'<?php wz_icon("{icon_name}"); ?>')

    def _replace_images(self, element: Tag):
        """Replace image src with dynamic PHP."""
        images = element.find_all('img')
        for img in images:
            if img.get('src'):
                # Check if product image context
                if 'product' in str(element).lower():
                    img['src'] = '<?php echo wz_get_thumbnail($product); ?>'
                else:
                    img['src'] = '<?php echo wz_config("image.url"); ?>'

            if img.get('alt'):
                img['alt'] = '<?php echo wz_config("image.alt"); ?>'

    def _replace_links(self, element: Tag):
        """Replace links with dynamic PHP."""
        links = element.find_all('a')
        for link in links:
            if link.get('href') and not link['href'].startswith('<?php'):
                # Check context
                if 'product' in str(element).lower():
                    link['href'] = '<?php echo wz_get_permalink($product); ?>'
                elif 'category' in str(element).lower():
                    link['href'] = '<?php echo wz_get_category_link($category); ?>'
                else:
                    link['href'] = '<?php echo wz_config("link.url"); ?>'

    def _sanitize_key(self, text: str) -> str:
        """Convert text to config key (lowercase, underscore-separated)."""
        # Remove special chars, convert to lowercase
        key = re.sub(r'[^\w\s]', '', text.lower())
        # Replace spaces with underscores
        key = re.sub(r'\s+', '_', key)
        # Truncate to 50 chars
        key = key[:50]
        return key

    def generate_php_file(self, components: List[Dict], output_path: str):
        """
        Generate complete PHP template file from components.

        Args:
            components: List of detected components
            output_path: Output file path
        """
        lines = [
            "<?php",
            "/**",
            " * Template: Auto-generated by Kiwi UI Generator V2",
            " * DO NOT edit manually — regenerate from demo",
            " */",
            "",
            "// Guard: Check if Wezone is active",
            "if (!function_exists('wz_config')) {",
            "    return;",
            "}",
            "",
        ]

        # Convert each component
        for i, component in enumerate(components):
            lines.append(f"<!-- Component {i+1}: {component['type']} -->")
            php_code = self.convert_component(component)
            lines.append(php_code)
            lines.append("")

        # Write to file
        from pathlib import Path
        Path(output_path).write_text('\n'.join(lines), encoding='utf-8')


def main():
    """CLI for testing HTML to PHP conversion."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from generator.parsers.component_detector import ComponentDetector

    if len(sys.argv) < 2:
        print("Usage: python html_to_php.py <html_file>")
        sys.exit(1)

    html_path = Path(sys.argv[1])
    html_content = html_path.read_text(encoding='utf-8')

    # Detect components
    detector = ComponentDetector()
    components = detector.detect_components(html_content)

    print(f"Detected {len(components)} components\n")

    # Convert first 5 components
    converter = HTMLToPHPConverter()
    for i, comp in enumerate(components[:5], 1):
        print(f"=== Component {i}: {comp['type']} (confidence: {comp['confidence']:.2f}) ===")
        php_code = converter.convert_component(comp)
        print(php_code[:500])  # Show first 500 chars
        print()


if __name__ == "__main__":
    main()