#!/usr/bin/env python3
"""Kiwi log_read hook — capture Read calls for learning context patterns.

Data arrives via stdin as JSON (Claude Code PostToolUse hook protocol).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    # Claude Code sends hook data via stdin, NOT env vars
    try:
        stdin_data = sys.stdin.read()
    except Exception:
        return

    if not stdin_data:
        return

    try:
        payload = json.loads(stdin_data)
    except json.JSONDecodeError:
        return

    # Extract file_path from tool_input inside the payload
    tool_input = payload.get("tool_input", {})
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except json.JSONDecodeError:
            return

    file_path = tool_input.get("file_path", "")
    if not file_path:
        return

    # Skip internal/infrastructure files
    skip_patterns = [".claude/kiwi/", ".claude\\kiwi\\", "node_modules", ".git/"]
    if any(p in file_path for p in skip_patterns):
        return

    try:
        from agent.reasoning.session_logger import log_tool_call

        log_tool_call("Read", file_path)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass