#!/usr/bin/env python3
"""Debug hook — dump all env vars and stdin to file for inspection."""

import json
import os
import sys
import time
from pathlib import Path

LOG_FILE = Path(__file__).parent.parent / "memory" / "hook_debug.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

with open(LOG_FILE, "a", encoding="utf-8") as f:
    f.write(f"\n{'='*60}\n")
    f.write(f"Timestamp: {time.time()}\n")
    f.write(f"Script: {__file__}\n")
    f.write(f"Args: {sys.argv}\n")

    # Env vars
    relevant = {k: v for k, v in os.environ.items()
                if any(x in k for x in ('TOOL', 'CLAUDE', 'INPUT', 'HOOK'))}
    f.write(f"Env vars: {json.dumps(relevant, indent=2)}\n")

    # TOOL_INPUT
    tool_input = os.environ.get("TOOL_INPUT", "")
    f.write(f"TOOL_INPUT: {tool_input[:500] if tool_input else '(empty)'}\n")

    # stdin
    try:
        stdin_data = sys.stdin.read(1000)
        f.write(f"stdin: {stdin_data[:500] if stdin_data else '(empty)'}\n")
    except Exception as e:
        f.write(f"stdin error: {e}\n")

print("debug hook ran", file=sys.stderr)
