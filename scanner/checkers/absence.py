"""Absence checker — pattern MUST exist."""

import os
import re
import fnmatch

from ..models import Violation

_regex_cache = {}


def _compile(pattern: str):
    if pattern not in _regex_cache:
        _regex_cache[pattern] = re.compile(pattern)
    return _regex_cache[pattern]


class AbsenceChecker:
    def check(self, pattern_def: dict, files: list, theme_path: str) -> list:
        violations = []
        regex = pattern_def["pattern"]
        pre_check = pattern_def.get("pre_check")
        scope_mode = pattern_def.get("scope_mode", "per_file")
        scope = pattern_def.get("scope", "")
        exclude_pattern = pattern_def.get("exclude")
        exclude_path = pattern_def.get("exclude_path")

        if exclude_pattern and files:
            files = [f for f in files
                     if not fnmatch.fnmatch(
                         os.path.relpath(f, theme_path).replace("\\", "/"),
                         exclude_pattern)]

        if exclude_path and files:
            pre_count = len(files)
            files = [f for f in files
                     if exclude_path not in f.replace("\\", "/")]
            if pre_count > 0 and not files:
                return violations

        # File existence check
        if scope == "theme root" and ("/" in regex or "\\" in regex):
            clean_path = regex.replace("\\.", ".").replace("\\", "/")
            target = os.path.join(theme_path, clean_path)
            if not os.path.isfile(target):
                violations.append(Violation(
                    lesson_id=pattern_def["id"],
                    severity=pattern_def["severity"],
                    category=pattern_def["category"],
                    description=pattern_def["description"],
                    file=clean_path,
                    line=0,
                    match_text=f"File does not exist: {clean_path}",
                ))
            return violations

        if not files:
            if pattern_def.get("skip_empty_scope"):
                return violations
            violations.append(Violation(
                lesson_id=pattern_def["id"],
                severity=pattern_def["severity"],
                category=pattern_def["category"],
                description=pattern_def["description"],
                file=f"[NO FILES MATCHING: {scope}]",
                line=0,
                match_text="Scope resolved to 0 files — template may be missing entirely",
            ))
            return violations

        pre_check_matched_any = False
        for filepath in files:
            if _has_file_level_ignore(filepath, pattern_def["id"]):
                continue

            if pre_check:
                pre_matches = _grep_file(pre_check, filepath)
                if not pre_matches:
                    continue
                pre_check_matched_any = True
            else:
                pre_check_matched_any = True

            matches = _grep_file(regex, filepath)
            if not matches:
                if scope_mode == "any":
                    continue
                rel_path = os.path.relpath(filepath, theme_path).replace("\\", "/")
                violations.append(Violation(
                    lesson_id=pattern_def["id"],
                    severity=pattern_def["severity"],
                    category=pattern_def["category"],
                    description=pattern_def["description"],
                    file=rel_path,
                    line=0,
                    match_text=f"Missing: {regex}",
                ))
            else:
                if scope_mode == "any":
                    return violations

        if scope_mode == "any" and files and pre_check_matched_any:
            scope_str = pattern_def.get("scope", "")
            violations.append(Violation(
                lesson_id=pattern_def["id"],
                severity=pattern_def["severity"],
                category=pattern_def["category"],
                description=pattern_def["description"],
                file=f"[NOT FOUND IN: {scope_str}]",
                line=0,
                match_text=f"Missing: {regex}",
            ))

        return violations


def _grep_file(pattern: str, filepath: str) -> list:
    compiled = _compile(pattern)
    matches = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f, 1):
                if compiled.search(line):
                    matches.append((i, line.rstrip()))
    except (OSError, IOError):
        pass
    return matches


def _has_file_level_ignore(filepath: str, lesson_id: str) -> bool:
    """Check first 10 lines for file-level @kiwi-ignore or # nosec comment.

    Supports:
    - @kiwi-ignore LES-XXX
    - @kiwi-ignore all
    - # nosec (ignore all)
    - # nosec: LES-XXX (ignore specific lesson)
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= 10:
                    break
                if f"@kiwi-ignore {lesson_id}" in line or "@kiwi-ignore all" in line:
                    return True
                # Support # nosec comments
                if "# nosec" in line or "#nosec" in line:
                    if re.search(r'#\s*nosec\s*$', line) or re.search(r'#\s*nosec\s*[^:]', line):
                        return True
                    if re.search(rf'#\s*nosec:\s*{re.escape(lesson_id)}', line):
                        return True
    except (OSError, IOError):
        pass
    return False