"""Data models for Kiwi Scanner v3."""

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class Violation:
    lesson_id: str
    severity: str
    category: str
    description: str
    file: str
    line: int = 0
    match_text: str = ""


@dataclass
class Report:
    theme_path: str
    violations: list = field(default_factory=list)
    patterns_checked: int = 0
    files_scanned: int = 0
    warnings: list = field(default_factory=list)
    ast_skipped_files: int = 0

    @property
    def critical_count(self):
        return sum(1 for v in self.violations if v.severity == "CRITICAL")

    @property
    def high_count(self):
        return sum(1 for v in self.violations if v.severity == "HIGH")

    @property
    def suggest_count(self):
        return sum(1 for v in self.violations if v.severity == "SUGGEST")

    def cap_per_lesson(self, max_count: int) -> "Report":
        """Return new Report with at most max_count violations per lesson_id."""
        if max_count <= 0:
            return self
        counts = defaultdict(int)
        capped = []
        overflow = defaultdict(int)
        for v in self.violations:
            counts[v.lesson_id] += 1
            if counts[v.lesson_id] <= max_count:
                capped.append(v)
            else:
                overflow[v.lesson_id] += 1
        r = Report(
            theme_path=self.theme_path,
            violations=capped,
            patterns_checked=self.patterns_checked,
            files_scanned=self.files_scanned,
        )
        r._overflow = overflow
        if hasattr(self, "_sub_reports"):
            r._sub_reports = self._sub_reports
        return r

    def grouped(self) -> dict:
        """Group violations by lesson_id. Returns {lesson_id: [violations]}."""
        groups = defaultdict(list)
        for v in self.violations:
            groups[v.lesson_id].append(v)
        return dict(groups)