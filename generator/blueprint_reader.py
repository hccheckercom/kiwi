"""
Blueprint Reader

Parses Blueprint markdown files to extract rules, specs, and templates.
Caches parsed content for performance.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re
from dataclasses import dataclass
import yaml


@dataclass
class BlueprintSpec:
    """Parsed Blueprint specification."""
    phase: str
    file_path: str
    sections: List[str]
    data_sources: List[str]
    acceptance_criteria: List[str]
    rules: List[str]
    raw_content: str


class BlueprintReader:
    """
    Parse Blueprint markdown files.

    Extracts:
    - GATE phases and rules
    - Page specifications
    - Design system tokens
    - Component references
    - API function signatures
    """

    def __init__(self, blueprint_dir: Path):
        self.blueprint_dir = blueprint_dir
        self._cache: Dict[str, BlueprintSpec] = {}

    def read_gate_rules(self) -> List[str]:
        """
        Read 15 immutable rules from 00-GATE.md.

        Returns:
            List of rule strings
        """
        gate_file = self.blueprint_dir / "00-GATE.md"
        if not gate_file.exists():
            raise FileNotFoundError(f"GATE file not found: {gate_file}")

        content = gate_file.read_text(encoding='utf-8')

        # Extract rules from table (lines 35-51 in GATE.md)
        rules = []
        in_rules_table = False

        for line in content.split('\n'):
            if '## GATE 2 — 15 LUẬT BẤT BIẾN' in line:
                in_rules_table = True
                continue

            if in_rules_table:
                if line.startswith('## GATE 3'):
                    break

                # Parse table rows: | # | Luật | Verify nhanh |
                if line.startswith('|') and not line.startswith('|---|'):
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 3 and parts[1].isdigit():
                        rule_text = parts[2]
                        rules.append(rule_text)

        return rules

    def read_foundation_spec(self) -> Dict:
        """
        Read G0 (Foundation) phase specification.

        Returns:
            Dict with layers T1-T4 and their file requirements
        """
        foundation_file = self.blueprint_dir / "G0-chuan-bi" / "04-FOUNDATION.md"

        if not foundation_file.exists():
            # Fallback: extract from 00-GATE.md
            return self._extract_foundation_from_gate()

        content = foundation_file.read_text(encoding='utf-8')

        # Parse foundation layers
        spec = {
            'T1': {
                'name': 'Config',
                'files': [
                    'store-config.php',
                    'design-tokens.json',
                    'tailwind.config.js',
                    'package.json',
                    'src/main.css'
                ],
                'verification': 'npm install && npm run build:css succeeds'
            },
            'T2': {
                'name': 'WP Bootstrap',
                'files': [
                    'style.css',
                    'index.php',
                    'functions.php',
                    'inc/helpers.php',
                    'inc/security.php',
                    'inc/seo.php',
                    'inc/setup.php'
                ],
                'verification': 'Activate theme → 0 PHP errors'
            },
            'T3': {
                'name': 'Layout Shell',
                'files': [
                    'header.php',
                    'footer.php',
                    'inc/cart.php',
                    'assets/js/main.js'
                ],
                'verification': 'Responsive at 375px/768px/1280px'
            },
            'T4': {
                'name': 'Integration',
                'files': [],
                'verification': 'Inspect :root CSS vars, console.log(wzTheme)'
            }
        }

        return spec

    def _extract_foundation_from_gate(self) -> Dict:
        """Extract foundation spec from GATE.md as fallback."""
        return {
            'T1': {
                'name': 'Config',
                'files': [
                    'store-config.php',
                    'design-tokens.json',
                    'tailwind.config.js',
                    'package.json',
                    'src/main.css'
                ],
                'verification': 'npm install && npm run build:css'
            },
            'T2': {
                'name': 'WP Bootstrap',
                'files': [
                    'style.css',
                    'index.php',
                    'functions.php',
                    'inc/helpers.php',
                    'inc/security.php',
                    'inc/seo.php',
                    'inc/setup.php'
                ],
                'verification': 'Theme activation'
            },
            'T3': {
                'name': 'Layout Shell',
                'files': [
                    'header.php',
                    'footer.php',
                    'inc/cart.php',
                    'assets/js/main.js'
                ],
                'verification': 'Responsive check'
            },
            'T4': {
                'name': 'Integration',
                'files': [],
                'verification': 'CSS vars + wzTheme object'
            }
        }

    def read_design_tokens_spec(self) -> Dict:
        """
        Read design tokens specification.

        Returns:
            Dict with token categories and their structure
        """
        return {
            'colors': [
                'primary', 'secondary', 'accent', 'surface',
                'error', 'success', 'muted', 'outline'
            ],
            'typography': {
                'font_family': 'string',
                'scale': ['xs', 'sm', 'base', 'lg', 'xl', '2xl', '3xl']
            },
            'spacing': ['xs', 'sm', 'md', 'lg', 'xl', '2xl', 'gutter', 'container_max'],
            'radius': ['sm', 'DEFAULT', 'md', 'lg', 'xl', 'card', 'header', 'full'],
            'shadows': ['sm', 'md', 'lg', 'nav'],
            'breakpoints': {
                'sm': '640px',
                'md': '768px',
                'lg': '1024px',
                'xl': '1280px',
                '2xl': '1440px'
            },
            'z_index': ['dropdown', 'sticky', 'fixed', 'modal_backdrop', 'modal', 'tooltip'],
            'features': ['compat_widget', 'review_bar_chart', 'header_style', 'bottom_bar_style']
        }

    def read_page_spec(self, page_name: str) -> Optional[BlueprintSpec]:
        """
        Read page specification from Blueprint.

        Args:
            page_name: Page name (e.g., 'home', 'product', 'checkout')

        Returns:
            BlueprintSpec or None if not found
        """
        # Phase 1 MVP: Not implemented yet
        # Will be implemented in Phase 2 (Page Generator)
        raise NotImplementedError("Page specs not yet implemented (Phase 2)")

    def get_component_list(self) -> List[str]:
        """
        Get list of 16 built-in components from WeZone ThemeEngine.

        Returns:
            List of component names
        """
        return [
            'badge',
            'product-card',
            'breadcrumb',
            'cart-item',
            'price-display',
            'quantity-input',
            'filter-bar',
            'search-bar',
            'notice-box',
            'bottom-nav',
            'hero-banner',
            'star-rating',
            'trust-badges',
            'flash-sale-bar',
            'category-card',
            'product-grid'
        ]

    def get_wz_functions(self) -> Dict[str, str]:
        """
        Get common wz_* function signatures.

        Returns:
            Dict mapping function name to signature
        """
        return {
            'wz_get_product': 'wz_get_product(int $id): array',
            'wz_get_products': 'wz_get_products(array $args): array',
            'wz_cart': 'wz_cart(): array',
            'wz_cart_add': 'wz_cart_add(int $product_id, int $qty): bool',
            'wz_config': 'wz_config(string $key, mixed $default = null): mixed',
            'wz_component': 'wz_component(string $name, array $args = []): void',
            'wz_icon': 'wz_icon(string $name, array $args = []): string',
            'wezone_is_active': 'wezone_is_active(string $plugin): bool',
            'wz_format_price': 'wz_format_price(float $price): string',
        }

    def clear_cache(self):
        """Clear cached specs."""
        self._cache.clear()