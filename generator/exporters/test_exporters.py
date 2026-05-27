"""Unit tests for token exporters."""

import pytest

from exporters.base import BaseExporter
from exporters.css_exporter import CSSExporter
from exporters.scss_exporter import SCSSExporter
from exporters.php_exporter import PHPExporter
from exporters.tailwind_exporter import TailwindExporter
from tokens.schema import DesignTokens


class TestCSSExporter:
    """Test CSS exporter."""

    def test_export_colors(self):
        """Test exporting colors to CSS variables."""
        tokens = DesignTokens(
            colors={
                "primary": {"value": "#3b82f6"},
                "secondary": {"value": "#8b5cf6"},
            }
        )
        exporter = CSSExporter()
        result = exporter.export(tokens)

        assert ":root {" in result
        assert "--color-primary: #3b82f6;" in result
        assert "--color-secondary: #8b5cf6;" in result
        assert "}" in result

    def test_export_nested_colors(self):
        """Test exporting nested color structure."""
        tokens = DesignTokens(
            colors={
                "primary": {
                    "500": {"value": "#3b82f6"},
                    "600": {"value": "#2563eb"},
                }
            }
        )
        exporter = CSSExporter()
        result = exporter.export(tokens)

        assert "--color-primary-500: #3b82f6;" in result
        assert "--color-primary-600: #2563eb;" in result

    def test_export_typography(self):
        """Test exporting typography to CSS variables."""
        tokens = DesignTokens(
            typography={
                "h1": {"fontSize": "2.5rem", "lineHeight": "1.2"},
            }
        )
        exporter = CSSExporter()
        result = exporter.export(tokens)

        assert "--font-h1-size: 2.5rem;" in result or "--font-h1-fontSize: 2.5rem;" in result

    def test_custom_options(self):
        """Test custom exporter options."""
        tokens = DesignTokens(
            colors={"primary": {"value": "#3b82f6"}}
        )
        exporter = CSSExporter(options={
            "selector": ".theme",
            "prefix": "$"
        })
        result = exporter.export(tokens)

        assert ".theme {" in result
        assert "$color-primary: #3b82f6;" in result


class TestSCSSExporter:
    """Test SCSS exporter."""

    def test_export_colors(self):
        """Test exporting colors to SCSS map."""
        tokens = DesignTokens(
            colors={
                "primary": {"value": "#3b82f6"},
                "secondary": {"value": "#8b5cf6"},
            }
        )
        exporter = SCSSExporter()
        result = exporter.export(tokens)

        assert "$tokens: (" in result
        assert "'color': (" in result
        assert "'primary': #3b82f6," in result
        assert "'secondary': #8b5cf6," in result
        assert ");" in result

    def test_export_nested_colors(self):
        """Test exporting nested color structure."""
        tokens = DesignTokens(
            colors={
                "primary": {
                    "500": {"value": "#3b82f6"},
                    "600": {"value": "#2563eb"},
                }
            }
        )
        exporter = SCSSExporter()
        result = exporter.export(tokens)

        assert "'primary': (" in result
        assert "'500': #3b82f6," in result
        assert "'600': #2563eb," in result

    def test_custom_map_name(self):
        """Test custom map name."""
        tokens = DesignTokens(
            colors={"primary": {"value": "#3b82f6"}}
        )
        exporter = SCSSExporter(options={"map_name": "$theme"})
        result = exporter.export(tokens)

        assert "$theme: (" in result


class TestPHPExporter:
    """Test PHP exporter."""

    def test_export_colors(self):
        """Test exporting colors to PHP array."""
        tokens = DesignTokens(
            colors={
                "primary": {"value": "#3b82f6"},
                "secondary": {"value": "#8b5cf6"},
            }
        )
        exporter = PHPExporter()
        result = exporter.export(tokens)

        assert "<?php" in result
        assert "return [" in result
        assert "'colors' => [" in result
        assert "'primary' => '#3b82f6'," in result
        assert "'secondary' => '#8b5cf6'," in result
        assert "];" in result

    def test_export_nested_colors(self):
        """Test exporting nested color structure."""
        tokens = DesignTokens(
            colors={
                "primary": {
                    "500": {"value": "#3b82f6"},
                    "600": {"value": "#2563eb"},
                }
            }
        )
        exporter = PHPExporter()
        result = exporter.export(tokens)

        assert "'primary' => [" in result
        assert "'500' => '#3b82f6'," in result
        assert "'600' => '#2563eb'," in result

    def test_export_typography(self):
        """Test exporting typography to PHP array."""
        tokens = DesignTokens(
            typography={
                "h1": {"fontSize": "2.5rem", "lineHeight": "1.2"},
            }
        )
        exporter = PHPExporter()
        result = exporter.export(tokens)

        assert "'typography' => [" in result
        assert "'h1' => [" in result


