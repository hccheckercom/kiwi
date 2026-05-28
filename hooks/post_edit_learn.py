#!/usr/bin/env python3
"""PostToolUse hook — extract lesson candidates from theme file edits."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    tool_input = os.environ.get("TOOL_INPUT", "")
    tool_output = os.environ.get("TOOL_OUTPUT", "")
    if not tool_input:
        return

    try:
        data = json.loads(tool_input)
    except json.JSONDecodeError:
        return

    file_path = data.get("file_path", "")
    if not file_path:
        return

    # Only learn from theme files
    norm = file_path.replace("\\", "/")
    if "/themes/" not in norm:
        return

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in (".php", ".js", ".ts", ".css", ".scss"):
        return

    # old_string/new_string available for Edit; for Write we have no before
    old_string = data.get("old_string")
    new_string = data.get("new_string")
    if old_string is None or new_string is None:
        return

    # Wrap in minimal file context so diff is meaningful
    before = old_string
    after = new_string

    try:
        from generator.learning.fix_extractor import extract_lesson_candidate
        # Extract theme slug from path
        parts = norm.split("/themes/")
        theme_slug = parts[1].split("/")[0] if len(parts) > 1 else ""
        extract_lesson_candidate(before, after, file_path, theme_slug)
    except Exception:
        pass  # Never block the edit


if __name__ == "__main__":
    main()