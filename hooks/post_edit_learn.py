#!/usr/bin/env python3
"""PostToolUse hook — extract lesson candidates from theme file edits."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Theme slugs that are scratch/test/fixture work — their edits must never feed
# the learning pipeline. A synthetic theme like `test-synthetic-learning` once
# polluted the suggestion table with junk such as `<?php $a = 1; ?>`.
_EXCLUDED_THEME_MARKERS = ("test-", "test_", "synthetic", "fixture", "demo-test", "scratch", "sandbox", "tmp")


def _is_excluded_theme(slug: str) -> bool:
    """True if the theme slug looks like test/synthetic/fixture work."""
    if not slug:
        return True
    s = slug.lower()
    return any(s.startswith(m) or m in s for m in _EXCLUDED_THEME_MARKERS)



def _read_payload():
    """Read hook payload from stdin (Claude Code protocol). Fallback to env var."""
    try:
        stdin_data = sys.stdin.read()
        if stdin_data:
            return json.loads(stdin_data)
    except Exception:
        pass
    raw = os.environ.get("TOOL_INPUT", "")
    if raw:
        try:
            return {"tool_input": json.loads(raw)}
        except json.JSONDecodeError:
            return None
    return None


def main():
    payload = _read_payload()
    if not payload:
        return

    tool_input = payload.get("tool_input") or payload
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except json.JSONDecodeError:
            return

    file_path = tool_input.get("file_path", "")
    if not file_path:
        return

    norm = file_path.replace("\\", "/")
    if "/themes/" not in norm:
        return

    # Skip test/synthetic/fixture themes — their patterns pollute the
    # suggestion table with junk (e.g. `<?php $a = 1; ?>`) that no human
    # would ever promote. The slug is the dir right after /themes/.
    parts = norm.split("/themes/")
    theme_slug = parts[1].split("/")[0] if len(parts) > 1 else ""
    if _is_excluded_theme(theme_slug) or "/tmp" in norm or "/temp/" in norm:
        return

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in (".php", ".js", ".ts", ".css", ".scss"):
        return

    old_string = tool_input.get("old_string")
    new_string = tool_input.get("new_string")

    # Write tool: no old_string. Treat empty before -> full content as creation.
    if old_string is None and new_string is None:
        content = tool_input.get("content")
        if content is None:
            return
        old_string = ""
        new_string = content

    if old_string is None or new_string is None:
        return

    try:
        from memory.db import init_db
        init_db()
    except Exception:
        pass

    try:
        from generator.learning.fix_extractor import extract_lesson_candidate
        parts = norm.split("/themes/")
        theme_slug = parts[1].split("/")[0] if len(parts) > 1 else ""
        extract_lesson_candidate(old_string, new_string, file_path, theme_slug)
    except Exception:
        pass

    # A manually-applied edit that adds a known hardening primitive (nonce,
    # sanitize, error handling) is a confirmed fix — feed it to the AST learner
    # so it can generalize into a contextual rule, the same as a kiwi_fix apply.
    if old_string and _diff_adds_hardening(old_string, new_string):
        try:
            from learning.context_learner import (
                learn_from_fix_context,
                save_contextual_lesson,
            )
            diff = f"- {old_string}\n+ {new_string}"
            line = _first_changed_line(file_path, old_string)
            lesson = learn_from_fix_context(file_path, line, diff)
            if lesson and lesson.confidence >= 0.7:
                save_contextual_lesson(lesson)
        except Exception:
            pass


# Hardening primitives whose APPEARANCE in the +side (but not the −side) means
# the edit fixed a security/robustness gap — exactly what learn_from_fix_context
# knows how to generalize (_analyze_fix_diff in context_learner.py).
_HARDENING_MARKERS = (
    "wp_verify_nonce", "check_ajax_referer", "sanitize_text_field",
    "esc_html", "esc_attr", "esc_url", "is_wp_error", "wp_unslash",
)


def _diff_adds_hardening(old_string: str, new_string: str) -> bool:
    """True if new_string introduces a hardening primitive the old lacked."""
    return any(m in new_string and m not in old_string for m in _HARDENING_MARKERS)


def _first_changed_line(file_path: str, old_string: str) -> int:
    """Best-effort 1-based line of the edit, for AST node lookup. Defaults to 1."""
    try:
        anchor = old_string.strip().splitlines()[0].strip()
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f, 1):
                if anchor and anchor in line:
                    return i
    except Exception:
        pass
    return 1


if __name__ == "__main__":
    main()