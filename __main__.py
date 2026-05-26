#!/usr/bin/env python3
"""Kiwi CLI entry point for python -m execution."""

import sys
import os
from pathlib import Path

# Add kiwi directory to path
KIWI_DIR = Path(__file__).parent
if str(KIWI_DIR) not in sys.path:
    sys.path.insert(0, str(KIWI_DIR))

from cli import main

if __name__ == "__main__":
    main()