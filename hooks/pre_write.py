"""Pre-write hook: Block Write on code files if kiwi_context not called."""

import sys
import json
import os
from pathlib import Path

def main():
    # Read stdin
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # Allow if can't parse

    file_path = data.get("file_path", "")

    # Check if code file
    CODE_EXTENSIONS = (".php", ".css", ".js", ".ts", ".tsx", ".jsx")
    if not file_path.endswith(CODE_EXTENSIONS):
        sys.exit(0)  # Allow non-code files

    # Check state file
    kiwi_dir = Path(__file__).parent.parent
    state_file = kiwi_dir / ".context_state.json"

    if state_file.exists():
        try:
            with open(state_file) as f:
                state = json.load(f)
                if state.get("kiwi_context_called"):
                    sys.exit(0)  # Allow
        except (json.JSONDecodeError, IOError):
            pass

    # BLOCK
    print("❌ BLOCKED: Must call kiwi_context before Write on code files")
    print(f"File: {file_path}")
    print("Run: mcp__kiwi__kiwi_context(task='...', compact=true/false)")
    sys.exit(1)

if __name__ == "__main__":
    main()