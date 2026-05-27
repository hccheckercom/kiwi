"""Unit tests for token schema, validator, and normalizer."""

import pytest
from pydantic import ValidationError

from tokens.schema import (
    DesignTokens,
    ColorToken,
    DimensionToken,
    TypographyToken,
    FontFamilyToken,
)
from tokens.validator import TokenValidator, validate_design_tokens
from tokens.normalizer import TokenNormalizer, normalize_tokens


class TestColorToken:
    """Test ColorToken validation."""

    def test_valid_hex_colors(self):
        """Test valid hex color formats."""
        assert ColorToken(value="#3b82f6").value == "#3b82f6"
        assert ColorToken(value="#fff").value == "#fff"
        assert ColorToken(value="#3b82f6aa").value == "#3b82f6aa"

    def test_valid_rgb_colors(self):
        """Test valid RGB/RGBA formats."""
        assert ColorToken(value="rgb(59, 130, 246)").value == "rgb(59, 130, 246)"
        assert ColorToken(value="rgba(59, 130, 246, 0.5)").value == "rgba(59, 130, 246, 0.5)"

    def test_valid_hsl_colors(self):
        """Test valid HSL/HSLA formats."""
        assert ColorToken(value="hsl(217, 91%, 60%)").value == "hsl(217, 91%, 60%)"
        assert ColorToken(value="hsla(217, 91%, 60%, 0.5)").value == "hsla(217, 91%, 60%, 0.5)"

    def test_valid_named_colors(self):
        """Test valid named colors."""
        assert ColorToken(value="blue").value == "blue"
        assert ColorToken(value="transparent").value == "transparent"

    def test_invalid_hex_colors(self):
        """Test invalid hex color formats."""
        with pytest.raises(ValidationError):
            ColorToken(value="#12")  # Too short
        with pytest.raises(ValidationError):
            ColorToken(value="#12345")  # Invalid length
        with pytest.raises(ValidationError):
            ColorToken(value="12345")  # Missing #

    def test_empty_color(self):
        """Test empty color value."""
        with pytest.raises(ValidationError):
            ColorToken(value="")


class TestDimensionToken:
    """Test DimensionToken validation."""

    def test_valid_dimensions(self):
        """Test valid dimension formats."""
        assert DimensionToken(value="1rem").value == "1rem"
        assert DimensionToken(value="16px").value == "16px"
        assert DimensionToken(value="100%").value == "100%"
        assert DimensionToken(value="50vh").value == "50vh"
        assert DimensionToken(value="2.5em").value == "2.5em"

    def test_invalid_dimensions(self):
        """Test invalid dimension formats."""
        with pytest.raises(ValidationError):
            DimensionToken(value="16")  # Missing unit
        with pytest.raises(ValidationError):
            DimensionToken(value="rem")  # Missing number
        with pytest.raises(ValidationError):
            DimensionToken(value="16pt")  # Invalid unit


class TestTypographyToken:
    """Test TypographyToken validation."""

    def test_valid_typography_with_fontSize(self):
        """Test typography with fontSize."""
        token = TypographyToken(fontSize="2.5rem", lineHeight="1.2")
        assert token.fontSize == "2.5rem"
        assert token.lineHeight == "1.2"

    def test_valid_typography_with_fontFamily(self):
        """Test typography with fontFamily."""
        token = TypographyToken(fontFamily="Inter, sans-serif")
        assert token.fontFamily == "Inter, sans-serif"

    def test_typography_missing_required_fields(self):
        """Test typography without fontSize or fontFamily."""
        with pytest.raises(ValidationError):
            TypographyToken(lineHeight="1.5")  # Missing fontSize and fontFamily


class TestDesignTokens:
    """Test DesignTokens schema."""

    def test_empty_tokens(self):
        """Test creating empty token set."""
        tokens = DesignTokens()
        assert tokens.colors == {}
        assert tokens.typography == {}
        assert tokens.spacing == {}
        assert tokens.borderRadius == {}

    def test_flat_color_tokens(self):
        """Test flat color structure."""
        tokens = DesignTokens(
            colors={
                "primary": {"value": "#3b82f6", "type": "color"},
                "secondary": {"value": "#8b5cf6", "type": "color"},
            }
        )
        assert len(tokens.colors) == 2

    def test_nested_color_tokens(self):
        """Test nested color structure."""
        tokens = DesignTokens(
            colors={
                "primary": {
                    "500": {"value": "#3b82f6", "type": "color"},
                    "600": {"value": "#2563eb", "type": "color"},
                }
            }
        )
        assert "primary" in tokens.colors

    def test_get_flat_tokens(self):
        """Test flattening nested tokens."""
        tokens = DesignTokens(
            colors={
                "primary": {
                    "500": {"value": "#3b82f6"},
                    "600": {"value": "#2563eb"},
                }
            }
        )
        flat = tokens.get_flat_tokens("colors")
        assert flat["colors.primary.500"] == "#3b82f6"
        assert flat["colors.primary.600"] == "#2563eb"

    def test_get_token_count(self):
        """Test counting tokens per category."""
        tokens = DesignTokens(
            colors={
                "primary": {"value": "#3b82f6"},
                "secondary": {"value": "#8b5cf6"},
            },
            typography={
                "h1": {"fontSize": "2.5rem"},
                "h2": {"fontSize": "2rem"},
            }
        )
        counts = tokens.get_token_count()
        assert counts["colors"] == 2
        assert counts["typography"] == 2


