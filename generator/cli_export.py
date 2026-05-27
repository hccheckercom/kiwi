"""CLI for exporting design tokens to multiple formats.

Usage:
    python cli_export.py --format css themes/sfvn
    python cli_export.py --format scss themes/sfvn
    python cli_export.py --format php themes/sfvn
    python cli_export.py --format tailwind themes/sfvn
    python cli_export.py --all themes/sfvn
"""

import argparse
import sys
from pathlib import Path

# Add generator directory to path
sys.path.insert(0, str(Path(__file__).parent))

from parsers.token_extractor import DesignTokenExtractor
from tokens import normalize_tokens, validate_design_tokens, create_default_pipeline
from exporters import CSSExporter, SCSSExporter, PHPExporter, TailwindExporter


EXPORTERS = {
    "css": (CSSExporter, "assets/css/tokens.css"),
    "scss": (SCSSExporter, "assets/scss/_tokens.scss"),
    "php": (PHPExporter, "inc/store-config.php"),
    "tailwind": (TailwindExporter, "tailwind.config.js"),
}


def export_tokens(theme_path: str, format_name: str, output_path: str = None) -> bool:
    """Export tokens to specified format.

    Args:
        theme_path: Path to theme folder
        format_name: Export format (css, scss, php, tailwind)
        output_path: Optional custom output path

    Returns:
        True if export succeeded, False otherwise
    """
    theme_dir = Path(theme_path)

    if not theme_dir.exists():
        print(f"Error: Theme path not found: {theme_path}")
        return False

    if format_name not in EXPORTERS:
        print(f"Error: Unknown format '{format_name}'. Valid formats: {', '.join(EXPORTERS.keys())}")
        return False

    # Extract tokens from demo folder
    print(f"Extracting tokens from {theme_path}...")

    demo_dir = theme_dir / "demos" / "demo1"
    if not demo_dir.exists():
        print(f"Error: Demo folder not found: {demo_dir}")
        print(f"  CLI export requires a demo folder with code.html and DESIGN.md")
        print(f"  For themes without demos, use the Python API directly")
        return False

    try:
        extractor = DesignTokenExtractor()
        legacy_tokens = extractor.extract_from_demo(str(demo_dir))
    except Exception as e:
        print(f"Error: Token extraction failed: {e}")
        return False

    # Normalize
    print("Normalizing tokens...")
    tokens = normalize_tokens(legacy_tokens)

    # Validate
    print("Validating tokens...")
    report = validate_design_tokens(tokens.model_dump())

    if not report["valid"]:
        print("Error: Token validation failed:")
        for error in report["errors"]:
            print(f"  - {error}")
        return False

    if report["warnings"]:
        print(f"Warning: {len(report['warnings'])} validation warnings:")
        for warning in report["warnings"][:3]:
            print(f"  - {warning}")

    # Transform
    print("Applying transforms...")
    transformer = create_default_pipeline()
    transformed = transformer.apply(tokens)

    # Export
    exporter_class, default_path = EXPORTERS[format_name]
    exporter = exporter_class()

    output_file = Path(output_path) if output_path else theme_dir / default_path
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"Exporting to {output_file}...")
    exporter.export_to_file(transformed, str(output_file))

    print(f"✓ Successfully exported {format_name} to {output_file}")
    return True


def export_all(theme_path: str) -> bool:
    """Export tokens to all formats.

    Args:
        theme_path: Path to theme folder

    Returns:
        True if all exports succeeded, False otherwise
    """
    print(f"Exporting all formats for {theme_path}...")
    print("=" * 60)

    success_count = 0
    for format_name in EXPORTERS.keys():
        if export_tokens(theme_path, format_name):
            success_count += 1
        print()

    print("=" * 60)
    print(f"Exported {success_count}/{len(EXPORTERS)} formats successfully")

    return success_count == len(EXPORTERS)


def main():
    parser = argparse.ArgumentParser(
        description="Export design tokens to multiple formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m cli_export --format css themes/sfvn
  python -m cli_export --format scss themes/sfvn
  python -m cli_export --format php themes/sfvn
  python -m cli_export --format tailwind themes/sfvn
  python -m cli_export --all themes/sfvn
  python -m cli_export --format css themes/sfvn --output custom/path/tokens.css
        """
    )

    parser.add_argument(
        "theme_path",
        help="Path to theme folder"
    )

    parser.add_argument(
        "--format",
        choices=list(EXPORTERS.keys()),
        help="Export format (css, scss, php, tailwind)"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Export to all formats"
    )

    parser.add_argument(
        "--output",
        help="Custom output path (only with --format)"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.all and not args.format:
        parser.error("Either --format or --all is required")

    if args.all and args.format:
        parser.error("Cannot use both --format and --all")

    if args.output and not args.format:
        parser.error("--output can only be used with --format")

    # Execute
    if args.all:
        success = export_all(args.theme_path)
    else:
        success = export_tokens(args.theme_path, args.format, args.output)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()