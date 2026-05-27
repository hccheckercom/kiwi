"""Tailwind exporter — export design tokens to tailwind.config.js.

Output format:
module.exports = {
  theme: {
    extend: {
      colors: {
        primary: '#3b82f6',
        secondary: '#8b5cf6'
      },
      fontSize: {
        'heading-h1': '2.5rem',
        'heading-h2': '2rem'
      },
      spacing: {
        '4': '1rem',
        '8': '2rem'
      },
      borderRadius: {
        'lg': '0.5rem'
      }
    }
  }
}
"""

from typing import Dict, Any
import json

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from exporters.base import BaseExporter
from tokens.schema import DesignTokens


class TailwindExporter(BaseExporter):
    """Export tokens to tailwind.config.js."""

    def __init__(self, options: Dict[str, Any] = None):
        """Initialize Tailwind exporter.

        Options:
            indent: Indent size (default: 2)
            format: 'js' or 'json' (default: 'js')
        """
        super().__init__(options)
        self.indent = self.options.get('indent', 2)
        self.format = self.options.get('format', 'js')

    def export(self, tokens: DesignTokens) -> str:
        """Export tokens to tailwind.config.js.

        Args:
            tokens: Validated DesignTokens schema

        Returns:
            Tailwind config file content
        """
        config = {
            'theme': {
                'extend': {}
            }
        }

        # Export colors
        if tokens.colors:
            config['theme']['extend']['colors'] = self._export_category(tokens.colors)

        # Export typography (fontSize + fontFamily)
        if tokens.typography:
            font_config = self._export_typography(tokens.typography)
            if 'fontSize' in font_config:
                config['theme']['extend']['fontSize'] = font_config['fontSize']
            if 'fontFamily' in font_config:
                config['theme']['extend']['fontFamily'] = font_config['fontFamily']

        # Export spacing
        if tokens.spacing:
            config['theme']['extend']['spacing'] = self._export_category(tokens.spacing)

        # Export border radius
        if tokens.borderRadius:
            config['theme']['extend']['borderRadius'] = self._export_category(tokens.borderRadius)

        if self.format == 'json':
            return json.dumps(config, indent=self.indent)
        else:
            return self._format_as_js(config)

    def _export_category(self, category: Dict) -> Dict:
        """Export single category recursively.

        Args:
            category: Category dict

        Returns:
            Tailwind-compatible dict
        """
        result = {}

        for key, value in category.items():
            if isinstance(value, dict):
                # Check if it's a token leaf node
                if "value" in value:
                    result[key] = value["value"]
                elif hasattr(value, 'value'):
                    result[key] = value.value
                else:
                    # Nested category
                    result[key] = self._export_category(value)
            elif hasattr(value, 'value'):
                result[key] = value.value
            else:
                result[key] = value

        return result

    def _export_typography(self, typography: Dict) -> Dict:
        """Export typography tokens.

        Args:
            typography: Typography dict

        Returns:
            Dict with fontSize and fontFamily keys
        """
        font_config = {
            'fontSize': {},
            'fontFamily': {}
        }

        for scale_name, scale_props in typography.items():
            if isinstance(scale_props, dict):
                if hasattr(scale_props, 'fontSize'):
                    # Pydantic TypographyToken
                    if scale_props.fontSize:
                        font_size = scale_props.fontSize.value if hasattr(scale_props.fontSize, 'value') else scale_props.fontSize
                        line_height = scale_props.lineHeight if scale_props.lineHeight else None

                        if line_height:
                            # Tailwind fontSize with lineHeight: ['2.5rem', {lineHeight: '1.2'}]
                            font_config['fontSize'][scale_name] = [font_size, {'lineHeight': str(line_height)}]
                        else:
                            font_config['fontSize'][scale_name] = font_size

                    if scale_props.fontFamily:
                        font_family = scale_props.fontFamily
                        if isinstance(font_family, str):
                            font_config['fontFamily'][scale_name] = [font_family]
                        else:
                            font_config['fontFamily'][scale_name] = font_family
                else:
                    # Dict format
                    if 'fontSize' in scale_props:
                        font_size_value = scale_props['fontSize']
                        if isinstance(font_size_value, dict) and 'value' in font_size_value:
                            font_size = font_size_value['value']
                        elif hasattr(font_size_value, 'value'):
                            font_size = font_size_value.value
                        else:
                            font_size = font_size_value

                        line_height = scale_props.get('lineHeight')
                        if line_height:
                            font_config['fontSize'][scale_name] = [font_size, {'lineHeight': str(line_height)}]
                        else:
                            font_config['fontSize'][scale_name] = font_size

                    if 'fontFamily' in scale_props:
                        font_family = scale_props['fontFamily']
                        if isinstance(font_family, str):
                            font_config['fontFamily'][scale_name] = [font_family]
                        else:
                            font_config['fontFamily'][scale_name] = font_family

        # Remove empty categories
        if not font_config['fontSize']:
            del font_config['fontSize']
        if not font_config['fontFamily']:
            del font_config['fontFamily']

        return font_config

    def _format_as_js(self, config: Dict) -> str:
        """Format config as JavaScript module.exports.

        Args:
            config: Config dict

        Returns:
            JavaScript module.exports string
        """
        lines = ["module.exports = {"]
        lines.extend(self._format_object(config, level=1))
        lines.append("}")

        return "\n".join(lines)

    def _format_object(self, obj: Any, level: int = 0) -> list:
        """Format object as JavaScript recursively.

        Args:
            obj: Object to format
            level: Nesting level

        Returns:
            List of formatted lines
        """
        lines = []
        indent = " " * (self.indent * level)

        if isinstance(obj, dict):
            for key, value in obj.items():
                # Format key
                if key.isidentifier() and not key.isdigit():
                    js_key = key
                else:
                    js_key = f"'{key}'"

                if isinstance(value, dict):
                    lines.append(f"{indent}{js_key}: {{")
                    lines.extend(self._format_object(value, level + 1))
                    lines.append(f"{indent}}},")
                elif isinstance(value, list):
                    lines.append(f"{indent}{js_key}: {self._format_array(value)},")
                else:
                    lines.append(f"{indent}{js_key}: {self._format_value(value)},")

        return lines

    def _format_array(self, arr: list) -> str:
        """Format array as JavaScript.

        Args:
            arr: Array to format

        Returns:
            Formatted JavaScript array
        """
        formatted_items = []
        for item in arr:
            if isinstance(item, dict):
                # Inline object
                items = [f"{k}: {self._format_value(v)}" for k, v in item.items()]
                formatted_items.append("{" + ", ".join(items) + "}")
            else:
                formatted_items.append(self._format_value(item))

        return "[" + ", ".join(formatted_items) + "]"

    def _format_value(self, value: Any) -> str:
        """Format value as JavaScript.

        Args:
            value: Value to format

        Returns:
            Formatted JavaScript value
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