"""BOM checker — detect UTF-8 BOM in PHP files."""

import os

from ..models import Violation


class BomChecker:
    def check(self, pattern_def: dict, files: list, theme_path: str) -> list:
        violations = []
        for filepath in files:
            try:
                with open(filepath, "rb") as f:
                    header = f.read(3)
                if header == b'\xef\xbb\xbf':
                    rel_path = os.path.relpath(filepath, theme_path).replace("\\", "/")
                    violations.append(Violation(
                        lesson_id=pattern_def["id"],
                        severity=pattern_def["severity"],
                        category=pattern_def["category"],
                        description=pattern_def["description"],
                        file=rel_path,
                        line=1,
                        match_text="File starts with UTF-8 BOM (EF BB BF)",
                    ))
            except (OSError, IOError):
                pass
        return violations