# nosec - test fixtures with hardcoded credentials for testing purposes
"""Test nosec detection logic."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from scanner.checkers.presence import _has_kiwi_ignore

# Test cases
test_cases = [
    ('pickle.load(f)  # nosec', 'LES-638', True),
    ('pickle.load(f)  # nosec: LES-638', 'LES-638', True),
    ('pickle.load(f)  #nosec', 'LES-638', True),
    ('password = "admin"  # nosec', 'LES-638', True),
    ('password = "admin"', 'LES-638', False),  # nosec
    ('eval(code)  # nosec: LES-629', 'LES-629', True),
    ('eval(code)', 'LES-629', False),
]

print('Testing _has_kiwi_ignore function with nosec support:')
print('=' * 70)
passed = 0
failed = 0

for line, lesson_id, expected in test_cases:
    result = _has_kiwi_ignore(line, lesson_id)
    status = 'PASS' if result == expected else 'FAIL'
    if result == expected:
        passed += 1
    else:
        failed += 1
    print(f'{status}: {line[:50]:50} -> {result} (expected {expected})')

print('=' * 70)
print(f'Results: {passed} passed, {failed} failed')
