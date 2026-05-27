"""Dark mode coverage checker — elements with bg-* should have dark:bg-*."""

from pathlib import Path
from typing import List, Dict, Set

from ..models import Violation
from ..utils import extract_classes, read_file_cached

# Base → Dark pairs
DARK_PAIRS = {
    "bg-white": {"dark:bg-gray-900", "dark:bg-gray-800", "dark:bg-slate-900"},
    "bg-gray-50": {"dark:bg-gray-800", "dark:bg-gray-900"},
    "bg-gray-100": {"dark:bg-gray-800", "dark:bg-gray-700"},
    "text-gray-900": {"dark:text-white", "dark:text-gray-100"},
    "text-gray-700": {"dark:text-gray-300", "dark:text-gray-200"},
    "text-gray-500": {"dark:text-gray-400"},
    "text-gray-600": {"dark:text-gray-400", "dark:text-gray-300"},
    "border-gray-200": {"dark:border-gray-700", "dark:border-gray-600"},
    "border-gray-300": {"dark:border-gray-600", "dark:border-gray-700"},
}


class DarkCoverageChecker:
    """Check that light mode classes have corresponding dark mode variants."""

    def check(self, base_path: str, pattern: Dict, files: List[str]) -> List[Violation]:
        violations = []
        base = Path(base_path)
        base_class = pattern.get("base_class", "")
        required_class = pattern.get("required_class", "")
        base_classes = pattern.get("base_classes", [])

        # Build pairs from lesson config
        if base_classes and isinstance(base_classes, list):
            pairs = {}
            for item in base_classes:
                if isinstance(item, dict):
                    bc = item.get("pattern", "")
                    reqs = item.get("requires", [])
                    if bc and reqs:
                        pairs[bc] = set(reqs)
        elif base_class and required_class:
            pairs = {base_class: {required_class}}
        else:
            pairs = DARK_PAIRS

        for filepath in files:
            content = read_file_cached(filepath)
            if content is None:
                continue

            rel = str(Path(filepath).relative_to(base)).replace("\\", "/")
            file_violations = 0

            for i, line in enumerate(content.split("\n"), 1):
                classes = extract_classes(line)
                for cls_str in classes:
                    missing = self._check_dark_coverage(cls_str, pairs)
                    for base_cls, expected in missing:
                        violations.append(Violation(
                            lesson_id=pattern["id"],
                            severity=pattern["severity"],
                            category=pattern["category"],
                            file=rel,
                            line=i,
                            description=f"'{base_cls}' missing dark variant (need one of: {', '.join(expected)})",
                            match_text=cls_str.strip()[:100],
                        ))
                        file_violations += 1
                        if file_violations >= pattern.get("max_per_file", 10):
                            break

                if file_violations >= pattern.get("max_per_file", 10):
                    break

        return violations

    def _check_dark_coverage(self, cls_str: str, pairs: Dict[str, Set[str]]) -> List[tuple]:
        """Check if light classes have dark variants."""
        missing = []
        tokens = set(cls_str.split())

        for base_cls, dark_options in pairs.items():
            if base_cls in tokens:
                if not any(dark_cls in tokens for dark_cls in dark_options):
                    # Check if ANY dark: variant of this property exists
                    prop_type = base_cls.split("-")[0]  # bg, text, border
                    has_any_dark = any(t.startswith(f"dark:{prop_type}-") for t in tokens)
                    if not has_any_dark:
                        missing.append((base_cls, dark_options))

        return missing

