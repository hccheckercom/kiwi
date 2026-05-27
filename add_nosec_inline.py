"""Add inline # nosec comments to test files with hardcoded credentials."""
import re
from pathlib import Path

kiwi_dir = Path(__file__).parent

# Find all test files
test_files = list(kiwi_dir.rglob("test_*.py"))

modified_count = 0

for test_file in test_files:
    try:
        content = test_file.read_text(encoding='utf-8')
        lines = content.splitlines(keepends=True)
        modified = False

        for i, line in enumerate(lines):
            # Add nosec to lines with hardcoded credentials (not already having nosec)
            if re.search(r'password\s*=\s*["\']admin|password\s*=\s*["\']secret', line):
                if '# nosec' not in line and '#nosec' not in line:
                    lines[i] = line.rstrip() + '  # nosec\n'
                    modified = True

        if modified:
            test_file.write_text(''.join(lines), encoding='utf-8')
            modified_count += 1
            print(f"Modified: {test_file.name}")

    except Exception as e:
        print(f"Error processing {test_file.name}: {e}")

print(f"\nTotal files modified: {modified_count}")