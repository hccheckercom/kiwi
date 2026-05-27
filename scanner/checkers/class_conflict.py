"""Class conflict checker — detect conflicting CSS classes on same element."""

import re
from pathlib import Path
from typing import List, Dict

from ..models import Violation
from ..utils import extract_classes, read_file_cached

CONFLICT_PAIRS = [
    (r"max-w-\w+", r"\bw-full\b", "max-w-* conflicts with w-full"),
    (r"\bhidden\b", r"\bblock\b", "hidden conflicts with block (check responsive prefix)"),
    (r"\bfixed\b", r"\babsolute\b", "fixed conflicts with absolute"),
    (r"\bstatic\b", r"\brelative\b", "static conflicts with relative"),
]


class ClassConflictChecker:
    """Detect conflicting CSS classes on the same element."""

    def check(self, base_path: str, pattern: Dict, files: List[str]) -> List[Violation]:
        violations = []
        conflict_pattern = pattern.get("pattern", "")

        # If lesson specifies custom conflict patterns, use those
        if conflict_pattern:
            pairs = [(conflict_pattern, pattern.get("must_not_contain", ""), pattern.get("title", ""))]
        else:
            pairs = CONFLICT_PAIRS

        base = Path(base_path)

        for filepath in files:
            content = read_file_cached(filepath)
            if content is None:
                continue

            rel = str(Path(filepath).relative_to(base)).replace("\\", "/")

            for i, line in enumerate(content.split("\n"), 1):
                classes = extract_classes(line)
                if not classes:
                    continue

                for pat_a, pat_b, desc in pairs:
                    if not pat_a or not pat_b:
                        continue
                    # Both patterns must match in same className string
                    # But only flag if they're NOT prefixed differently (e.g., md:block + hidden is ok)
                    for cls_str in classes:
                        a_match = re.search(pat_a, cls_str)
                        b_match = re.search(pat_b, cls_str)
                        if a_match and b_match:
                            # Check if they have different responsive prefixes
                            a_prefix = self._get_prefix(cls_str, a_match.start())
                            b_prefix = self._get_prefix(cls_str, b_match.start())
                            if a_prefix == b_prefix:
                                violations.append(Violation(
                                    lesson_id=pattern["id"],
                                    severity=pattern["severity"],
                                    category=pattern["category"],
                                    file=rel,
                                    line=i,
                                    description=desc or pattern.get("title", "Class conflict"),
                                    match_text=cls_str.strip()[:100],
                                ))
                                if len(violations) >= pattern.get("max_per_file", 10):
                                    break

        return violations

    def _get_prefix(self, cls_str: str, pos: int) -> str:
        """Get responsive prefix for the class token at position."""
        start = pos
        while start > 0 and cls_str[start - 1] != ' ':
            start -= 1
        token = cls_str[start:pos]
        for prefix in ("2xl:", "xl:", "lg:", "md:", "sm:"):
            if token.endswith(prefix):
                return prefix.rstrip(":")
        return ""