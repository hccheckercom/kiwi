"""Token transformer — modular transform pipeline for design tokens.

Inspired by style-dictionary's transform system but implemented in Python.
Each transform is a pure function that takes DesignTokens and returns modified DesignTokens.
"""

from typing import Callable, List, Dict, Any
import re

try:
    from .schema import DesignTokens, ColorToken, DimensionToken
except ImportError:
    from schema import DesignTokens, ColorToken, DimensionToken


TransformFunction = Callable[[DesignTokens], DesignTokens]


class TokenTransformer:
    """Transform pipeline for design tokens.

    Usage:
        transformer = TokenTransformer()
        transformer.register(px_to_rem)
        transformer.register(hex_to_rgb)
        transformed = transformer.apply(tokens)
    """

    def __init__(self):
        self.transforms: List[TransformFunction] = []

    def register(self, transform: TransformFunction) -> None:
        """Register a transform function."""
        self.transforms.append(transform)

    def apply(self, tokens: DesignTokens) -> DesignTokens:
        """Apply all registered transforms in order."""
        result = tokens
        for transform in self.transforms:
            result = transform(result)
        return result


# Core Transforms

def px_to_rem(tokens: DesignTokens, base_px: float = 16.0) -> DesignTokens:
    """Convert px values to rem (spacing, fontSize, borderRadius).

    Args:
        tokens: Input tokens
        base_px: Base font size in px (default: 16)

    Returns:
        Tokens with px values converted to rem
    """
    def convert_value(value: Any) -> Any:
        """Convert single value from px to rem."""
        if isinstance(value, str) and value.endswith('px'):
            try:
                px_value = float(value[:-2])
                rem_value = px_value / base_px
                return f"{rem_value}rem"
            except ValueError:
                return value
        return value

    def convert_dict(d: Dict) -> Dict:
        """Recursively convert dict values."""
        result = {}
        for key, val in d.items():
            if isinstance(val, dict):
                if "value" in val:
                    result[key] = {**val, "value": convert_value(val["value"])}
                else:
                    result[key] = convert_dict(val)
            elif hasattr(val, 'value'):
                val.value = convert_value(val.value)
                result[key] = val
            else:
                result[key] = convert_value(val)
        return result

    tokens_dict = tokens.model_dump()
    tokens_dict["spacing"] = convert_dict(tokens_dict.get("spacing", {}))
    tokens_dict["borderRadius"] = convert_dict(tokens_dict.get("borderRadius", {}))

    # Convert fontSize in typography
    typography = tokens_dict.get("typography", {})
    for scale_name, scale_props in typography.items():
        if isinstance(scale_props, dict) and "fontSize" in scale_props:
            if isinstance(scale_props["fontSize"], dict) and "value" in scale_props["fontSize"]:
                scale_props["fontSize"]["value"] = convert_value(scale_props["fontSize"]["value"])
            elif isinstance(scale_props["fontSize"], str):
                scale_props["fontSize"] = convert_value(scale_props["fontSize"])

    return DesignTokens(**tokens_dict)


def hex_to_rgb(tokens: DesignTokens) -> DesignTokens:
    """Convert hex colors to rgb format.

    Args:
        tokens: Input tokens

    Returns:
        Tokens with hex colors converted to rgb(r, g, b)
    """
    def hex_to_rgb_value(hex_color: str) -> str:
        """Convert single hex color to rgb."""
        if not hex_color.startswith('#'):
            return hex_color

        hex_color = hex_color.lstrip('#')

        # Handle short hex (#RGB)
        if len(hex_color) == 3:
            hex_color = ''.join([c*2 for c in hex_color])

        # Handle hex with alpha (#RRGGBBAA)
        if len(hex_color) == 8:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            a = int(hex_color[6:8], 16) / 255
            return f"rgba({r}, {g}, {b}, {a:.2f})"

        # Standard hex (#RRGGBB)
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return f"rgb({r}, {g}, {b})"

        return f"#{hex_color}"

    def convert_dict(d: Dict) -> Dict:
        """Recursively convert dict values."""
        result = {}
        for key, val in d.items():
            if isinstance(val, dict):
                if "value" in val and isinstance(val["value"], str):
                    result[key] = {**val, "value": hex_to_rgb_value(val["value"])}
                else:
                    result[key] = convert_dict(val)
            elif hasattr(val, 'value') and isinstance(val.value, str):
                val.value = hex_to_rgb_value(val.value)
                result[key] = val
            else:
                result[key] = val
        return result

    tokens_dict = tokens.model_dump()
    tokens_dict["colors"] = convert_dict(tokens_dict.get("colors", {}))

    return DesignTokens(**tokens_dict)


