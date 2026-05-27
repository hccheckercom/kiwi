"""SCSS exporter — export design tokens to SCSS map.

Output format:
$tokens: (
  'color': (
    'primary': #3b82f6,
    'secondary': #8b5cf6
  ),
  'font': (
    'heading-h1-size': 2.5rem,
    'heading-h1-line-height': 1.2
  ),
  'spacing': (
    '4': 1rem,
    '8': 2rem
  )
);
"""

from typing import Dict, Any

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from exporters.base import BaseExporter
from tokens.schema import DesignTokens


class SCSSExporter(BaseExporter):
    """Export tokens to SCSS map."""

    def __init__(self, options: Dict[str, Any] = None):
        """Initialize SCSS exporter.

        Options:
            indent: Indent size (default: 2)
            map_name: Map variable name (default: "$tokens")
        """
        super().__init__(options)
        self.indent = self.options.get('indent', 2)
        self.map_name = self.options.get('map_name', '$tokens')

    def export(self, tokens: DesignTokens) -> str:
        """Export tokens to SCSS map.

        Args:
            tokens: Validated DesignTokens schema

        Returns:
            SCSS map declaration
        """
        lines = [f"{self.map_name}: ("]

        # Export colors
        if tokens.colors:
            lines.append(f"{' ' * self.indent}'color': (")
            lines.extend(self._export_category(tokens.colors, level=2))
            lines.append(f"{' ' * self.indent}),")

        # Export typography
        if tokens.typography:
            lines.append(f"{' ' * self.indent}'font': (")
            lines.extend(self._export_typography(tokens.typography, level=2))
            lines.append(f"{' ' * self.indent}),")

        # Export spacing
        if tokens.spacing:
            lines.append(f"{' ' * self.indent}'spacing': (")
            lines.extend(self._export_category(tokens.spacing, level=2))
            lines.append(f"{' ' * self.indent}),")

        # Export border radius
        if tokens.borderRadius:
            lines.append(f"{' ' * self.indent}'radius': (")
            lines.extend(self._export_category(tokens.borderRadius, level=2))
            lines.append(f"{' ' * self.indent}),")

        lines.append(");")

        return "\n".join(lines)

    def _export_category(self, category: Dict, level: int = 1) -> list:
        """Export single category recursively.

        Args:
            category: Category dict
            level: Nesting level for indentation

        Returns:
            List of SCSS map lines
        """
        lines = []
        indent = " " * (self.indent * level)

        for key, value in category.items():
            if isinstance(value, dict):
                # Check if it's a token leaf node
                if "value" in value:
                    scss_value = self._format_value(value["value"])
                    lines.append(f"{indent}'{key}': {scss_value},")
                elif hasattr(value, 'value'):
                    scss_value = self._format_value(value.value)
                    lines.append(f"{indent}'{key}': {scss_value},")
                else:
                    # Nested category
                    lines.append(f"{indent}'{key}': (")
                    lines.extend(self._export_category(value, level + 1))
                    lines.append(f"{indent}),")
            elif hasattr(value, 'value'):
                scss_value = self._format_value(value.value)
                lines.append(f"{indent}'{key}': {scss_value},")
            else:
                scss_value = self._format_value(value)
                lines.append(f"{indent}'{key}': {scss_value},")

        return lines

    def _export_typography(self, typography: Dict, level: int = 1) -> list:
        """Export typography tokens.

        Args:
            typography: Typography dict
            level: Nesting level

        Returns:
            List of SCSS map lines
        """
        lines = []
        indent = " " * (self.indent * level)

        for scale_name, scale_props in typography.items():
            if isinstance(scale_props, dict):
                if hasattr(scale_props, 'fontSize'):
                    # Pydantic TypographyToken
                    if scale_props.fontSize:
                        font_size = scale_props.fontSize.value if hasattr(scale_props.fontSize, 'value') else scale_props.fontSize
                        lines.append(f"{indent}'{scale_name}-size': {self._format_value(font_size)},")
                    if scale_props.lineHeight:
                        lines.append(f"{indent}'{scale_name}-line-height': {self._format_value(scale_props.lineHeight)},")
                    if scale_props.fontWeight:
                        lines.append(f"{indent}'{scale_name}-weight': {self._format_value(scale_props.fontWeight)},")
                    if scale_props.fontFamily:
                        font_family = scale_props.fontFamily if isinstance(scale_props.fontFamily, str) else ', '.join(scale_props.fontFamily)
                        lines.append(f"{indent}'{scale_name}-family': {self._format_value(font_family)},")
                else:
                    # Dict format
                    for prop, value in scale_props.items():
                        if isinstance(value, dict) and "value" in value:
                            scss_value = value["value"]
                        elif hasattr(value, 'value'):
                            scss_value = value.value
                        else:
                            scss_value = value

                        lines.append(f"{indent}'{scale_name}-{prop}': {self._format_value(scss_value)},")

        return lines

    def _format_value(self, value: Any) -> str:
        """Format value for SCSS.

        Args:
            value: Token value

        Returns:
            Formatted SCSS value
        """
        if isinstance(value, str):
            # Check if it needs quotes
            if value.startswith('#') or value.endswith(('px', 'rem', 'em', '%', 'vh', 'vw')):
                return value
            elif value.startswith(('rgb', 'rgba', 'hsl', 'hsla')):
                return value
            else:
                # String value needs quotes
                return f"'{value}'"
        elif isinstance(value, (int, float)):
            return str(value)
        else:
            return str(value)
