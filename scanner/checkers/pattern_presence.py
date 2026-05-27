"""Pattern presence/absence checker — reusable from Kiwi logic."""

import re
from pathlib import Path
from typing import List, Dict

from ..models import Violation
from ..utils import read_file_cached


class PatternPresenceChecker:
    """Check for presence or absence of patterns in files."""

    def __init__(self, mode: str = "presence"):
        self.mode = mode  # "presence" = should NOT exist, "absence" = MUST exist

    def check(self, base_path: str, pattern: Dict, files: List[str]) -> List[Violation]:
        violations = []
        regex_str = pattern.get("pattern", "")
        if not regex_str:
            return violations

        try:
            regex = re.compile(regex_str)
        except re.error:
            return violations

        base = Path(base_path)

        if self.mode == "presence":
            return self._check_presence(base, pattern, regex, files)
        else:
            return self._check_absence(base, pattern, regex, files)

    def _check_presence(self, base: Path, pattern: Dict, regex, files: List[str]) -> List[Violation]:
        """Pattern SHOULD NOT exist — flag if found."""
        violations = []
        max_per_file = pattern.get("max_per_file", 10)

        for filepath in files:
            content = read_file_cached(filepath)
            if content is None:
                continue

            rel = str(Path(filepath).relative_to(base)).replace("\\", "/")
            count = 0

            for i, line in enumerate(content.split("\n"), 1):
                if regex.search(line):
                    violations.append(Violation(
                        lesson_id=pattern["id"],
                        severity=pattern["severity"],
                        category=pattern["category"],
                        file=rel,
                        line=i,
                        description=pattern.get("title", "Pattern should not exist"),
                        match_text=line.strip()[:100],
                    ))
                    count += 1
                    if count >= max_per_file:
                        break

        return violations

    def _check_absence(self, base: Path, pattern: Dict, regex, files: List[str]) -> List[Violation]:
        """Pattern MUST exist — flag if missing."""
        violations = []

        if not files and pattern.get("skip_empty_scope", False):
            return violations

        for filepath in files:
            content = read_file_cached(filepath)
            if content is None:
                continue

            rel = str(Path(filepath).relative_to(base)).replace("\\", "/")

            if not regex.search(content):
                violations.append(Violation(
                    lesson_id=pattern["id"],
                    severity=pattern["severity"],
                    category=pattern["category"],
                    file=rel,
                    line=0,
                    description=pattern.get("title", "Required pattern missing"),
                    match_text=f"Missing: {pattern.get('pattern', '')}",
                ))

        return violations