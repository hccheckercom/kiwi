"""Unit tests for token transformer and merger."""

import pytest

from tokens.schema import DesignTokens
from tokens.transformer import (
    TokenTransformer,
    px_to_rem,
    hex_to_rgb,
    flatten_nested,
    add_css_var_prefix,
    sort_by_category,
    create_default_pipeline,
)
from tokens.merger import TokenMerger, merge_tokens


class TestPxToRem:
    """Test px_to_rem transform."""

    def test_convert_spacing_px_to_rem(self):
        """Test converting spacing values from px to rem."""
        tokens = DesignTokens(
            spacing={
                "4": {"value": "16px"},
                "8": {"value": "32px"},
            }
        )
        result = px_to_rem(tokens)
        # After Pydantic validation, becomes SpacingToken object
        assert result.spacing["4"].value == "1.0rem"
        assert result.spacing["8"].value == "2.0rem"

    def test_convert_fontSize_px_to_rem(self):
        """Test converting fontSize from px to rem."""
        tokens = DesignTokens(
            typography={
                "h1": {"fontSize": "40px"},
            }
        )
        result = px_to_rem(tokens)
        # Typography becomes TypographyToken, fontSize becomes DimensionToken
        h1 = result.typography["h1"]
        if hasattr(h1, 'fontSize'):
            assert h1.fontSize.value == "2.5rem"
        else:
            assert h1["fontSize"]["value"] == "2.5rem"

    def test_preserve_non_px_values(self):
        """Test that non-px values are preserved."""
        tokens = DesignTokens(
            spacing={
                "4": {"value": "1rem"},
                "8": {"value": "100%"},
            }
        )
        result = px_to_rem(tokens)
        assert result.spacing["4"].value == "1rem"
        assert result.spacing["8"].value == "100%"

    def test_custom_base_px(self):
        """Test custom base px value."""
        tokens = DesignTokens(
            spacing={"4": {"value": "20px"}}
        )
        result = px_to_rem(tokens, base_px=10.0)
        assert result.spacing["4"].value == "2.0rem"


class TestHexToRgb:
    """Test hex_to_rgb transform."""

    def test_convert_6_digit_hex(self):
        """Test converting 6-digit hex to rgb."""
        tokens = DesignTokens(
            colors={"primary": {"value": "#3b82f6"}}
        )
        result = hex_to_rgb(tokens)
        assert result.colors["primary"].value == "rgb(59, 130, 246)"

    def test_convert_3_digit_hex(self):
        """Test converting 3-digit hex to rgb."""
        tokens = DesignTokens(
            colors={"primary": {"value": "#fff"}}
        )
        result = hex_to_rgb(tokens)
        assert result.colors["primary"].value == "rgb(255, 255, 255)"

    def test_convert_8_digit_hex_with_alpha(self):
        """Test converting 8-digit hex with alpha to rgba."""
        tokens = DesignTokens(
            colors={"primary": {"value": "#3b82f680"}}
        )
        result = hex_to_rgb(tokens)
        assert result.colors["primary"].value == "rgba(59, 130, 246, 0.50)"

    def test_preserve_non_hex_colors(self):
        """Test that non-hex colors are preserved."""
        tokens = DesignTokens(
            colors={
                "primary": {"value": "rgb(59, 130, 246)"},
                "secondary": {"value": "blue"},
            }
        )
        result = hex_to_rgb(tokens)
        assert result.colors["primary"].value == "rgb(59, 130, 246)"
        assert result.colors["secondary"].value == "blue"

    def test_nested_colors(self):
        """Test converting nested color structure."""
        tokens = DesignTokens(
            colors={
                "primary": {
                    "500": {"value": "#3b82f6"},
                    "600": {"value": "#2563eb"},
                }
            }
        )
        result = hex_to_rgb(tokens)
        assert result.colors["primary"]["500"]["value"] == "rgb(59, 130, 246)"
        assert result.colors["primary"]["600"]["value"] == "rgb(37, 99, 235)"


class TestFlattenNested:
    """Test flatten_nested transform."""

    def test_flatten_nested_colors(self):
        """Test flattening nested color structure."""
        tokens = DesignTokens(
            colors={
                "primary": {
                    "500": {"value": "#3b82f6"},
                    "600": {"value": "#2563eb"},
                }
            }
        )
        result = flatten_nested(tokens)
        assert "primary-500" in result.colors
        assert "primary-600" in result.colors
        assert result.colors["primary-500"].value == "#3b82f6"

    def test_preserve_flat_structure(self):
        """Test that flat structure is preserved."""
        tokens = DesignTokens(
            colors={"primary": {"value": "#3b82f6"}}
        )
        result = flatten_nested(tokens)
        assert "primary" in result.colors
        assert result.colors["primary"].value == "#3b82f6"

    def test_custom_separator(self):
        """Test custom separator."""
        tokens = DesignTokens(
            colors={
                "primary": {
                    "500": {"value": "#3b82f6"},
                }
            }
        )
        result = flatten_nested(tokens, separator=".")
        assert "primary.500" in result.colors


class TestAddCssVarPrefix:
    """Test add_css_var_prefix transform."""

    def test_add_prefix_to_colors(self):
        """Test adding -- prefix to color keys."""
        tokens = DesignTokens(
            colors={"primary": {"value": "#3b82f6"}}
        )
        result = add_css_var_prefix(tokens)
        assert "--primary" in result.colors
        assert result.colors["--primary"].value == "#3b82f6"

    def test_preserve_existing_prefix(self):
        """Test that existing prefix is not duplicated."""
        tokens = DesignTokens(
            colors={"--primary": {"value": "#3b82f6"}}
        )
        result = add_css_var_prefix(tokens)
        assert "--primary" in result.colors
        assert "--" not in result.colors  # No double prefix

    def test_custom_prefix(self):
        """Test custom prefix."""
        tokens = DesignTokens(
            colors={"primary": {"value": "#3b82f6"}}
        )
        result = add_css_var_prefix(tokens, prefix="$")
        assert "$primary" in result.colors


