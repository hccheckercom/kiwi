"""Test generation with new checkout and account templates."""
from generator.orchestrator import ThemeGenerator
from pathlib import Path

# Test generation with new templates
generator = ThemeGenerator(
    theme_name='kiwi-test-checkout',
    input_spec={
        'shop_name': 'Test Shop',
        'primary_color': '#3b82f6',
        'secondary_color': '#8b5cf6',
        'font_family': 'Inter, sans-serif'
    },
    dry_run=True
)
result = generator.generate(phases=['G0', 'G1'])

print(f'\n=== Generation Summary ===')
print(f'Success: {result.success}')
print(f'Files created: {len(result.files_created)}')
print(f'Duration: {result.duration_seconds:.2f}s')
print(f'Violations found: {result.violations_found}')
print(f'Violations fixed: {result.violations_fixed}')
print(f'Violations remaining: {len(result.violations_remaining)}')
if result.files_created:
    print(f'\nNew files in this test:')
    for f in result.files_created:
        if 'checkout' in f or 'register' in f or 'progress' in f:
            print(f'  - {f}')
