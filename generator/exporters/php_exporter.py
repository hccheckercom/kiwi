"""PHP exporter — export design tokens to PHP array.

Output format:
<?php
return [
    'colors' => [
        'primary' => '#3b82f6',
        'secondary' => '#8b5cf6',
    ],
    'typography' => [
        'h1' => [
            'fontSize' => '2.5rem',
            'lineHeight' => '1.2',
        ],
    ],
    'spacing' => [
        '4' => '1rem',
        '8' => '2rem',
    ],
];
"""

from typing import Dict, Any

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from exporters.base import BaseExporter
from tokens.schema import DesignTokens


class PHPExporter(BaseExporter):
    """Export tokens to PHP array (for store-config.php)."""

    def __init__(self, options: Dict[str, Any] = None):
        """Initialize PHP exporter.

        Options:
            indent: Indent size (default: 4)
            short_array: Use short array syntax [] (default: True)
        """
        super().__init__(options)
        self.indent = self.options.get('indent', 4)
        self.short_array = self.options.get('short_array', True)

    def export(self, tokens: DesignTokens) -> str:
        """Export tokens to PHP array.

        Args:
            tokens: Validated DesignTokens schema

        Returns:
            PHP array declaration
        """
        lines = ["<?php", "return ["]

        # Export colors
        if tokens.colors:
            lines.append(f"{' ' * self.indent}'colors' => [")
            lines.extend(self._export_category(tokens.colors, level=2))
            lines.append(f"{' ' * self.indent}],")

        # Export typography
        if tokens.typography:
            lines.append(f"{' ' * self.indent}'typography' => [")
            lines.extend(self._export_typography(tokens.typography, level=2))
            lines.append(f"{' ' * self.indent}],")

        # Export spacing
        if tokens.spacing:
            lines.append(f"{' ' * self.indent}'spacing' => [")
            lines.extend(self._export_category(tokens.spacing, level=2))
            lines.append(f"{' ' * self.indent}],")

        # Export border radius
        if tokens.borderRadius:
            lines.append(f"{' ' * self.indent}'borderRadius' => [")
            lines.extend(self._export_category(tokens.borderRadius, level=2))
            lines.append(f"{' ' * self.indent}],")

        lines.append("];")

        return "\n".join(lines)

    def _export_category(self, category: Dict, level: int = 1) -> list:
        """Export single category recursively.

        Args:
            category: Category dict
            level: Nesting level for indentation

        Returns:
            List of PHP array lines
        """
        lines = []
        indent = " " * (self.indent * level)

        for key, value in category.items():
            php_key = self._format_key(key)

            if isinstance(value, dict):
                # Check if it's a token leaf node
                if "value" in value:
                    php_value = self._format_value(value["value"])
                    lines.append(f"{indent}{php_key} => {php_value},")
                elif hasattr(value, 'value'):
                    php_value = self._format_value(value.value)
                    lines.append(f"{indent}{php_key} => {php_value},")
                else:
                    # Nested category
                    lines.append(f"{indent}{php_key} => [")
                    lines.extend(self._export_category(value, level + 1))
                    lines.append(f"{indent}],")
            elif hasattr(value, 'value'):
                php_value = self._format_value(value.value)
                lines.append(f"{indent}{php_key} => {php_value},")
            else:
                php_value = self._format_value(value)
                lines.append(f"{indent}{php_key} => {php_value},")

        return lines

    def _export_typography(self, typography: Dict, level: int = 1) -> list:
        """Export typography tokens.

        Args:
            typography: Typography dict
            level: Nesting level

        Returns:
            List of PHP array lines
        """
        lines = []
        indent = " " * (self.indent * level)

        for scale_name, scale_props in typography.items():
            php_key = self._format_key(scale_name)

            if isinstance(scale_props, dict):
                if hasattr(scale_props, 'fontSize'):
                    # Pydantic TypographyToken - convert to dict
                    lines.append(f"{indent}{php_key} => [")
                    sub_indent = " " * (self.indent * (level + 1))

                    if scale_props.fontSize:
                        font_size = scale_props.fontSize.value if hasattr(scale_props.fontSize, 'value') else scale_props.fontSize
                        lines.append(f"{sub_indent}'fontSize' => {self._format_value(font_size)},")
                    if scale_props.lineHeight:
                        lines.append(f"{sub_indent}'lineHeight' => {self._format_value(scale_props.lineHeight)},")
                    if scale_props.fontWeight:
                        lines.append(f"{sub_indent}'fontWeight' => {self._format_value(scale_props.fontWeight)},")
                    if scale_props.fontFamily:
                        font_family = scale_props.fontFamily if isinstance(scale_props.fontFamily, str) else ', '.join(scale_props.fontFamily)
                        lines.append(f"{sub_indent}'fontFamily' => {self._format_value(font_family)},")

                    lines.append(f"{indent}],")
                else:
                    # Dict format
                    lines.append(f"{indent}{php_key} => [")
                    sub_indent = " " * (self.indent * (level + 1))

                    for prop, value in scale_props.items():
                        if isinstance(value, dict) and "value" in value:
                            php_value = value["value"]
                        elif hasattr(value, 'value'):
                            php_value = value.value
                        else:
                            php_value = value

                        lines.append(f"{sub_indent}'{prop}' => {self._format_value(php_value)},")

                    lines.append(f"{indent}],")

        return lines

    def _format_key(self, key: str) -> str:
        """Format key for PHP array.

        Args:
            key: Token key

        Returns:
            Formatted PHP key
        """
        # If key is numeric or contains special chars, quote it
        if key.isdigit() or not key.replace('-', '').replace('_', '').isalnum():
            return f"'{key}'"
        return f"'{key}'"

    def _format_value(self, value: Any) -> str:
        """Format value for PHP.

        Args:
            value: Token value

        Returns:
            Formatted PHP value
        """
        if isinstance(value, str):
            # Escape single quotes
            escaped = value.replace("'", "\\'")
            return f"'{escaped}'"
        elif isinstance(value, bool):
            return 'true' if value else 'false'
        elif isinstance(value, (int, float)):
            return str(value)
        elif value is None:
            return 'null'
        else:
            return f"'{str(value)}'"
