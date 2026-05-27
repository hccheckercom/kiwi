"""Integration example — Complete token pipeline from extraction to export.

This example demonstrates the full token management pipeline:
1. Extract tokens from demo HTML + DESIGN.md
2. Normalize to schema
3. Validate
4. Transform (px→rem, sort)
5. Export to multiple formats (CSS, SCSS, PHP, Tailwind)
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from tokens import (
    normalize_tokens,
    validate_design_tokens,
    create_default_pipeline,
    merge_tokens,
)
from exporters import CSSExporter, SCSSExporter, PHPExporter, TailwindExporter


def main():
    """Run complete token pipeline example."""

    # Example: Legacy tokens from token_extractor.py
    legacy_tokens = {
        "colors": {
            "primary": "#3b82f6",
            "secondary": "#8b5cf6",
            "success": "#10b981",
            "error": "#ef4444",
        },
        "typography": {
            "h1": {"fontSize": "40px", "lineHeight": "1.2"},
            "h2": {"fontSize": "32px", "lineHeight": "1.3"},
            "body": {"fontSize": "16px", "lineHeight": "1.5"},
        },
        "spacing": {
            "4": "16px",
            "8": "32px",
            "12": "48px",
            "16": "64px",
        },
        "borderRadius": {
            "sm": "4px",
            "md": "8px",
            "lg": "12px",
        },
    }

    print("=" * 60)
    print("Token Pipeline Integration Example")
    print("=" * 60)

    # Step 1: Normalize to schema
    print("\n[1/5] Normalizing tokens to schema...")
    tokens = normalize_tokens(legacy_tokens)
    print(f"  OK Normalized {tokens.get_token_count()}")

    # Step 2: Validate
    print("\n[2/5] Validating tokens...")
    report = validate_design_tokens(tokens.model_dump())
    if report["valid"]:
        print("  OK Validation passed")
        if report["warnings"]:
            print(f"  WARNING {len(report['warnings'])} warnings:")
            for warning in report["warnings"][:3]:
                print(f"    - {warning}")
    else:
        print("  ERROR Validation failed:")
        for error in report["errors"]:
            print(f"    - {error}")
        return

    # Step 3: Transform
    print("\n[3/5] Applying transforms (px->rem, sort)...")
    transformer = create_default_pipeline()
    transformed = transformer.apply(tokens)
    print("  OK Transforms applied")

    # Step 4: Export to multiple formats
    print("\n[4/5] Exporting to multiple formats...")

    exporters = {
        "CSS": CSSExporter(),
        "SCSS": SCSSExporter(),
        "PHP": PHPExporter(),
        "Tailwind": TailwindExporter(),
    }

    outputs = {}
    for format_name, exporter in exporters.items():
        output = exporter.export(transformed)
        outputs[format_name] = output
        print(f"  OK {format_name}: {len(output)} characters")

    # Step 5: Show sample outputs
    print("\n[5/5] Sample outputs:")

    print("\n--- CSS (first 10 lines) ---")
    print("\n".join(outputs["CSS"].split("\n")[:10]))

    print("\n--- SCSS (first 10 lines) ---")
    print("\n".join(outputs["SCSS"].split("\n")[:10]))

    print("\n--- PHP (first 10 lines) ---")
    print("\n".join(outputs["PHP"].split("\n")[:10]))

    print("\n--- Tailwind (first 10 lines) ---")
    print("\n".join(outputs["Tailwind"].split("\n")[:10]))

    print("\n" + "=" * 60)
    print("Pipeline complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()