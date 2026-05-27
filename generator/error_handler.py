"""Error Handling & Validation for UI Generator"""

from pathlib import Path
from typing import Dict, Any, Optional, List
import json


class GeneratorError(Exception):
    """Base exception for generator errors."""
    pass


class ValidationError(GeneratorError):
    """Validation failed."""
    pass


class ParseError(GeneratorError):
    """Failed to parse input."""
    pass


class ConversionError(GeneratorError):
    """Failed to convert HTML to PHP."""
    pass


class Validator:
    """Validate inputs and outputs for UI generator."""

    @staticmethod
    def validate_demo_folder(demo_path: str) -> Dict[str, Any]:
        """
        Validate demo folder structure.

        Returns:
            Validation report with errors/warnings
        """
        demo_dir = Path(demo_path)
        errors = []
        warnings = []

        # Check folder exists
        if not demo_dir.exists():
            errors.append(f"Demo folder not found: {demo_path}")
            return {"valid": False, "errors": errors, "warnings": warnings}

        # Check required files
        required_files = ["code.html"]
        for filename in required_files:
            filepath = demo_dir / filename
            if not filepath.exists():
                errors.append(f"Required file missing: {filename}")

        # Check optional files
        optional_files = ["DESIGN.md", "screen.png"]
        for filename in optional_files:
            filepath = demo_dir / filename
            if not filepath.exists():
                warnings.append(f"Optional file missing: {filename} (will use defaults)")

        # Validate HTML file
        html_path = demo_dir / "code.html"
        if html_path.exists():
            try:
                html_content = html_path.read_text(encoding="utf-8")
                if len(html_content) < 100:
                    warnings.append("HTML file is very short (< 100 chars)")
                if "<html" not in html_content.lower():
                    warnings.append("HTML file may not be valid HTML (no <html> tag)")
            except Exception as e:
                errors.append(f"Failed to read HTML file: {e}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    @staticmethod
    def validate_theme_name(theme_name: str) -> Dict[str, Any]:
        """
        Validate theme name.

        Returns:
            Validation report
        """
        errors = []
        warnings = []

        if not theme_name:
            errors.append("Theme name is required")
            return {"valid": False, "errors": errors, "warnings": warnings}

        # Check length
        if len(theme_name) < 3:
            errors.append("Theme name too short (min 3 chars)")
        if len(theme_name) > 50:
            errors.append("Theme name too long (max 50 chars)")

        # Check characters
        if not theme_name.replace("-", "").replace("_", "").isalnum():
            errors.append("Theme name must contain only letters, numbers, hyphens, dashes")

        # Check reserved names
        reserved = ["wordpress", "woocommerce", "wp-admin", "wp-content"]
        if theme_name.lower() in reserved:
            errors.append(f"Theme name '{theme_name}' is reserved")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    @staticmethod
    def validate_design_tokens(tokens: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate extracted design tokens.

        Returns:
            Validation report
        """
        errors = []
        warnings = []

        # Check required token categories (only colors and typography are mandatory)
        required_categories = ["colors", "typography"]
        for category in required_categories:
            if category not in tokens or not tokens[category]:
                errors.append(f"Missing required token category: {category}")

        # Check optional categories (spacing and borderRadius can use Tailwind defaults)
        optional_categories = ["spacing", "borderRadius"]
        for category in optional_categories:
            if category not in tokens or not tokens[category]:
                warnings.append(f"Optional token category '{category}' not found, will use Tailwind defaults")

        # Validate colors
        if "colors" in tokens:
            colors = tokens["colors"]
            if "primary" not in colors:
                warnings.append("No primary color defined (will use default)")
            if "secondary" not in colors:
                warnings.append("No secondary color defined (will use default)")

            # Check color format
            for key, value in colors.items():
                if not isinstance(value, str):
                    continue
                if not value.startswith("#") and not value.startswith("rgb"):
                    warnings.append(f"Color '{key}' may not be valid: {value}")

        # Validate typography
        if "typography" in tokens:
            typo = tokens["typography"]
            if "fontFamily" not in typo:
                warnings.append("No font family defined (will use default)")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }


class ErrorHandler:
    """Handle errors gracefully with retry logic."""

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    def with_retry(self, func, *args, **kwargs):
        """
        Execute function with retry logic.

        Args:
            func: Function to execute
            *args, **kwargs: Function arguments

        Returns:
            Function result

        Raises:
            Last exception if all retries fail
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    print(f"Attempt {attempt + 1} failed: {e}. Retrying...")
                    continue
                else:
                    print(f"All {self.max_retries} attempts failed.")
                    raise last_error

    def safe_parse_html(self, html_content: str) -> Optional[str]:
        """
        Parse HTML with error handling.

        Returns:
            Parsed HTML or None if failed
        """
        try:
            # Basic validation
            if not html_content or len(html_content) < 10:
                raise ParseError("HTML content is empty or too short")

            # Check for basic HTML structure
            if "<" not in html_content:
                raise ParseError("No HTML tags found")

            return html_content

        except Exception as e:
            print(f"HTML parsing failed: {e}")
            return None

    def safe_convert_to_php(self, html: str, component_type: str) -> Optional[str]:
        """
        Convert HTML to PHP with error handling.

        Returns:
            PHP code or None if failed
        """
        try:
            if not html:
                raise ConversionError("HTML is empty")

            # Basic conversion (placeholder)
            php = f"<?php\n// {component_type}\n?>\n{html}"
            return php

        except Exception as e:
            print(f"HTML→PHP conversion failed: {e}")
            return None


def format_validation_report(report: Dict[str, Any], title: str = "Validation") -> str:
    """Format validation report for display."""
    lines = [f"{title} Report:", ""]

    if report["valid"]:
        lines.append("✓ Valid")
    else:
        lines.append("✗ Invalid")

    if report["errors"]:
        lines.append("")
        lines.append("Errors:")
        for error in report["errors"]:
            lines.append(f"  - {error}")

    if report["warnings"]:
        lines.append("")
        lines.append("Warnings:")
        for warning in report["warnings"]:
            lines.append(f"  - {warning}")

    return "\n".join(lines)