def flatten_nested(tokens: DesignTokens, separator: str = "-") -> DesignTokens:
    """Flatten nested token structure to single level.

    Args:
        tokens: Input tokens with nested structure
        separator: Separator for flattened keys (default: "-")

    Returns:
        Tokens with flat structure (colors.primary.500 → colors.primary-500)
    """
    def flatten_dict(d: Dict, prefix: str = "") -> Dict:
        """Recursively flatten nested dict."""
        result = {}
        for key, val in d.items():
            full_key = f"{prefix}{separator}{key}" if prefix else key

            if isinstance(val, dict):
                if "value" in val or "fontSize" in val or "fontFamily" in val:
                    result[full_key] = val
                else:
                    result.update(flatten_dict(val, full_key))
            else:
                result[full_key] = val

        return result

    tokens_dict = tokens.model_dump()

    for category in ["colors", "spacing", "borderRadius"]:
        if category in tokens_dict:
            tokens_dict[category] = flatten_dict(tokens_dict[category])

    return DesignTokens(**tokens_dict)


def add_css_var_prefix(tokens: DesignTokens, prefix: str = "--") -> DesignTokens:
    """Add CSS variable prefix to token keys.

    Args:
        tokens: Input tokens
        prefix: Prefix to add (default: "--")

    Returns:
        Tokens with prefixed keys (primary → --primary)
    """
    def prefix_dict(d: Dict) -> Dict:
        """Add prefix to all keys."""
        result = {}
        for key, val in d.items():
            new_key = f"{prefix}{key}" if not key.startswith(prefix) else key

            if isinstance(val, dict) and not ("value" in val or "fontSize" in val):
                result[new_key] = prefix_dict(val)
            else:
                result[new_key] = val

        return result

    tokens_dict = tokens.model_dump()

    for category in ["colors", "spacing", "borderRadius"]:
        if category in tokens_dict:
            tokens_dict[category] = prefix_dict(tokens_dict[category])

    return DesignTokens(**tokens_dict)


def sort_by_category(tokens: DesignTokens) -> DesignTokens:
    """Sort tokens alphabetically within each category.

    Args:
        tokens: Input tokens

    Returns:
        Tokens with sorted keys
    """
    def sort_dict(d: Dict) -> Dict:
        """Recursively sort dict keys."""
        result = {}
        for key in sorted(d.keys()):
            val = d[key]
            if isinstance(val, dict) and not ("value" in val or "fontSize" in val):
                result[key] = sort_dict(val)
            else:
                result[key] = val
        return result

    tokens_dict = tokens.model_dump()

    for category in ["colors", "typography", "spacing", "borderRadius"]:
        if category in tokens_dict:
            tokens_dict[category] = sort_dict(tokens_dict[category])

    return DesignTokens(**tokens_dict)


# Convenience function

def create_default_pipeline() -> TokenTransformer:
    """Create transformer with default transforms.

    Returns:
        TokenTransformer with px_to_rem and sort_by_category
    """
    transformer = TokenTransformer()
    transformer.register(px_to_rem)
    transformer.register(sort_by_category)
    return transformer
