"""Debug token extraction for synthetic demos."""
import sys
from pathlib import Path

# Add generator to path
sys.path.insert(0, str(Path(__file__).parent))

from parsers.token_extractor import DesignTokenExtractor

extractor = DesignTokenExtractor()

# Use absolute path from script location
base_path = Path(__file__).parent.parent.parent.parent / 'themes'

for i in [1, 2]:
    print(f'\n=== Demo {i} ===')

    demo_file = base_path / f'synthetic-demo-{i}' / 'code.html'
    print(f'Reading: {demo_file}')

    if not demo_file.exists():
        print(f'ERROR: File not found!')
        continue

    # Use extract_from_html which expects HTML file path
    tokens = extractor.extract_from_html(str(demo_file))

    print(f'Colors: {len(tokens.get("colors", {}))}')
    print(f'Typography: {len(tokens.get("typography", {}))}')
    print(f'Spacing: {len(tokens.get("spacing", {}))}')
    print(f'BorderRadius: {len(tokens.get("borderRadius", {}))}')

    if tokens.get('colors'):
        print(f'  Color values: {tokens["colors"]}')
    else:
        print('  ERROR: No colors extracted!')

    if tokens.get('typography'):
        print(f'  Typography: {tokens["typography"]}')
    else:
        print('  ERROR: No typography extracted!')
