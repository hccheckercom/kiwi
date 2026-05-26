#!/usr/bin/env python3
"""Kiwi Backup CLI — Run from anywhere in the project."""
import sys
from pathlib import Path

# Add kiwi to path
KIWI_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(KIWI_DIR))

from backup.cli import main

if __name__ == '__main__':
    main()