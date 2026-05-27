"""Sibling consistency checker — pages in same route group must share layout patterns."""

import re
import os
from pathlib import Path
from typing import List, Dict

from ..models import Violation
from ..utils import read_file_cached


class SiblingConsistencyChecker:
    """Check that sibling pages in same route group have consistent layout."""

    def check(self, base_path: str, pattern: Dict, files: List[str]) -> List[Violation]:
        violations = []
        must_not_contain = pattern.get("must_not_contain", "")
        if not must_not_contain:
            return violations

        regex = re.compile(must_not_contain)
        group_pattern = pattern.get("group_pattern", "")
        target_pattern = pattern.get("target_pattern", "")
        base = Path(base_path)

        # Find group parents (list pages)
        parent_pages = {}
        if group_pattern:
            for f in base.rglob(group_pattern.replace("**/", "")):
                if f.is_file():
                    parent_dir = str(f.parent.relative_to(base)).replace("\\", "/")
                    content = self._read_safe(str(f))
                    has_constraint = bool(regex.search(content))
                    parent_pages[parent_dir] = has_constraint

        # Check target pages (sub-pages)
        for filepath in files:
            fp = Path(filepath)
            rel = str(fp.relative_to(base)).replace("\\", "/")

            # Find which parent group this file belongs to
            parent_dir = self._find_parent_group(rel, parent_pages)
            if parent_dir is None:
                continue

            # If parent does NOT have the constraint, child should NOT either
            if not parent_pages[parent_dir]:
                content = self._read_safe(filepath)
                for i, line in enumerate(content.split("\n"), 1):
                    match = regex.search(line)
                    if match:
                        violations.append(Violation(
                            lesson_id=pattern["id"],
                            severity=pattern["severity"],
                            category=pattern["category"],
                            file=rel,
                            line=i,
                            description=pattern.get("title", "Sibling consistency violation"),
                            match_text=line.strip(),
                        ))
                        break  # One violation per file is enough

        return violations

    def _find_parent_group(self, rel_path: str, parent_pages: Dict) -> str:
        """Find the closest parent group for a file path."""
        parts = rel_path.split("/")
        for i in range(len(parts) - 1, 0, -1):
            candidate = "/".join(parts[:i])
            if candidate in parent_pages:
                return candidate
        return None

    def _read_safe(self, filepath: str) -> str:
        return read_file_cached(filepath) or ""