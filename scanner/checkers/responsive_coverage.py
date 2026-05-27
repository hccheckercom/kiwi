"""Responsive coverage checker — ensure responsive classes have base styles."""

import re
from pathlib import Path
from typing import List, Dict

from ..models import Violation
from ..utils import extract_classes, read_file_cached

RESPONSIVE_PREFIXES = ["sm:", "md:", "lg:", "xl:", "2xl:"]


class ResponsiveCoverageChecker:
    """Check that responsive classes have corresponding base (mobile) styles."""

    def check(self, base_path: str, pattern: Dict, files: List[str]) -> List[Violation]:
        violations = []
        base = Path(base_path)
        check_pattern = pattern.get("pattern", "")

        for filepath in files:
            content = read_file_cached(filepath)
            if content is None:
                continue

            rel = str(Path(filepath).relative_to(base)).replace("\\", "/")

            for i, line in enumerate(content.split("\n"), 1):
                classes = extract_classes(line)
                for cls_str in classes:
                    issues = self._check_responsive(cls_str, check_pattern)
                    for issue in issues:
                        violations.append(Violation(
                            lesson_id=pattern["id"],
                            severity=pattern["severity"],
                            category=pattern["category"],
                            file=rel,
                            line=i,
                            description=issue,
                            match_text=cls_str.strip()[:100],
                        ))

        return violations

    def _check_responsive(self, cls_str: str, check_pattern: str = "") -> List[str]:
        """Check for responsive classes missing base styles."""
        issues = []
        tokens = cls_str.split()

        # Group by property (grid-cols, flex, hidden, etc.)
        responsive_props = {}
        base_props = set()

        for token in tokens:
            prefix, prop = self._split_prefix(token)
            if prefix:
                if prop not in responsive_props:
                    responsive_props[prop] = []
                responsive_props[prop].append(prefix)
            else:
                base_props.add(prop)

        # Check: if md:X exists but no base X (or similar base style)
        if check_pattern:
            regex = re.compile(check_pattern)
            for prop, prefixes in responsive_props.items():
                if regex.search(prop) and prop not in base_props:
                    prop_base = self._get_property_base(prop)
                    if prop_base and not any(bp.startswith(prop_base) for bp in base_props):
                        issues.append(f"'{'/'.join(prefixes)}:{prop}' has no base mobile style")

        return issues

    def _split_prefix(self, token: str) -> tuple:
        """Split responsive prefix from class name."""
        for prefix in RESPONSIVE_PREFIXES:
            if token.startswith(prefix):
                return prefix.rstrip(":"), token[len(prefix):]
        return "", token

    def _get_property_base(self, prop: str) -> str:
        """Get the base property name (e.g., grid-cols-2 -> grid-cols)."""
        parts = prop.rsplit("-", 1)
        if len(parts) == 2 and parts[1].isdigit():
            return parts[0]
        return ""

