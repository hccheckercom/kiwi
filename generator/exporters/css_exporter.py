"""CSS exporter — export design tokens to CSS variables.

Output format:
:root {
  --color-primary: #3b82f6;
  --font-heading-h1-size: 2.5rem;
  --spacing-4: 1rem;
}
"""

from typing import Dict, Any

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from exporters.base import BaseExporter
from tokens.schema import DesignTokens


class CSSExporter(BaseExporter):
    """Export tokens to CSS variables."""

    def __init__(self, options: Dict[str, Any] = None):
        """Initialize CSS exporter.

        Options:
            indent: Indent size (default: 2)
            selector: Root selector (default: ":root")
            prefix: Variable prefix (default: "--")
        """
        super().__init__(options)
        self.indent = self.options.get('indent', 2)
        self.selector = self.options.get('selector', ':root')
        self.prefix = self.options.get('prefix', '--')

    def export(self, tokens: DesignTokens) -> str:
        """Export tokens to CSS variables.

        Args:
            tokens: Validated DesignTokens schema

        Returns:
            CSS variable declarations
        """
        lines = [f"{self.selector} {{"]

        # Export colors
        if tokens.colors:
            lines.append(self._format_comment("  /* Colors */"))
            lines.extend(self._export_category(tokens.colors, "color"))

        # Export typography
        if tokens.typography:
            lines.append("")
            lines.append(self._format_comment("  /* Typography */"))
            lines.extend(self._export_typography(tokens.typography))

        # Export spacing
        if tokens.spacing:
            lines.append("")
            lines.append(self._format_comment("  /* Spacing */"))
            lines.extend(self._export_category(tokens.spacing, "spacing"))

        # Export border radius
        if tokens.borderRadius:
            lines.append("")
            lines.append(self._format_comment("  /* Border Radius */"))
            lines.extend(self._export_category(tokens.borderRadius, "radius"))

        lines.append("}")

        return "\n".join(lines)

    def _export_category(self, category: Dict, category_name: str, prefix: str = "") -> list:
        """Export single category recursively.

        Args:
            category: Category dict
            category_name: Category name for variable naming
            prefix: Current prefix for nested keys

        Returns:
            List of CSS variable lines
        """
        lines = []
        indent = " " * self.indent

        for key, value in category.items():
            full_key = f"{prefix}-{key}" if prefix else key
            var_name = f"{self.prefix}{category_name}-{full_key}"

            if isinstance(value, dict):
                # Check if it's a token leaf node
                if "value" in value:
                    # Token with value
                    css_value = value["value"]
                    comment = value.get("comment", "")

                    if comment:
                        lines.append(f"{indent}{self._format_comment(comment, '/*')} */")
                    lines.append(f"{indent}{var_name}: {css_value};")
                elif hasattr(value, 'value'):
                    # Pydantic model
                    css_value = value.value
                    comment = getattr(value, 'comment', None)

                    if comment:
                        lines.append(f"{indent}{self._format_comment(comment, '/*')} */")
                    lines.append(f"{indent}{var_name}: {css_value};")
                else:
                    # Nested category
                    lines.extend(self._export_category(value, category_name, full_key))
            elif hasattr(value, 'value'):
                # Pydantic model
                css_value = value.value
                comment = getattr(value, 'comment', None)

                if comment:
                    lines.append(f"{indent}{self._format_comment(comment, '/*')} */")
                lines.append(f"{indent}{var_name}: {css_value};")
            else:
                # Direct value
                lines.append(f"{indent}{var_name}: {value};")

        return lines

    def _export_typography(self, typography: Dict) -> list:
        """Export typography tokens.

        Args:
            typography: Typography dict

        Returns:
            List of CSS variable lines
        """
        lines = []
        indent = " " * self.indent

        for scale_name, scale_props in typography.items():
            if isinstance(scale_props, dict):
                # Check if it's a TypographyToken or dict
                if hasattr(scale_props, 'fontSize'):
                    # Pydantic TypographyToken
                    if scale_props.fontSize:
                        font_size = scale_props.fontSize.value if hasattr(scale_props.fontSize, 'value') else scale_props.fontSize
                        lines.append(f"{indent}{self.prefix}font-{scale_name}-size: {font_size};")
                    if scale_props.lineHeight:
                        lines.append(f"{indent}{self.prefix}font-{scale_name}-line-height: {scale_props.lineHeight};")
                    if scale_props.fontWeight:
                        lines.append(f"{indent}{self.prefix}font-{scale_name}-weight: {scale_props.fontWeight};")
                    if scale_props.fontFamily:
                        font_family = scale_props.fontFamily if isinstance(scale_props.fontFamily, str) else ', '.join(scale_props.fontFamily)
                        lines.append(f"{indent}{self.prefix}font-{scale_name}-family: {font_family};")
                else:
                    # Dict format
                    for prop, value in scale_props.items():
                        if isinstance(value, dict) and "value" in value:
                            css_value = value["value"]
                        elif hasattr(value, 'value'):
                            css_value = value.value
                        else:
                            css_value = value

                        lines.append(f"{indent}{self.prefix}font-{scale_name}-{prop}: {css_value};")

        return lines

    def _format_comment(self, comment: str, prefix: str = "/*") -> str:
        """Format CSS comment.

        Args:
            comment: Comment text
            prefix: Comment prefix

        Returns:
            Formatted comment
        """
        if not comment:
            return ""
        if prefix == "/*":
            return f"/* {comment}"
        return f"{prefix} {comment}"