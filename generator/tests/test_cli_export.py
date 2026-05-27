"""Tests for CLI export functionality."""

import pytest
import tempfile
import shutil
from pathlib import Path
import sys

# Add generator to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli_export import export_tokens, export_all, EXPORTERS


@pytest.fixture
def temp_theme():
    """Create temporary theme with demo folder."""
    temp_dir = tempfile.mkdtemp()
    theme_dir = Path(temp_dir) / "test-theme"
    demo_dir = theme_dir / "demos" / "demo1"
    demo_dir.mkdir(parents=True)

    # Create minimal DESIGN.md
    design_file = demo_dir / "DESIGN.md"
    design_file.write_text("""---
colors:
  primary: "#3b82f6"
  secondary: "#8b5cf6"
typography:
  h1:
    fontSize: "40px"
    lineHeight: "1.2"
spacing:
  "4": "16px"
borderRadius:
  md: "8px"
---

# Test Theme
""", encoding="utf-8")

    # Create minimal code.html
    html_file = demo_dir / "code.html"
    html_file.write_text("""<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body><h1>Test</h1></body>
</html>
""", encoding="utf-8")

    yield str(theme_dir)

    # Cleanup
    shutil.rmtree(temp_dir)


def test_export_css(temp_theme):
    """Test CSS export."""
    output_file = Path(temp_theme) / "test-output.css"
    success = export_tokens(temp_theme, "css", str(output_file))

    assert success
    assert output_file.exists()

    content = output_file.read_text(encoding="utf-8")
    assert ":root {" in content
    assert "--color-primary" in content or "--primary" in content


def test_export_scss(temp_theme):
    """Test SCSS export."""
    output_file = Path(temp_theme) / "test-output.scss"
    success = export_tokens(temp_theme, "scss", str(output_file))

    assert success
    assert output_file.exists()

    content = output_file.read_text(encoding="utf-8")
    assert "$" in content  # SCSS variables


def test_export_php(temp_theme):
    """Test PHP export."""
    output_file = Path(temp_theme) / "test-output.php"
    success = export_tokens(temp_theme, "php", str(output_file))

    assert success
    assert output_file.exists()

    content = output_file.read_text(encoding="utf-8")
    assert "<?php" in content
    assert "return [" in content or "return array(" in content


def test_export_tailwind(temp_theme):
    """Test Tailwind export."""
    output_file = Path(temp_theme) / "test-output.js"
    success = export_tokens(temp_theme, "tailwind", str(output_file))

    assert success
    assert output_file.exists()

    content = output_file.read_text(encoding="utf-8")
    assert "module.exports" in content or "export default" in content


def test_export_all_formats(temp_theme):
    """Test exporting all formats."""
    success = export_all(temp_theme)

    assert success

    # Check all default files exist
    theme_path = Path(temp_theme)
    for _, default_path in EXPORTERS.values():
        output_file = theme_path / default_path
        assert output_file.exists(), f"Missing {default_path}"


def test_export_nonexistent_theme():
    """Test error handling for nonexistent theme."""
    success = export_tokens("themes/nonexistent", "css")
    assert not success


def test_export_invalid_format(temp_theme):
    """Test error handling for invalid format."""
    success = export_tokens(temp_theme, "invalid")
    assert not success


def test_export_with_custom_output(temp_theme):
    """Test export with custom output path."""
    custom_output = Path(temp_theme) / "custom" / "tokens.css"
    success = export_tokens(temp_theme, "css", str(custom_output))

    assert success
    assert custom_output.exists()