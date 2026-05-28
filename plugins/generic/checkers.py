"""Generic checkers — language-agnostic code quality checks."""

import os
import re
from pathlib import Path
from dataclasses import dataclass, field

from .auto_detector import SKIP_DIRS, LANG_EXTENSIONS
from .convention_learner import ConventionSet, _classify_case, _FUNC_PATTERNS, _CLASS_PATTERNS


@dataclass
class Violation:
    file: str
    line: int
    rule: str
    message: str
    severity: str = "SUGGEST"
    category: str = "generic"


def check_naming_consistency(path: str, conventions: ConventionSet, max_files: int = 200) -> list[Violation]:
    """Flag names that deviate from learned naming conventions."""
    violations = []
    naming_rules = conventions.by_category("naming")
    if not naming_rules:
        return violations

    func_rules = {r.pattern: r for r in naming_rules if "Functions" in r.rule}
    class_rules = {r.pattern: r for r in naming_rules if "Classes" in r.rule}

    root = Path(path)
    count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            lang = LANG_EXTENSIONS.get(ext)
            if not lang:
                continue

            fpath = os.path.join(dirpath, f)
            try:
                lines = Path(fpath).read_text(encoding="utf-8", errors="ignore").split("\n")
            except OSError:
                continue

            func_pat = _FUNC_PATTERNS.get(lang)
            class_pat = _CLASS_PATTERNS.get(lang)

            for i, line in enumerate(lines):
                if func_pat:
                    m = func_pat.match(line)
                    if m:
                        name = next((g for g in m.groups() if g), None)
                        if name and len(name) > 2 and not name.startswith("__"):
                            case = _classify_case(name)
                            for expected_case, rule in func_rules.items():
                                if lang in rule.rule and case != expected_case:
                                    violations.append(Violation(
                                        file=fpath,
                                        line=i + 1,
                                        rule="naming-consistency",
                                        message=f"Function '{name}' uses {case}, expected {expected_case}",
                                        category="naming",
                                    ))

                if class_pat:
                    m = class_pat.match(line)
                    if m:
                        name = next((g for g in m.groups() if g), None)
                        if name and len(name) > 2:
                            case = _classify_case(name)
                            for expected_case, rule in class_rules.items():
                                if lang in rule.rule and case != expected_case:
                                    violations.append(Violation(
                                        file=fpath,
                                        line=i + 1,
                                        rule="naming-consistency",
                                        message=f"Class '{name}' uses {case}, expected {expected_case}",
                                        category="naming",
                                    ))

            count += 1
            if count >= max_files:
                return violations

    return violations


_EMPTY_CATCH = {
    "javascript": re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}"),
    "typescript": re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}"),
    "php": re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}"),
    "python": re.compile(r"except.*?:\s*(?:pass|\.\.\.)\s*$"),
    "go": re.compile(r"if\s+err\s*!=\s*nil\s*\{\s*\}"),
}


def check_error_handling(path: str, max_files: int = 200) -> list[Violation]:
    """Flag empty catch/except blocks and swallowed errors."""
    violations = []
    root = Path(path)
    count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            lang = LANG_EXTENSIONS.get(ext)
            if not lang or lang not in _EMPTY_CATCH:
                continue

            fpath = os.path.join(dirpath, f)
            try:
                content = Path(fpath).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            pat = _EMPTY_CATCH[lang]
            for m in pat.finditer(content):
                line_num = content[:m.start()].count("\n") + 1
                violations.append(Violation(
                    file=fpath,
                    line=line_num,
                    rule="empty-error-handler",
                    message="Empty error handler — errors are silently swallowed",
                    severity="HIGH",
                    category="error-handling",
                ))

            count += 1
            if count >= max_files:
                return violations

    return violations


_DEAD_CODE_PATTERNS = [
    (re.compile(r"^\s*(?:return|throw|raise|exit)\b.*$\n\s*\S", re.MULTILINE), "unreachable-code"),
]

_COMMENTED_BLOCK_RE = re.compile(r"((?:^\s*(?://|#).*\n){5,})", re.MULTILINE)


def check_dead_code(path: str, max_files: int = 200) -> list[Violation]:
    """Flag obvious dead code: unreachable statements, large commented blocks."""
    violations = []
    root = Path(path)
    count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            lang = LANG_EXTENSIONS.get(ext)
            if not lang or lang in ("css", "scss", "less", "html", "sql"):
                continue

            fpath = os.path.join(dirpath, f)
            try:
                content = Path(fpath).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for m in _COMMENTED_BLOCK_RE.finditer(content):
                block = m.group(1)
                line_count = block.count("\n")
                if line_count >= 5:
                    line_num = content[:m.start()].count("\n") + 1
                    violations.append(Violation(
                        file=fpath,
                        line=line_num,
                        rule="commented-code-block",
                        message=f"Large commented-out code block ({line_count} lines)",
                        category="dead-code",
                    ))

            count += 1
            if count >= max_files:
                return violations

    return violations


def check_file_size(path: str, max_lines: int = 500, max_files: int = 500) -> list[Violation]:
    """Flag files exceeding a line threshold."""
    violations = []
    root = Path(path)
    count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            lang = LANG_EXTENSIONS.get(ext)
            if not lang or lang in ("css", "scss", "less", "html"):
                continue

            fpath = os.path.join(dirpath, f)
            try:
                lines = Path(fpath).read_text(encoding="utf-8", errors="ignore").count("\n")
            except OSError:
                continue

            if lines > max_lines:
                violations.append(Violation(
                    file=fpath,
                    line=1,
                    rule="file-too-large",
                    message=f"File has {lines} lines (threshold: {max_lines})",
                    category="complexity",
                ))

            count += 1
            if count >= max_files:
                return violations

    return violations


def run_all_checks(path: str, conventions: ConventionSet | None = None) -> list[Violation]:
    """Run all generic checks and return combined violations."""
    violations = []
    violations.extend(check_error_handling(path))
    violations.extend(check_dead_code(path))
    violations.extend(check_file_size(path))
    if conventions:
        violations.extend(check_naming_consistency(path, conventions))
    return violations