class TestTokenNormalizer:
    """Test TokenNormalizer."""

    def test_normalize_flat_colors(self):
        """Test normalizing flat color dict."""
        legacy = {
            "colors": {
                "primary": "#3b82f6",
                "secondary": "#8b5cf6",
            }
        }
        normalizer = TokenNormalizer()
        tokens = normalizer.normalize(legacy)
        assert "primary" in tokens.colors
        # After Pydantic validation, it becomes ColorToken object
        primary = tokens.colors["primary"]
        if isinstance(primary, dict):
            assert primary["value"] == "#3b82f6"
        else:
            assert primary.value == "#3b82f6"

    def test_normalize_nested_colors(self):
        """Test normalizing nested color dict."""
        legacy = {
            "colors": {
                "primary": {
                    "500": "#3b82f6",
                    "600": "#2563eb",
                }
            }
        }
        normalizer = TokenNormalizer()
        tokens = normalizer.normalize(legacy)
        assert "primary" in tokens.colors
        assert tokens.colors["primary"]["500"]["value"] == "#3b82f6"

    def test_normalize_typography(self):
        """Test normalizing typography dict."""
        legacy = {
            "typography": {
                "h1": {
                    "fontSize": "2.5rem",
                    "lineHeight": "1.2",
                }
            }
        }
        normalizer = TokenNormalizer()
        tokens = normalizer.normalize(legacy)
        assert "h1" in tokens.typography
        # Typography stays as dict (not converted to TypographyToken by normalizer)
        h1 = tokens.typography["h1"]
        assert isinstance(h1, dict)
        # fontSize is wrapped in token object by normalizer
        assert h1["fontSize"]["value"] == "2.5rem"

    def test_normalize_string_fontSize_bug(self):
        """Test normalizing legacy bug where fontSize is string."""
        legacy = {
            "typography": {
                "h1": "2.5rem"  # Bug: should be dict
            }
        }
        normalizer = TokenNormalizer()
        tokens = normalizer.normalize(legacy)
        assert "h1" in tokens.typography
        # After normalization + Pydantic validation, becomes TypographyToken
        h1 = tokens.typography["h1"]
        # Check if it's a TypographyToken object or dict
        if hasattr(h1, 'fontSize'):
            # TypographyToken object - fontSize is DimensionToken
            assert h1.fontSize.value == "2.5rem"
        else:
            # Dict format
            assert h1["fontSize"] == "2.5rem"


class TestTokenValidator:
    """Test TokenValidator."""

    def test_validate_valid_tokens(self):
        """Test validating valid token set."""
        tokens = {
            "colors": {
                "primary": "#3b82f6",
                "secondary": "#8b5cf6",
                "success": "#10b981",
                "error": "#ef4444",
                "warning": "#f59e0b",
                "info": "#3b82f6",
                "neutral-100": "#f5f5f5",
                "neutral-200": "#e5e5e5",
                "neutral-300": "#d4d4d4",
                "neutral-400": "#a3a3a3",
            },
            "typography": {
                "h1": {"fontSize": "2.5rem"},
                "h2": {"fontSize": "2rem"},
                "h3": {"fontSize": "1.75rem"},
                "h4": {"fontSize": "1.5rem"},
                "h5": {"fontSize": "1.25rem"},
                "body": {"fontSize": "1rem"},
            }
        }
        report = validate_design_tokens(tokens)
        assert report["valid"] is True
        assert len(report["errors"]) == 0

    def test_validate_missing_colors(self):
        """Test validation with no colors."""
        tokens = {
            "typography": {
                "h1": {"fontSize": "2.5rem"},
            }
        }
        report = validate_design_tokens(tokens)
        assert report["valid"] is False
        assert any("No colors defined" in err for err in report["errors"])

    def test_validate_few_colors_warning(self):
        """Test warning for few colors."""
        tokens = {
            "colors": {
                "primary": "#3b82f6",
                "secondary": "#8b5cf6",
            },
            "typography": {
                "h1": {"fontSize": "2.5rem"},
            }
        }
        report = validate_design_tokens(tokens)
        assert len(report["warnings"]) > 0
        assert any("colors found" in warn for warn in report["warnings"])

    def test_validate_missing_semantic_colors(self):
        """Test warning for missing semantic colors."""
        tokens = {
            "colors": {
                "primary": "#3b82f6",
                "secondary": "#8b5cf6",
                "neutral-100": "#f5f5f5",
                "neutral-200": "#e5e5e5",
                "neutral-300": "#d4d4d4",
                "neutral-400": "#a3a3a3",
                "neutral-500": "#737373",
                "neutral-600": "#525252",
                "neutral-700": "#404040",
                "neutral-800": "#262626",
            },
            "typography": {
                "h1": {"fontSize": "2.5rem"},
            }
        }
        report = validate_design_tokens(tokens)
        assert any("semantic colors" in warn for warn in report["warnings"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])