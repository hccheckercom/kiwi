"""Presence checker — pattern SHOULD NOT exist."""

import os
import re

from ..models import Violation

_regex_cache = {}


def _compile(pattern: str):
    """Compile regex with cache."""
    if pattern not in _regex_cache:
        try:
            _regex_cache[pattern] = re.compile(pattern)
        except re.error as e:
            import sys
            print(f"[WARN] Invalid regex pattern: {pattern[:100]}... Error: {e}", file=sys.stderr)
            _regex_cache[pattern] = None
    return _regex_cache[pattern]


class PresenceChecker:
    def check(self, pattern_def: dict, files: list, theme_path: str) -> list:
        violations = []
        regex = pattern_def["pattern"]
        exclude_line = pattern_def.get("exclude_line")
        context_guard = pattern_def.get("context_guard")
        max_per_file = pattern_def.get("max_per_file", 0)
        lesson_id = pattern_def["id"]
        dedup_mode = pattern_def.get("dedup", "")

        compiled_regex = _compile(regex)
        if compiled_regex is None:
            import sys
            print(f"[WARN] Skipping lesson {lesson_id} due to invalid regex", file=sys.stderr)
            return []

        compiled_exclude = _compile(exclude_line) if exclude_line else None
        compiled_guard = _compile(context_guard["pattern"]) if context_guard else None

        caller_cache = {}

        for filepath in files:
            matches = _grep_file_compiled(compiled_regex, filepath)
            if not matches:
                continue

            file_lines = _read_lines(filepath)

            if file_lines and _has_file_level_ignore(file_lines, lesson_id):
                continue

            if context_guard and file_lines and compiled_guard:
                if _check_cross_file_guard(
                    filepath, theme_path, compiled_guard, context_guard, caller_cache
                ):
                    continue

            file_count = 0
            reported_this_file = False

            for line_num, line_text in matches:
                if _has_kiwi_ignore(line_text, lesson_id):
                    continue
                if compiled_exclude and compiled_exclude.search(line_text):
                    continue
                if context_guard and file_lines and compiled_guard:
                    lines_before = int(context_guard.get("lines_before", 3))
                    lines_after = int(context_guard.get("lines_after", 0))
                    window_start = max(0, line_num - lines_before - 1)
                    window_end = min(len(file_lines), line_num + lines_after)
                    window = "".join(file_lines[window_start:window_end])
                    if compiled_guard.search(window):
                        continue

                if dedup_mode == "per_file" and reported_this_file:
                    continue

                rel_path = os.path.relpath(filepath, theme_path).replace("\\", "/")
                violations.append(Violation(
                    lesson_id=lesson_id,
                    severity=pattern_def["severity"],
                    category=pattern_def["category"],
                    description=pattern_def["description"],
                    file=rel_path,
                    line=line_num,
                    match_text=line_text.strip()[:120],
                ))
                file_count += 1
                reported_this_file = True
                if max_per_file and file_count >= max_per_file:
                    break

        return violations


def _check_cross_file_guard(
    filepath: str, theme_path: str, compiled_guard, context_guard: dict, caller_cache: dict
) -> bool:
    """Check if caller files contain the guard pattern (cross-file context)."""
    cross_file_guard = context_guard.get("cross_file")
    if not cross_file_guard:
        return False

    filename = os.path.basename(filepath)
    is_template_part = (
        "template-parts" in filepath.replace("\\", "/")
        or "partials" in filepath.replace("\\", "/")
        or "components" in filepath.replace("\\", "/")
    )

    if not is_template_part:
        return False

    cache_key = filepath
    if cache_key in caller_cache:
        return caller_cache[cache_key]

    stem = filename.replace(".php", "")
    escaped_stem = re.escape(stem)

    caller_pattern = re.compile(
        r"get_template_part\s*\(\s*['\"](?:[^'\"]*/)?"
        + escaped_stem
        + r"|include\s*\(\s*.*"
        + re.escape(filename)
        + r"|require\s*\(\s*.*"
        + re.escape(filename)
    )

    php_files = []
    for root, _, fnames in os.walk(theme_path):
        for fn in fnames:
            if fn.endswith(".php"):
                full = os.path.join(root, fn)
                if full != filepath:
                    php_files.append(full)

    for caller_file in php_files:
        try:
            with open(caller_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except (OSError, IOError):
            continue

        if caller_pattern.search(content):
            if compiled_guard.search(content):
                caller_cache[cache_key] = True
                return True

    caller_cache[cache_key] = False
    return False


def _has_kiwi_ignore(line_text: str, lesson_id: str) -> bool:
    if "@kiwi-ignore" not in line_text:
        return False
    return f"@kiwi-ignore {lesson_id}" in line_text or "@kiwi-ignore all" in line_text


def _has_file_level_ignore(file_lines: list, lesson_id: str) -> bool:
    """Check first 10 lines for file-level @kiwi-ignore comment."""
    for line in file_lines[:10]:
        if f"@kiwi-ignore {lesson_id}" in line or "@kiwi-ignore all" in line:
            return True
    return False


def _grep_file_compiled(compiled_regex, filepath: str) -> list:
    matches = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f, 1):
                if compiled_regex.search(line):
                    matches.append((i, line.rstrip()))
    except (OSError, IOError):
        pass
    return matches


def _grep_file(pattern: str, filepath: str) -> list:
    return _grep_file_compiled(_compile(pattern), filepath)


def _read_lines(filepath: str) -> list:
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.readlines()
    except (OSError, IOError):
        return []