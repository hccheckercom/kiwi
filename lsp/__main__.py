"""Entry point for python -m lsp."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lsp.server import main

main(sys.argv[1:])