#!/usr/bin/env python3
"""Check if test file matches LES-610 scope"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scanner.loader import load_patterns
from scanner.resolver import resolve_scope

patterns = load_patterns(platform='nextjs')
les610 = [p for p in patterns if p['id'] == 'LES-610']

if not les610:
    print("ERROR: LES-610 not found in patterns")
    sys.exit(1)

les610 = les610[0]

print("LES-610 pattern:")
print(f"  type: {les610['type']}")
print(f"  ast_check: {les610.get('ast_check')}")
print(f"  scope: {les610['scope']}")
print(f"  exclude: {les610.get('exclude')}")

theme_path = str(Path(__file__).parent.parent.parent / "webstore-vn")
files = resolve_scope(theme_path, les610['scope'], les610.get('exclude'))

test_files = [f for f in files if 'unhandled-promise-demo' in f]

print(f"\nTotal files matching scope: {len(files)}")
print(f"Test file found: {len(test_files) > 0}")

if test_files:
    print(f"\nTest file path:")
    for f in test_files:
        print(f"  {f}")
else:
    print("\nERROR: Test file not found in scope!")
    print("Checking if file exists...")
    test_file = Path(theme_path) / "unhandled-promise-demo.ts"
    print(f"  File exists: {test_file.exists()}")
    print(f"  File path: {test_file}")
