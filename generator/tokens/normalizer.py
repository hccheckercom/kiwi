"""Token normalizer — convert legacy dict format to DesignTokens schema.

Handles migration from current token_extractor.py output to new schema.
"""

from typing import Dict, Any

try:
    from .schema import DesignTokens
except ImportError:
    from schema import DesignTokens


class TokenNormalizer:
    """Normalize legacy token dict to DesignTokens schema."""

    def normalize(self, legacy_tokens: Dict[str, Any]) -> DesignTokens:
        """Convert legacy token dict to DesignTokens schema.

        Args:
            legacy_tokens: Dict from current token_extractor.py
                {
                    "colors": {"primary": "#3b82f6", ...},
                    "typography": {"h1": {"fontSize": "2.5rem", ...}, ...},
                    "spacing": {"4": "1rem", ...},
                    "borderRadius": {"lg": "0.5rem", ...}
                }

        Returns:
            Validated DesignTokens instance
        """
        normalized = {
            "colors": self._normalize_colors(legacy_tokens.get("colors", {})),
            "typography": self._normalize_typography(legacy_tokens.get("typography", {})),
            "spacing": self._normalize_spacing(legacy_tokens.get("spacing", {})),
            "borderRadius": self._normalize_border_radius(legacy_tokens.get("borderRadius", {})),
        }

        return DesignTokens(**normalized)

    def _normalize_colors(self, colors: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize color tokens.

        Handles:
        - Flat: {"primary": "#3b82f6"}
        - Nested: {"primary": {"500": "#3b82f6"}}
        """
        normalized = {}

        for key, value in colors.items():
            if isinstance(value, dict):
                # Nested color scale
                normalized[key] = self._normalize_colors(value)
            else:
                # Flat color value
                normalized[key] = {"value": value, "type": "color"}

        return normalized

    def _normalize_typography(self, typography: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize typography tokens.

        Handles:
        - Flat: {"h1": {"fontSize": "2.5rem", "lineHeight": "1.2"}}
        - Nested: {"heading": {"h1": {"fontSize": "2.5rem"}}}
        - String fontSize: {"h1": "2.5rem"} (legacy bug)
        """
        normalized = {}

        for key, value in typography.items():
            if isinstance(value, str):
                # Legacy bug: fontSize as string instead of dict
                normalized[key] = {"fontSize": value}
            elif isinstance(value, dict):
                # Check if it's a scale (has fontSize/fontFamily) or nested category
                if any(k in value for k in ["fontSize", "fontFamily", "lineHeight", "fontWeight"]):
                    # It's a scale
                    normalized[key] = value
                else:
                    # It's a nested category
                    normalized[key] = self._normalize_typography(value)
            else:
                normalized[key] = value

        return normalized

    def _normalize_spacing(self, spacing: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize spacing tokens.

        Handles:
        - Flat: {"4": "1rem"}
        - Nested: {"sm": {"4": "1rem"}}
        """
        normalized = {}

        for key, value in spacing.items():
            if isinstance(value, dict):
                # Nested spacing scale
                normalized[key] = self._normalize_spacing(value)
            else:
                # Flat spacing value
                normalized[key] = {"value": value, "type": "spacing"}

        return normalized

    def _normalize_border_radius(self, border_radius: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize borderRadius tokens.

        Handles:
        - Flat: {"lg": "0.5rem"}
        - Nested: {"button": {"lg": "0.5rem"}}
        """
        normalized = {}

        for key, value in border_radius.items():
            if isinstance(value, dict):
                # Nested border radius scale
                normalized[key] = self._normalize_border_radius(value)
            else:
                # Flat border radius value
                normalized[key] = {"value": value, "type": "borderRadius"}

        return normalized


def normalize_tokens(legacy_tokens: Dict[str, Any]) -> DesignTokens:
    """Convenience function to normalize tokens.

    Args:
        legacy_tokens: Dict from current token_extractor.py

    Returns:
        Validated DesignTokens instance
    """
    normalizer = TokenNormalizer()
    return normalizer.normalize(legacy_tokens)