"""Verify P0 bugs are fixed."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from parsers.token_extractor import DesignTokenExtractor

print("="*60)
print("VERIFYING P0 BUGS FIXED")
print("="*60)

# Bug 1: Token Extraction (67% failure rate)
print("\n[1/2] Testing token extraction on 3 demos...")
extractor = DesignTokenExtractor()
success_count = 0

for i in [1, 2, 3]:
    demo_path = f'D:/projects/wezone/themes/synthetic-demo-{i}'
    try:
        tokens = extractor.extract_from_demo(demo_path)
        if tokens.get('colors') and tokens.get('typography'):
            print(f"  Demo {i}: PASS")
            success_count += 1
        else:
            print(f"  Demo {i}: FAIL (missing tokens)")
    except Exception as e:
        print(f"  Demo {i}: FAIL ({e})")

print(f"\nToken Extraction: {success_count}/3 success ({success_count/3*100:.0f}%)")
if success_count == 3:
    print("  Status: FIXED")
else:
    print("  Status: STILL BROKEN")

# Bug 2: Feedback Logging
print("\n[2/2] Testing feedback logging...")
try:
    from memory.db import log_component_pattern

    # Test logging a component
    log_component_pattern(
        gen_id='test-verify-001',
        component_type='header',
        html_snippet='<header>test</header>',
        confidence=0.85,
        auto_applied=True
    )
    print("  Feedback logging: PASS")
    print("  Status: FIXED")
except Exception as e:
    print(f"  Feedback logging: FAIL ({e})")
    print("  Status: STILL BROKEN")

print("\n" + "="*60)
print("VERIFICATION COMPLETE")
print("="*60)
