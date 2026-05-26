"""Cross-check checker — pattern in scope A must have corresponding pattern in scope B."""

import os
import re
from pathlib import Path

from ..models import Violation
from ..resolver import resolve_scope


class CrossChecker:
    def check(self, pattern_def: dict, files: list, theme_path: str) -> list:
        violations = []
        regex = pattern_def["pattern"]
        cross_check = pattern_def.get("cross_check", "")
        cross_scope = pattern_def.get("cross_check_scope")
        ignore_matches = set(pattern_def.get("ignore_matches", []))
        exclude_line = pattern_def.get("exclude_line")
        context_guard = pattern_def.get("context_guard")

        if not cross_check:
            return violations

        cross_content = None
        is_file_target = False

        if cross_scope:
            cross_files = resolve_scope(theme_path, cross_scope)
            cross_content = ""
            for cf in cross_files:
                try:
                    with open(cf, "r", encoding="utf-8", errors="ignore") as f:
                        cross_content += f.read() + "\n"
                except (OSError, IOError):
                    pass
        else:
            cross_parts = [p.strip() for p in cross_check.split("|")]
            file_exts = (".php", ".css", ".js")
            _path_chars = re.compile(r'^[a-zA-Z0-9_./*\-]+$')
            looks_like_files = all(
                any(p.endswith(ext) for ext in file_exts) and _path_chars.match(p)
                for p in cross_parts
            )
            if looks_like_files:
                is_file_target = True
                cross_content = ""
                found_any_file = False
                for cp in cross_parts:
                    clean_path = cp.replace("\\", "/")
                    if "*" in clean_path:
                        for match in Path(theme_path).glob(clean_path):
                            if match.is_file():
                                found_any_file = True
                                try:
                                    with open(match, "r", encoding="utf-8", errors="ignore") as f:
                                        cross_content += f.read() + "\n"
                                except (OSError, IOError):
                                    pass
                    else:
                        target = os.path.join(theme_path, clean_path)
                        if os.path.isfile(target):
                            found_any_file = True
                            try:
                                with open(target, "r", encoding="utf-8", errors="ignore") as f:
                                    cross_content += f.read() + "\n"
                            except (OSError, IOError):
                                pass
                # If no cross_check files found, skip this lesson entirely
                if not found_any_file:
                    return violations

        for filepath in files:
            if _has_file_level_ignore(filepath, pattern_def["id"]):
                continue

            matches = _grep_file(regex, filepath)
            if not matches:
                continue

            file_lines = None
            if context_guard:
                file_lines = _read_lines(filepath)

            if cross_content is None:
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        file_content = f.read()
                except (OSError, IOError):
                    file_content = ""
                for line_num, line_text in matches:
                    if exclude_line and re.search(exclude_line, line_text):
                        continue
                    if context_guard and file_lines:
                        ws = max(0, line_num - int(context_guard.get("lines_before", 3)) - 1)
                        we = min(len(file_lines), line_num + int(context_guard.get("lines_after", 0)))
                        if re.search(context_guard["pattern"], "".join(file_lines[ws:we])):
                            continue
                    if not re.search(cross_check, file_content):
                        rel_path = os.path.relpath(filepath, theme_path).replace("\\", "/")
                        violations.append(Violation(
                            lesson_id=pattern_def["id"],
                            severity=pattern_def["severity"],
                            category=pattern_def["category"],
                            description=pattern_def["description"],
                            file=rel_path,
                            line=line_num,
                            match_text=line_text.strip()[:120],
                        ))
                        break
            elif is_file_target:
                for line_num, line_text in matches:
                    if exclude_line and re.search(exclude_line, line_text):
                        continue
                    if context_guard and file_lines:
                        ws = max(0, line_num - int(context_guard.get("lines_before", 3)) - 1)
                        we = min(len(file_lines), line_num + int(context_guard.get("lines_after", 0)))
                        if re.search(context_guard["pattern"], "".join(file_lines[ws:we])):
                            continue
                    m = re.search(regex, line_text)
                    if m:
                        matched_text = m.group(0).rstrip("(")
                        if matched_text in ignore_matches:
                            continue
                        escaped_text = matched_text.replace(":", "\\:")
                        if matched_text not in cross_content and escaped_text not in cross_content:
                            if file_lines is None:
                                file_lines = _read_lines(filepath)
                            if any(re.search(r'function\s+' + re.escape(matched_text) + r'\s*\(', l) for l in file_lines):
                                continue
                            rel_path = os.path.relpath(filepath, theme_path).replace("\\", "/")
                            violations.append(Violation(
                                lesson_id=pattern_def["id"],
                                severity=pattern_def["severity"],
                                category=pattern_def["category"],
                                description=pattern_def["description"],
                                file=rel_path,
                                line=line_num,
                                match_text=line_text.strip()[:120],
                            ))
            else:
                if not re.search(cross_check, cross_content):
                    for line_num, line_text in matches:
                        if exclude_line and re.search(exclude_line, line_text):
                            continue
                        if context_guard and file_lines:
                            ws = max(0, line_num - int(context_guard.get("lines_before", 3)) - 1)
                            we = min(len(file_lines), line_num + int(context_guard.get("lines_after", 0)))
                            if re.search(context_guard["pattern"], "".join(file_lines[ws:we])):
                                continue
                        rel_path = os.path.relpath(filepath, theme_path).replace("\\", "/")
                        violations.append(Violation(
                            lesson_id=pattern_def["id"],
                            severity=pattern_def["severity"],
                            category=pattern_def["category"],
                            description=pattern_def["description"],
                            file=rel_path,
                            line=line_num,
                            match_text=line_text.strip()[:120],
                        ))

        return violations


def _grep_file(pattern: str, filepath: str) -> list:
    matches = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f, 1):
                if re.search(pattern, line):
                    matches.append((i, line.rstrip()))
    except (OSError, IOError):
        pass
    return matches


def _read_lines(filepath: str) -> list:
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.readlines()
    except (OSError, IOError):
        return []


def _has_file_level_ignore(filepath: str, lesson_id: str) -> bool:
    """Check first 10 lines for file-level @kiwi-ignore comment."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= 10:
                    break
                if f"@kiwi-ignore {lesson_id}" in line or "@kiwi-ignore all" in line:
                    return True
    except (OSError, IOError):
        pass
    return False