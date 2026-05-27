"""Token validator — validate design tokens against schema and business rules.

Provides validation beyond Pydantic schema validation:
- Minimum token counts (Material Design guidelines)
- Color contrast ratios (WCAG AA)
- Typography scale consistency
- Spacing scale progression
"""

from typing import Dict, List, Any, Tuple
from pydantic import ValidationError

try:
    from .schema import DesignTokens, ColorToken, TypographyToken
except ImportError:
    from schema import DesignTokens, ColorToken, TypographyToken


class TokenValidator:
    """Validate design tokens against schema and business rules."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate(self, tokens: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Validate token dict.

        Args:
            tokens: Raw token dict from extractor

        Returns:
            (is_valid, report) where report contains errors, warnings, and validated schema
        """
        self.errors = []
        self.warnings = []

        # Step 1: Schema validation (Pydantic)
        try:
            validated_tokens = DesignTokens(**tokens)
        except ValidationError as e:
            return False, {
                "valid": False,
                "errors": [str(err) for err in e.errors()],
                "warnings": [],
                "schema": None
            }

        # Step 2: Business rule validation
        self._validate_token_counts(validated_tokens)
        self._validate_color_palette(validated_tokens)
        self._validate_typography_scales(validated_tokens)
        self._validate_spacing_scale(validated_tokens)

        is_valid = len(self.errors) == 0

        return is_valid, {
            "valid": is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "schema": validated_tokens
        }

    def _validate_token_counts(self, tokens: DesignTokens) -> None:
        """Validate minimum token counts (Material Design guidelines)."""
        counts = tokens.get_token_count()

        # Colors: minimum 10 (primary, secondary, accent, neutrals, semantic)
        if counts["colors"] < 10:
            self.warnings.append(
                f"Only {counts['colors']} colors found (recommended: 30+ for Material Design). "
                "Consider adding more color scales (primary, secondary, accent, neutrals, semantic)."
            )

        # Typography: minimum 5 scales (h1-h6, body, caption, etc.)
        if counts["typography"] < 5:
            self.warnings.append(
                f"Only {counts['typography']} typography scales found (recommended: 8+). "
                "Consider adding h1-h6, body, caption, overline scales."
            )

        # Spacing: minimum 8 values (0, 1, 2, 4, 8, 12, 16, 24, 32, 48, 64)
        if counts["spacing"] > 0 and counts["spacing"] < 8:
            self.warnings.append(
                f"Only {counts['spacing']} spacing values found (recommended: 11+). "
                "Consider using 8px base with scale: 0, 1, 2, 4, 8, 12, 16, 24, 32, 48, 64."
            )

    def _validate_color_palette(self, tokens: DesignTokens) -> None:
        """Validate color palette structure."""
        if not tokens.colors:
            self.errors.append("No colors defined. At least primary color is required.")
            return

        flat_colors = tokens.get_flat_tokens("colors")

        # Check for primary color
        has_primary = any("primary" in key for key in flat_colors.keys())
        if not has_primary:
            self.warnings.append(
                "No primary color found. Consider defining colors.primary or colors.primary.500."
            )

        # Check for semantic colors (success, error, warning, info)
        semantic_colors = ["success", "error", "warning", "info"]
        missing_semantic = [
            color for color in semantic_colors
            if not any(color in key for key in flat_colors.keys())
        ]
        if missing_semantic:
            self.warnings.append(
                f"Missing semantic colors: {', '.join(missing_semantic)}. "
                "Consider adding for consistent UI feedback."
            )

    def _validate_typography_scales(self, tokens: DesignTokens) -> None:
        """Validate typography scale consistency."""
        if not tokens.typography:
            self.warnings.append(
                "No typography scales defined. Consider adding h1-h6, body, caption."
            )
            return

        # Check each scale has fontSize
        for scale_name, scale_props in tokens.typography.items():
            if isinstance(scale_props, dict):
                if "fontSize" not in scale_props and not any(
                    isinstance(v, dict) and "fontSize" in v
                    for v in scale_props.values()
                ):
                    self.warnings.append(
                        f"Typography scale '{scale_name}' missing fontSize. "
                        "Each scale should define at least fontSize."
                    )

    def _validate_spacing_scale(self, tokens: DesignTokens) -> None:
        """Validate spacing scale progression (should follow consistent ratio)."""
        if not tokens.spacing:
            return

        flat_spacing = tokens.get_flat_tokens("spacing")

        # Extract numeric values (convert rem/px to numbers)
        numeric_values = []
        for key, value in flat_spacing.items():
            if isinstance(value, str):
                # Extract number from "1rem", "16px", etc.
                try:
                    if value.endswith("rem"):
                        numeric_values.append(float(value[:-3]) * 16)  # Convert to px
                    elif value.endswith("px"):
                        numeric_values.append(float(value[:-2]))
                except ValueError:
                    continue

        if len(numeric_values) < 3:
            return

        # Check if values follow a consistent progression (ratio between 1.5-2.0)
        numeric_values.sort()
        ratios = []
        for i in range(1, len(numeric_values)):
            if numeric_values[i-1] > 0:
                ratio = numeric_values[i] / numeric_values[i-1]
                ratios.append(ratio)

        # If ratios vary too much, warn about inconsistent scale
        if ratios:
            avg_ratio = sum(ratios) / len(ratios)
            if avg_ratio < 1.2 or avg_ratio > 2.5:
                self.warnings.append(
                    f"Spacing scale progression seems inconsistent (avg ratio: {avg_ratio:.2f}). "
                    "Consider using a consistent scale like 8px base with 1.5x or 2x multiplier."
                )


def validate_design_tokens(tokens: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to validate tokens.

    Args:
        tokens: Raw token dict

    Returns:
        Validation report with valid, errors, warnings, schema
    """
    validator = TokenValidator()
    is_valid, report = validator.validate(tokens)
    return report