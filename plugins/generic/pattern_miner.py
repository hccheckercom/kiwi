"""Mine repeated code patterns from a codebase and suggest new lessons."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from collections import Counter, defaultdict

from .auto_detector import SKIP_DIRS, LANG_EXTENSIONS


@dataclass
class PatternSuggestion:
    title: str
    category: str
    pattern_regex: str
    occurrences: int
    example_files: list = field(default_factory=list)
    suggested_lesson: str = ""
    confidence: float = 0.0


def mine(path: str, min_occurrences: int = 3, max_files: int = 500) -> list[PatternSuggestion]:
    """Mine codebase for repeated patterns worth codifying as lessons."""
    from core.gating import gate_check
    result = gate_check("max_patterns")
    if not result.allowed:
        return []

    root = Path(path)
    if not root.is_dir():
        return []

    suggestions = []
    suggestions.extend(_mine_error_patterns(root, min_occurrences, max_files))
    suggestions.extend(_mine_todo_fixme(root, min_occurrences, max_files))
    suggestions.extend(_mine_magic_numbers(root, min_occurrences, max_files))
    suggestions.extend(_mine_long_functions(root, max_files))
    suggestions.extend(_mine_repeated_blocks(root, min_occurrences, max_files))
    suggestions.extend(_mine_console_debug(root, min_occurrences, max_files))

    suggestions.sort(key=lambda s: s.confidence, reverse=True)
    return suggestions


def _walk_source_files(root: Path, max_files: int):
    """Yield (path, lang) for source files."""
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            lang = LANG_EXTENSIONS.get(ext)
            if lang:
                yield os.path.join(dirpath, f), lang
                count += 1
                if count >= max_files:
                    return


_EMPTY_CATCH = {
    "javascript": re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}", re.MULTILINE),
    "typescript": re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}", re.MULTILINE),
    "php": re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}", re.MULTILINE),
    "python": re.compile(r"except.*?:\s*(?:pass|\.\.\.)\s*$", re.MULTILINE),
    "go": re.compile(r"if\s+err\s*!=\s*nil\s*\{\s*\}", re.MULTILINE),
}


def _mine_error_patterns(root: Path, min_occ: int, max_files: int) -> list[PatternSuggestion]:
    hits = defaultdict(list)

    for fpath, lang in _walk_source_files(root, max_files):
        pat = _EMPTY_CATCH.get(lang)
        if not pat:
            continue
        try:
            content = Path(fpath).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if pat.search(content):
            hits[lang].append(fpath)

    suggestions = []
    for lang, files in hits.items():
        if len(files) >= min_occ:
            suggestions.append(PatternSuggestion(
                title=f"Empty error handler ({lang})",
                category="error-handling",
                pattern_regex=_EMPTY_CATCH[lang].pattern,
                occurrences=len(files),
                example_files=files[:5],
                confidence=min(len(files) / 10, 1.0),
                suggested_lesson=_format_lesson(
                    f"Empty error handler ({lang})",
                    "error-handling",
                    "SUGGEST",
                    _EMPTY_CATCH[lang].pattern,
                    f"Empty catch/except blocks silently swallow errors, making debugging impossible.",
                    "catch (e) {}",
                    "catch (e) { logger.error('Operation failed', e); throw; }",
                ),
            ))
    return suggestions


_TODO_RE = re.compile(r"(?://|#|/\*)\s*(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)


def _mine_todo_fixme(root: Path, min_occ: int, max_files: int) -> list[PatternSuggestion]:
    counts = Counter()
    file_examples = defaultdict(list)

    for fpath, lang in _walk_source_files(root, max_files):
        try:
            content = Path(fpath).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in _TODO_RE.finditer(content):
            tag = m.group(1).upper()
            counts[tag] += 1
            if len(file_examples[tag]) < 5:
                file_examples[tag].append(fpath)

    suggestions = []
    for tag, count in counts.items():
        if count >= min_occ and tag in ("FIXME", "HACK", "XXX"):
            suggestions.append(PatternSuggestion(
                title=f"Unresolved {tag} comments ({count} occurrences)",
                category="code-quality",
                pattern_regex=rf"(?://|#|/\*)\s*{tag}\b",
                occurrences=count,
                example_files=file_examples[tag],
                confidence=min(count / 20, 0.8),
            ))
    return suggestions


_MAGIC_NUMBER_RE = re.compile(
    r"(?<![.\w])\b(\d{2,})\b(?!\s*[;:}\])]?\s*(?://|/\*|#).*(?:px|ms|rem|em|vh|vw|port|status|code|http|error))",
)

_SAFE_NUMBERS = {
    "0", "1", "2", "10", "100", "1000", "60", "24", "365", "1024",
    "200", "201", "204", "301", "302", "400", "401", "403", "404", "500",
}


def _mine_magic_numbers(root: Path, min_occ: int, max_files: int) -> list[PatternSuggestion]:
    number_files = defaultdict(list)

    for fpath, lang in _walk_source_files(root, max_files):
        if lang in ("css", "scss", "less", "html", "sql"):
            continue
        try:
            lines = Path(fpath).read_text(encoding="utf-8", errors="ignore").split("\n")
        except OSError:
            continue
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("//", "#", "/*", "*")):
                continue
            for m in _MAGIC_NUMBER_RE.finditer(stripped):
                num = m.group(1)
                if num not in _SAFE_NUMBERS and len(num) >= 3:
                    number_files[num].append(fpath)

    repeated = {n: files for n, files in number_files.items() if len(set(files)) >= min_occ}
    if not repeated:
        return []

    total = sum(len(set(f)) for f in repeated.values())
    return [PatternSuggestion(
        title=f"Magic numbers repeated across files ({len(repeated)} distinct values)",
        category="code-quality",
        pattern_regex=r"\b\d{3,}\b",
        occurrences=total,
        example_files=list({f for files in repeated.values() for f in files})[:5],
        confidence=min(total / 15, 0.7),
    )] if total >= min_occ else []


def _mine_long_functions(root: Path, max_files: int) -> list[PatternSuggestion]:
    """Detect functions exceeding 100 lines."""
    _FUNC_START = re.compile(
        r"^\s*(?:(?:public|private|protected|static|async|export)\s+)*"
        r"(?:function\s+\w+|def\s+\w+|\w+\s*\([^)]*\)\s*[:{])"
    )
    long_funcs = []

    for fpath, lang in _walk_source_files(root, max_files):
        if lang in ("css", "scss", "less", "html", "sql"):
            continue
        try:
            lines = Path(fpath).read_text(encoding="utf-8", errors="ignore").split("\n")
        except OSError:
            continue

        func_start = None
        brace_depth = 0
        for i, line in enumerate(lines):
            if _FUNC_START.match(line):
                func_start = i
                brace_depth = 0
            if func_start is not None:
                brace_depth += line.count("{") - line.count("}")
                if brace_depth <= 0 and i > func_start:
                    length = i - func_start
                    if length > 100:
                        long_funcs.append((fpath, func_start + 1, length))
                    func_start = None

    if len(long_funcs) < 3:
        return []

    return [PatternSuggestion(
        title=f"Long functions (>{100} lines): {len(long_funcs)} found",
        category="complexity",
        pattern_regex="function_length > 100",
        occurrences=len(long_funcs),
        example_files=[f[0] for f in long_funcs[:5]],
        confidence=min(len(long_funcs) / 10, 0.8),
    )]


_CONSOLE_PATTERNS = {
    "javascript": re.compile(r"\bconsole\.(log|debug|info|warn)\s*\("),
    "typescript": re.compile(r"\bconsole\.(log|debug|info|warn)\s*\("),
    "python": re.compile(r"\bprint\s*\("),
    "php": re.compile(r"\b(?:var_dump|print_r|echo\s+\$|error_log)\s*\("),
}


def _mine_console_debug(root: Path, min_occ: int, max_files: int) -> list[PatternSuggestion]:
    hits = defaultdict(list)

    for fpath, lang in _walk_source_files(root, max_files):
        pat = _CONSOLE_PATTERNS.get(lang)
        if not pat:
            continue
        try:
            content = Path(fpath).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        count = len(pat.findall(content))
        if count >= 3:
            hits[lang].append(fpath)

    suggestions = []
    for lang, files in hits.items():
        if len(files) >= min_occ:
            suggestions.append(PatternSuggestion(
                title=f"Debug/console statements left in code ({lang})",
                category="code-quality",
                pattern_regex=_CONSOLE_PATTERNS[lang].pattern,
                occurrences=len(files),
                example_files=files[:5],
                confidence=min(len(files) / 8, 0.7),
            ))
    return suggestions


_BLOCK_MIN_LINES = 4


def _mine_repeated_blocks(root: Path, min_occ: int, max_files: int) -> list[PatternSuggestion]:
    """Find code blocks repeated across multiple files (potential DRY violations)."""
    block_hashes = defaultdict(list)

    for fpath, lang in _walk_source_files(root, max_files):
        if lang in ("css", "scss", "less", "html"):
            continue
        try:
            lines = Path(fpath).read_text(encoding="utf-8", errors="ignore").split("\n")
        except OSError:
            continue

        for i in range(len(lines) - _BLOCK_MIN_LINES):
            block = "\n".join(line.strip() for line in lines[i:i + _BLOCK_MIN_LINES])
            if len(block) < 40:
                continue
            if block.startswith(("//", "#", "/*", "*", "import", "from", "use ")):
                continue
            key = hash(block)
            if not block_hashes[key] or block_hashes[key][-1][0] != fpath:
                block_hashes[key].append((fpath, i + 1, block))

    repeated = {k: v for k, v in block_hashes.items() if len(v) >= min_occ}
    if not repeated:
        return []

    top = sorted(repeated.values(), key=len, reverse=True)[:5]
    suggestions = []
    for group in top:
        files = list({g[0] for g in group})
        suggestions.append(PatternSuggestion(
            title=f"Repeated code block across {len(files)} files",
            category="dry-violation",
            pattern_regex=group[0][2][:80],
            occurrences=len(group),
            example_files=files[:5],
            confidence=min(len(group) / 5, 0.9),
        ))

    return suggestions


def _format_lesson(title: str, category: str, severity: str, pattern: str,
                   why: str, bad: str, good: str) -> str:
    return f"""---
title: "{title}"
category: {category}
severity: {severity}
scan_type: presence
pattern: '{pattern}'
---

## Why
{why}

## Bad
```
{bad}
```

## Good
```
{good}
```
"""