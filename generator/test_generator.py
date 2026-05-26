"""
Test script for Kiwi Generator Phase 1

Quick test to verify foundation generation works end-to-end.
"""

import sys
from pathlib import Path

# Add kiwi to path
kiwi_dir = Path(__file__).parent.parent
sys.path.insert(0, str(kiwi_dir))

from generator.orchestrator import ThemeGenerator, format_generation_report


def test_foundation_generation():
    """Test foundation generation with minimal input."""

    # Test input spec
    input_spec = {
        'shop_name': 'Test Shop',
        'shop_tagline': 'Your trusted online store',
        'shop_phone': '0123456789',
        'shop_email': 'test@example.com',
        'shop_address': '123 Test Street',
        'primary_color': '#3b82f6',
        'secondary_color': '#8b5cf6',
        'accent_color': '#3b82f6',
        'font_family': 'Inter, system-ui, sans-serif',
        'shipping_free_threshold': 500000,
        'shipping_fees': []
    }

    # Create generator
    generator = ThemeGenerator(
        theme_name='test-theme',
        input_spec=input_spec,
        auto_fix=True,
        dry_run=False  # Set to True to preview without writing files
    )

    print("Starting foundation generation...")
    print(f"Output directory: {generator.output_dir}")
    print()

    # Generate
    report = generator.generate(phases=['G0'])

    # Display report
    print(format_generation_report(report))

    return report.success


if __name__ == '__main__':
    success = test_foundation_generation()
    sys.exit(0 if success else 1)