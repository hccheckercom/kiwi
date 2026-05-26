#!/usr/bin/env python3
"""Kiwi Scan wrapper with realtime verbose logging."""

import sys
import os
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Monkey-patch before imports
original_check = None
file_count = 0
total_files = 0

def _verbose_check(self, pattern_def, files, theme_path):
    """Wrapper that logs progress for each file."""
    global file_count, total_files
    total_files = len(files)
    file_count = 0

    print(f"\n🔍 Scanning {total_files} files...\n", flush=True)

    violations = []
    for file_path in files:
        file_count += 1
        rel_path = os.path.relpath(file_path, theme_path) if os.path.isabs(file_path) else file_path
        print(f"  [{file_count}/{total_files}] {rel_path}", flush=True)

        # Call original check for this file
        file_violations = original_check(self, pattern_def, [file_path], theme_path)
        violations.extend(file_violations)

        if file_violations:
            print(f"    ⚠️  Found {len(file_violations)} violation(s)", flush=True)

    print(f"\n✅ Scan complete: {file_count} files checked\n", flush=True)
    return violations

# Patch checker
from scanner.checkers.presence import PresenceChecker
original_check = PresenceChecker.check
PresenceChecker.check = _verbose_check

# Disable auto-resolution
from scanner import cli
cli._find_theme_root = lambda path: path

# Enable unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Run main
from scanner.cli import main
if __name__ == "__main__":
    main()