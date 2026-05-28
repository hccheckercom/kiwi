"""Bridge between LSP server and Kiwi Core scanner engine."""

import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from scanner import load_patterns, resolve_scope, Violation, Report
from scanner.loader import get_lesson_frontmatter


class KiwiBridge:
    """Connects LSP requests to Kiwi scanner for file-level analysis."""

    def __init__(self, config=None):
        from lsp.config import LspConfig
        self.config = config or LspConfig()
        self._patterns = None

    def _ensure_patterns(self) -> list:
        if self._patterns is None:
            lessons_dir = self.config.lessons_dir
            if not lessons_dir:
                lessons_dir = str(Path(__file__).parent.parent / "lessons")
            self._patterns = load_patterns(
                lessons_dir,
                platform=self.config.platform,
                scope_type=self.config.scope_type,
            )
        return self._patterns

    def invalidate_patterns(self):
        self._patterns = None

    def scan_file(self, file_path: str, content: Optional[str] = None) -> List[Violation]:
        """Scan a single file and return violations."""
        patterns = self._ensure_patterns()
        path = Path(file_path)

        if not path.exists() and content is None:
            return []

        if content is None:
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except (OSError, IOError):
                return []

        violations = []
        lines = content.split("\n")

        for pat in patterns:
            scan_type = pat.get("scan", {}).get("type", "presence")
            severity = pat.get("severity", "SUGGEST")

            if self.config.severity_filter != "ALL":
                severity_order = {"CRITICAL": 0, "HIGH": 1, "SUGGEST": 2}
                filter_level = severity_order.get(self.config.severity_filter, 2)
                pat_level = severity_order.get(severity, 2)
                if pat_level > filter_level:
                    continue

            scope_patterns = pat.get("scan", {}).get("scope", "**/*")
            if isinstance(scope_patterns, str):
                scope_patterns = [scope_patterns]

            if not _file_matches_scope(file_path, scope_patterns):
                continue

            if scan_type == "presence":
                import re
                pattern_str = pat.get("scan", {}).get("pattern", "")
                if not pattern_str:
                    continue
                try:
                    regex = re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
                except re.error:
                    continue

                for i, line in enumerate(lines, 1):
                    if regex.search(line):
                        violations.append(Violation(
                            lesson_id=pat.get("id", "UNKNOWN"),
                            severity=severity,
                            category=pat.get("category", "general"),
                            description=pat.get("title", "Violation detected"),
                            file=file_path,
                            line=i,
                            match_text=line.strip(),
                        ))

            elif scan_type == "absence":
                pattern_str = pat.get("scan", {}).get("pattern", "")
                if not pattern_str:
                    continue
                import re
                try:
                    regex = re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
                except re.error:
                    continue

                if not regex.search(content):
                    violations.append(Violation(
                        lesson_id=pat.get("id", "UNKNOWN"),
                        severity=severity,
                        category=pat.get("category", "general"),
                        description=pat.get("title", "Missing required pattern"),
                        file=file_path,
                        line=1,
                        match_text="",
                    ))

        max_diag = self.config.max_diagnostics_per_file
        if len(violations) > max_diag:
            violations = violations[:max_diag]

        return violations

    def get_fix_suggestion(self, lesson_id: str) -> Optional[dict]:
        """Get fix suggestion for a lesson."""
        try:
            fm, body = get_lesson_frontmatter(lesson_id)
            if fm and "fix" in fm:
                return {
                    "lesson_id": lesson_id,
                    "fix_type": fm["fix"].get("type", "replace"),
                    "good_code": fm.get("good_code", ""),
                    "description": fm.get("title", ""),
                    "body": body,
                }
        except Exception:
            pass
        return None

    def get_lesson_info(self, lesson_id: str) -> Optional[dict]:
        """Get lesson info for hover display."""
        try:
            fm, body = get_lesson_frontmatter(lesson_id)
            if fm:
                return {
                    "id": lesson_id,
                    "title": fm.get("title", ""),
                    "severity": fm.get("severity", ""),
                    "category": fm.get("category", ""),
                    "why": fm.get("why", ""),
                    "good_code": fm.get("good_code", ""),
                    "bad_code": fm.get("bad_code", ""),
                }
        except Exception:
            pass
        return None


def _file_matches_scope(file_path: str, scope_patterns: list) -> bool:
    """Check if file matches any of the scope glob patterns."""
    from fnmatch import fnmatch
    file_path_normalized = file_path.replace("\\", "/")
    name = Path(file_path).name

    for pattern in scope_patterns:
        pattern = pattern.replace("\\", "/")
        if fnmatch(name, pattern) or fnmatch(file_path_normalized, pattern):
            return True
        if pattern.startswith("**/"):
            suffix = pattern[3:]
            if fnmatch(name, suffix) or fnmatch(file_path_normalized, "*/" + suffix):
                return True
    return False
