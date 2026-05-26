"""Test G1 generation with actual theme output"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from generator.orchestrator import ThemeGenerator

def main():
    # Generate actual theme
    input_spec = {
        'shop_name': 'Kiwi Test Shop',
        'primary_color': '#3b82f6',
        'secondary_color': '#8b5cf6',
        'font_family': 'Inter, sans-serif'
    }

    print("=== Generating Theme with G0 + G1 ===\n")

    gen = ThemeGenerator('kiwi-test-g1', input_spec, dry_run=False)
    report = gen.generate(phases=['G0', 'G1'])

    print(f'\n=== Generation Report ===')
    print(f'Success: {report.success}')
    print(f'Phases: {report.phases_completed}')
    print(f'Files created: {len(report.files_created)}')
    print(f'Duration: {report.duration_seconds:.2f}s')

    if report.success:
        output_dir = Path('themes/kiwi-test-g1')
        print(f'\nTheme generated at: {output_dir.absolute()}')

        # List generated files
        print(f'\nGenerated files:')
        for f in sorted(report.files_created):
            print(f'  - {f}')

        print(f'\nNext steps:')
        print(f'1. Copy to LocalWP: C:\\Users\\Windows\\Local Sites\\wezone-dev\\app\\public\\wp-content\\themes\\')
        print(f'2. Activate theme in WordPress admin')
        print(f'3. Test pages: Home, Product Archive, Product Detail')
    else:
        print(f'\nError: {report.error_message}')
        if report.violations_remaining:
            print(f'\nViolations:')
            for v in report.violations_remaining:
                print(f"  - [{v['severity']}] {v['lesson_id']}: {v['file']}")

if __name__ == '__main__':
    main()