class TestSortByCategory:
    """Test sort_by_category transform."""

    def test_sort_colors_alphabetically(self):
        """Test sorting color keys alphabetically."""
        tokens = DesignTokens(
            colors={
                "secondary": {"value": "#8b5cf6"},
                "primary": {"value": "#3b82f6"},
                "accent": {"value": "#f59e0b"},
            }
        )
        result = sort_by_category(tokens)
        keys = list(result.colors.keys())
        assert keys == ["accent", "primary", "secondary"]

    def test_sort_nested_structure(self):
        """Test sorting nested structure."""
        tokens = DesignTokens(
            colors={
                "primary": {
                    "600": {"value": "#2563eb"},
                    "500": {"value": "#3b82f6"},
                }
            }
        )
        result = sort_by_category(tokens)
        nested_keys = list(result.colors["primary"].keys())
        assert nested_keys == ["500", "600"]


class TestTokenTransformer:
    """Test TokenTransformer pipeline."""

    def test_register_and_apply_single_transform(self):
        """Test registering and applying single transform."""
        transformer = TokenTransformer()
        transformer.register(px_to_rem)

        tokens = DesignTokens(
            spacing={"4": {"value": "16px"}}
        )
        result = transformer.apply(tokens)
        assert result.spacing["4"].value == "1.0rem"

    def test_apply_multiple_transforms_in_order(self):
        """Test applying multiple transforms in order."""
        transformer = TokenTransformer()
        transformer.register(px_to_rem)
        transformer.register(sort_by_category)

        tokens = DesignTokens(
            spacing={
                "8": {"value": "32px"},
                "4": {"value": "16px"},
            }
        )
        result = transformer.apply(tokens)

        # Check px_to_rem was applied
        assert result.spacing["4"].value == "1.0rem"
        assert result.spacing["8"].value == "2.0rem"

        # Check sort_by_category was applied
        keys = list(result.spacing.keys())
        assert keys == ["4", "8"]

    def test_default_pipeline(self):
        """Test default pipeline."""
        transformer = create_default_pipeline()

        tokens = DesignTokens(
            spacing={
                "8": {"value": "32px"},
                "4": {"value": "16px"},
            }
        )
        result = transformer.apply(tokens)

        # Should have px_to_rem and sort_by_category
        assert result.spacing["4"].value == "1.0rem"
        keys = list(result.spacing.keys())
        assert keys == ["4", "8"]


class TestTokenMerger:
    """Test TokenMerger."""

    def test_merge_two_flat_dicts(self):
        """Test merging two flat token dicts."""
        base = {
            "colors": {
                "primary": "#3b82f6",
                "secondary": "#8b5cf6",
            }
        }
        override = {
            "colors": {
                "secondary": "#a855f7",  # Override
                "accent": "#f59e0b",     # New
            }
        }

        merger = TokenMerger()
        result = merger.merge([base, override])

        assert result["colors"]["primary"] == "#3b82f6"
        assert result["colors"]["secondary"] == "#a855f7"  # Overridden
        assert result["colors"]["accent"] == "#f59e0b"

    def test_merge_nested_dicts(self):
        """Test merging nested token dicts."""
        base = {
            "colors": {
                "primary": {
                    "500": "#3b82f6",
                    "600": "#2563eb",
                }
            }
        }
        override = {
            "colors": {
                "primary": {
                    "600": "#1d4ed8",  # Override
                    "700": "#1e40af",  # New
                }
            }
        }

        merger = TokenMerger()
        result = merger.merge([base, override])

        assert result["colors"]["primary"]["500"] == "#3b82f6"
        assert result["colors"]["primary"]["600"] == "#1d4ed8"  # Overridden
        assert result["colors"]["primary"]["700"] == "#1e40af"

    def test_merge_token_leaf_nodes(self):
        """Test that token leaf nodes are replaced, not merged."""
        base = {
            "colors": {
                "primary": {"value": "#3b82f6", "comment": "Brand blue"}
            }
        }
        override = {
            "colors": {
                "primary": {"value": "#2563eb"}  # No comment
            }
        }

        merger = TokenMerger()
        result = merger.merge([base, override])

        # Override should replace entire token object
        assert result["colors"]["primary"]["value"] == "#2563eb"
        assert "comment" not in result["colors"]["primary"]

    def test_merge_multiple_sources(self):
        """Test merging more than two sources."""
        source1 = {"colors": {"primary": "#3b82f6"}}
        source2 = {"colors": {"secondary": "#8b5cf6"}}
        source3 = {"colors": {"accent": "#f59e0b"}}

        merger = TokenMerger()
        result = merger.merge([source1, source2, source3])

        assert result["colors"]["primary"] == "#3b82f6"
        assert result["colors"]["secondary"] == "#8b5cf6"
        assert result["colors"]["accent"] == "#f59e0b"

    def test_merge_tokens_convenience_function(self):
        """Test merge_tokens convenience function."""
        base = {"colors": {"primary": "#3b82f6"}}
        override = {"colors": {"secondary": "#8b5cf6"}}

        result = merge_tokens(base, override)

        assert result["colors"]["primary"] == "#3b82f6"
        assert result["colors"]["secondary"] == "#8b5cf6"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
