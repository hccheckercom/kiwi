"""Token schema definitions using Pydantic for validation and type safety.

Inspired by style-dictionary architecture but implemented in Python.
Supports nested token structures following W3C Design Tokens Community Group format.
"""

from typing import Any, Dict, Optional, Union, List
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class TokenValue(BaseModel):
    """Base token value with metadata.

    All tokens have a value and optional metadata like comments, type hints.
    """
    model_config = ConfigDict(extra="allow")

    value: Any
    comment: Optional[str] = None
    type: Optional[str] = None  # color, dimension, fontFamily, fontWeight, etc.


class ColorToken(TokenValue):
    """Color token with validation."""
    value: str
    type: str = "color"

    @field_validator("value")
    @classmethod
    def validate_color(cls, v):
        """Validate color format (hex, rgb, rgba, hsl, hsla, named)."""
        if not v:
            raise ValueError("Color value cannot be empty")

        # Hex color
        if v.startswith("#"):
            if len(v) not in [4, 7, 9]:  # #RGB, #RRGGBB, #RRGGBBAA
                raise ValueError(f"Invalid hex color: {v}")
            return v

        # RGB/RGBA
        if v.startswith("rgb"):
            return v

        # HSL/HSLA
        if v.startswith("hsl"):
            return v

        # Named colors (basic validation - just check it's a word)
        if v.isalpha():
            return v

        raise ValueError(f"Invalid color format: {v}")


class DimensionToken(TokenValue):
    """Dimension token (spacing, fontSize, borderRadius, etc.)."""
    value: str
    type: str = "dimension"

    @field_validator("value")
    @classmethod
    def validate_dimension(cls, v):
        """Validate dimension format (px, rem, em, %, vh, vw, etc.)."""
        if not v:
            raise ValueError("Dimension value cannot be empty")

        # Check if it ends with a valid unit
        valid_units = ["px", "rem", "em", "%", "vh", "vw", "vmin", "vmax", "ch", "ex"]
        if not any(v.endswith(unit) for unit in valid_units):
            raise ValueError(f"Invalid dimension unit: {v}")

        # Check if the numeric part is valid
        numeric_part = v.rstrip("".join(valid_units))
        try:
            float(numeric_part)
        except ValueError:
            raise ValueError(f"Invalid dimension value: {v}")

        return v


class FontFamilyToken(TokenValue):
    """Font family token."""
    value: Union[str, List[str]]
    type: str = "fontFamily"

    @field_validator("value")
    @classmethod
    def validate_font_family(cls, v):
        """Ensure font family is string or list of strings."""
        if isinstance(v, list):
            if not all(isinstance(f, str) for f in v):
                raise ValueError("Font family list must contain only strings")
        elif not isinstance(v, str):
            raise ValueError("Font family must be string or list of strings")
        return v


class TypographyToken(BaseModel):
    """Typography scale token (combines fontSize, lineHeight, fontWeight, etc.)."""
    model_config = ConfigDict(extra="allow")

    fontSize: Optional[Union[str, DimensionToken]] = None
    lineHeight: Optional[Union[str, float]] = None
    fontWeight: Optional[Union[str, int]] = None
    fontFamily: Optional[Union[str, List[str], FontFamilyToken]] = None
    letterSpacing: Optional[Union[str, DimensionToken]] = None
    textTransform: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def ensure_at_least_one_property(cls, values):
        """Ensure at least fontSize or fontFamily is present."""
        if not any([values.get("fontSize"), values.get("fontFamily")]):
            raise ValueError("Typography token must have at least fontSize or fontFamily")
        return values


class SpacingToken(DimensionToken):
    """Spacing token (margin, padding, gap)."""
    type: str = "spacing"


class BorderRadiusToken(DimensionToken):
    """Border radius token."""
    type: str = "borderRadius"


class DesignTokens(BaseModel):
    """Root design tokens schema.

    Supports nested token structures:
    - colors.primary.500
    - typography.heading.h1
    - spacing.4
    - borderRadius.lg
    """
    model_config = ConfigDict(extra="allow")

    colors: Dict[str, Union[ColorToken, Dict[str, Any]]] = Field(default_factory=dict)
    typography: Dict[str, Union[TypographyToken, Dict[str, Any]]] = Field(default_factory=dict)
    spacing: Dict[str, Union[SpacingToken, Dict[str, Any]]] = Field(default_factory=dict)
    borderRadius: Dict[str, Union[BorderRadiusToken, Dict[str, Any]]] = Field(default_factory=dict)

    @field_validator("colors", "typography", "spacing", "borderRadius", mode="before")
    @classmethod
    def normalize_nested_tokens(cls, v):
        """Normalize nested token structures.

        Converts:
        - {"primary": "#3b82f6"} → {"primary": ColorToken(value="#3b82f6")}
        - {"primary": {"500": "#3b82f6"}} → {"primary": {"500": ColorToken(value="#3b82f6")}}
        """
        if not isinstance(v, dict):
            return v

        def normalize_value(val):
            """Recursively normalize token values."""
            if isinstance(val, dict):
                # Check if it's a token object (has 'value' key)
                if "value" in val:
                    return val  # Already a token object
                # Otherwise, it's a nested category
                return {k: normalize_value(v) for k, v in val.items()}
            else:
                # Primitive value - wrap in token object
                return {"value": val}

        return {k: normalize_value(val) for k, val in v.items()}

    def get_flat_tokens(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Get flattened token dict with dot notation keys.

        Args:
            category: Optional category filter (colors, typography, etc.)

        Returns:
            Flat dict like {"colors.primary.500": "#3b82f6"}
        """
        def flatten(d: Dict, prefix: str = "") -> Dict[str, Any]:
            """Recursively flatten nested dict."""
            result = {}
            for key, value in d.items():
                full_key = f"{prefix}.{key}" if prefix else key

                if isinstance(value, TokenValue):
                    result[full_key] = value.value
                elif isinstance(value, dict):
                    if "value" in value:
                        result[full_key] = value["value"]
                    else:
                        result.update(flatten(value, full_key))
                else:
                    result[full_key] = value

            return result

        if category:
            category_data = getattr(self, category, {})
            return flatten(category_data, category)

        # Flatten all categories
        result = {}
        for cat in ["colors", "typography", "spacing", "borderRadius"]:
            category_data = getattr(self, cat, {})
            if category_data:
                result.update(flatten(category_data, cat))

        return result

    def get_token_count(self) -> Dict[str, int]:
        """Get count of tokens per category."""
        def count_tokens(d: Dict) -> int:
            """Recursively count leaf tokens."""
            count = 0
            for value in d.values():
                if isinstance(value, TokenValue):
                    count += 1
                elif isinstance(value, TypographyToken):
                    count += 1
                elif isinstance(value, dict):
                    if "value" in value or "fontSize" in value or "fontFamily" in value:
                        count += 1
                    else:
                        count += count_tokens(value)
            return count

        return {
            "colors": count_tokens(self.colors),
            "typography": count_tokens(self.typography),
            "spacing": count_tokens(self.spacing),
            "borderRadius": count_tokens(self.borderRadius),
        }