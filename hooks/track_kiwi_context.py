#!/usr/bin/env python3
"""Track kiwi_context MCP tool calls to enable pre-edit enforcement."""

import json
import os
import sys

MEMORY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "memory"
)


def get_conversation_id():
    """Get current conversation ID with fallback."""
    conv_id = os.environ.get("CLAUDE_CONVERSATION_ID")
    if conv_id:
        return sanitize_filename(conv_id)

    # Fallback: use git branch + hourly timestamp bucket
    try:
        import subprocess
        import time
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=os.path.dirname(MEMORY_DIR)
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            hour_bucket = int(time.time()) // 3600
            return sanitize_filename(f"{branch}-{hour_bucket}")
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
        # Git not available or command failed - use default
        print(f"Warning: Could not get git branch: {e}", file=sys.stderr)

    return "default"


def sanitize_filename(name):
    """Sanitize string for use in filename (remove invalid chars)."""
    import re
    # Replace invalid filename chars with dash
    return re.sub(r'[<>:"/\\|?*]', '-', name)


def get_state_file():
    """Get state file path for current conversation."""
    conv_id = get_conversation_id()
    return os.path.join(MEMORY_DIR, f".kiwi_context_state.{conv_id}.json")


def load_state():
    """Load conversation state."""
    state_file = get_state_file()
    if not os.path.exists(state_file):
        return {"kiwi_context_called": False}
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[kiwi] load_state error: {e}", file=sys.stderr)
        return {"kiwi_context_called": False}


def save_state(state):
    """Save conversation state."""
    state_file = get_state_file()
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def cleanup_old_state_files(days=7):
    """Remove state files older than N days."""
    import time
    import glob

    cutoff = time.time() - (days * 86400)
    pattern = os.path.join(MEMORY_DIR, ".kiwi_context_state.*.json")

    removed = 0
    for file_path in glob.glob(pattern):
        try:
            if os.path.getmtime(file_path) < cutoff:
                os.remove(file_path)
                removed += 1
        except (OSError, PermissionError) as e:
            # Log but don't fail - file may be in use or already deleted
            print(f"Warning: Could not remove {file_path}: {e}", file=sys.stderr)

    return removed


def main():
    """Mark kiwi_context as called for current conversation."""
    import time

    state = {
        "kiwi_context_called": True,
        "timestamp": time.time()
    }

    save_state(state)
    conv_id = get_conversation_id()

    # Cleanup old state files (keep last 7 days)
    removed = cleanup_old_state_files(days=7)

    print(f"OK kiwi_context tracked for conversation {conv_id}")
    if removed > 0:
        print(f"  Cleaned up {removed} old state file(s)", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"⚠️  Track hook error: {e}", file=sys.stderr)