"""Investigate remaining 2 CRITICAL violations."""
import os
import re
from pathlib import Path

kiwi_dir = Path(__file__).parent

# Get all Python files
py_files = []
for root, dirs, files in os.walk(kiwi_dir):
    # Skip venv, node_modules, .git
    dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules', 'venv']]
    for f in files:
        if f.endswith('.py'):
            py_files.append(os.path.join(root, f))

print(f'Scanning {len(py_files)} Python files...\n')

critical_violations = []

# Check LES-616: Bare except (excluding test files)
print('Checking LES-616: Bare except clauses...')
for f in py_files:
    try:
        with open(f, 'r', encoding='utf-8') as file:
            for i, line in enumerate(file, 1):
                if re.search(r'except:\s*$', line):
                    if '# nosec' not in line and '#nosec' not in line and '@kiwi-ignore' not in line:
                        critical_violations.append(('LES-616', f, i, line.strip()))
    except (OSError, IOError, UnicodeDecodeError):  # nosec
        pass

# Check LES-638: Hardcoded credentials (excluding test files and pattern templates)
print('Checking LES-638: Hardcoded credentials...')
for f in py_files:
    basename = os.path.basename(f)
    # Skip test files and pattern templates
    if 'test_' in basename or 'single_file.py' in f or '_fill_docs.py' in f:
        continue

    try:
        with open(f, 'r', encoding='utf-8') as file:
            for i, line in enumerate(file, 1):
                # Check for hardcoded credentials
                if re.search(r'(password|secret|api_key|token)\s*=\s*["\'][^"\']{8,}', line, re.I):
                    # Skip if has nosec or is a pattern definition
                    if '# nosec' in line or '#nosec' in line or '@kiwi-ignore' in line:
                        continue
                    if 'pattern' in line or 'bad' in line or 'good' in line:
                        continue
                    if 'get' in line or 'env' in line or 'getenv' in line:
                        continue

                    critical_violations.append(('LES-638', f, i, line.strip()[:80]))
    except (OSError, IOError, UnicodeDecodeError):  # nosec
        pass

print(f'\n{"="*70}')
print(f'Found {len(critical_violations)} CRITICAL violations:')
print(f'{"="*70}\n')

for lesson, f, line, text in critical_violations:
    rel_path = os.path.relpath(f, kiwi_dir)
    print(f'{lesson} | {rel_path}:{line}')
    print(f'  {text[:70]}')
    print()

if len(critical_violations) == 0:
    print('✅ No CRITICAL violations found in production code!')