class TestTailwindExporter:
    """Test Tailwind exporter."""

    def test_export_colors(self):
        """Test exporting colors to Tailwind config."""
        tokens = DesignTokens(
            colors={
                "primary": {"value": "#3b82f6"},
                "secondary": {"value": "#8b5cf6"},
            }
        )
        exporter = TailwindExporter()
        result = exporter.export(tokens)

        assert "module.exports = {" in result
        assert "theme: {" in result
        assert "extend: {" in result
        assert "colors: {" in result
        assert "primary: '#3b82f6'," in result
        assert "secondary: '#8b5cf6'," in result

    def test_export_nested_colors(self):
        """Test exporting nested color structure."""
        tokens = DesignTokens(
            colors={
                "primary": {
                    "500": {"value": "#3b82f6"},
                    "600": {"value": "#2563eb"},
                }
            }
        )
        exporter = TailwindExporter()
        result = exporter.export(tokens)

        assert "primary: {" in result
        assert "'500': '#3b82f6'," in result
        assert "'600': '#2563eb'," in result

    def test_export_typography_with_line_height(self):
        """Test exporting typography with lineHeight."""
        tokens = DesignTokens(
            typography={
                "h1": {"fontSize": "2.5rem", "lineHeight": "1.2"},
            }
        )
        exporter = TailwindExporter()
        result = exporter.export(tokens)

        assert "fontSize: {" in result
        # lineHeight becomes TypographyToken object with nested structure
        # Just verify the key parts are present
        assert "h1:" in result
        assert "'2.5rem'" in result
        assert "lineHeight" in result

    def test_export_spacing(self):
        """Test exporting spacing to Tailwind config."""
        tokens = DesignTokens(
            spacing={
                "4": {"value": "1rem"},
                "8": {"value": "2rem"},
            }
        )
        exporter = TailwindExporter()
        result = exporter.export(tokens)

        assert "spacing: {" in result
        assert "'4': '1rem'," in result
        assert "'8': '2rem'," in result

    def test_json_format(self):
        """Test JSON format output."""
        tokens = DesignTokens(
            colors={"primary": {"value": "#3b82f6"}}
        )
        exporter = TailwindExporter(options={"format": "json"})
        result = exporter.export(tokens)

        # Should be valid JSON
        import json
        config = json.loads(result)
        assert config["theme"]["extend"]["colors"]["primary"] == "#3b82f6"


class TestExporterIntegration:
    """Test exporter integration scenarios."""

    def test_export_all_formats(self):
        """Test exporting same tokens to all formats."""
        tokens = DesignTokens(
            colors={"primary": {"value": "#3b82f6"}},
            typography={"h1": {"fontSize": "2.5rem"}},
            spacing={"4": {"value": "1rem"}},
        )

        # CSS
        css = CSSExporter().export(tokens)
        assert "--color-primary: #3b82f6;" in css

        # SCSS
        scss = SCSSExporter().export(tokens)
        assert "'primary': #3b82f6," in scss

        # PHP
        php = PHPExporter().export(tokens)
        assert "'primary' => '#3b82f6'," in php

        # Tailwind
        tailwind = TailwindExporter().export(tokens)
        assert "primary: '#3b82f6'," in tailwind

    def test_export_to_file(self):
        """Test exporting to file."""
        import tempfile
        import os

        tokens = DesignTokens(
            colors={"primary": {"value": "#3b82f6"}}
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "tokens.css")
            exporter = CSSExporter()
            exporter.export_to_file(tokens, file_path)

            # Verify file was created
            assert os.path.exists(file_path)

            # Verify content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                assert "--color-primary: #3b82f6;" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
