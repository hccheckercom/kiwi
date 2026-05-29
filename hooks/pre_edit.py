"""Pre-edit hook: Block Edit/Write on code files if kiwi_context not called.

Reads conversation state written by track_kiwi_context.py.
Allows non-code files. Blocks code files until kiwi_context is invoked
in the current conversation. State expires after STATE_TTL_SEC.
"""

import sys
import json
import os
import time
from pathlib import Path

KIWI_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(KIWI_DIR / "hooks"))

CODE_EXTENSIONS = (".php", ".css", ".js", ".ts", ".tsx", ".jsx")
STATE_TTL_SEC = 3600


def _state_files():
    from track_kiwi_context import get_state_file, get_conversation_id

    primary = get_state_file()
    yield primary

    legacy = KIWI_DIR / ".context_state.json"
    if legacy.exists():
        yield str(legacy)


def _load_first_valid_state():
    for path in _state_files():
        if not path or not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
        except (json.JSONDecodeError, IOError, OSError):
            continue
        if not state.get("kiwi_context_called"):
            continue
        ts = state.get("timestamp", 0)
        if ts and (time.time() - ts) > STATE_TTL_SEC:
            continue
        return state
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    file_path = data.get("file_path") or data.get("tool_input", {}).get("file_path", "")
    if not file_path or not file_path.lower().endswith(CODE_EXTENSIONS):
        sys.exit(0)

    if _load_first_valid_state():
        sys.exit(0)

    print("BLOCKED: Must call kiwi_context before Edit/Write on code files")
    print(f"File: {file_path}")
    print("Run: mcp__kiwi__kiwi_context(task='...', target_file='...', compact=true|false)")
    print(f"State expires after {STATE_TTL_SEC // 60} min — re-call kiwi_context if stale")
    sys.exit(1)


if __name__ == "__main__":
    main()
