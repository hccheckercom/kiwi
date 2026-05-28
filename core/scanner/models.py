"""Re-export scanner models from original location for backward compat."""

import sys
from pathlib import Path

# Add parent kiwi dir to path for import
_kiwi_dir = Path(__file__).parent.parent.parent
if str(_kiwi_dir) not in sys.path:
    sys.path.insert(0, str(_kiwi_dir))

from scanner.models import Violation, Report

__all__ = ["Violation", "Report"]