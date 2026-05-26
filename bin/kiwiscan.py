#!/usr/bin/env python3
"""Kiwi Scan wrapper - disables auto-resolution for direct path scanning."""

import sys
import os
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scanner.cli import main
from scanner import cli

# Monkey-patch _find_theme_root to disable auto-resolution
def _no_auto_resolve(path: str) -> str:
    """Return path as-is without auto-resolution."""
    return path

cli._find_theme_root = _no_auto_resolve

# Enable verbose logging by default
if "--quiet" not in sys.argv and "-q" not in sys.argv:
    # Force unbuffered output for realtime logs
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

if __name__ == "__main__":
    main()