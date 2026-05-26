"""
Coverage Matcher & Scorer — Match patterns to lessons, calculate coverage %.

Proactive coverage: identify which patterns are protected by lessons.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from .inventory import CodePattern, FileInventory
from .anomaly import _extract_tokens, _jaccard_similarity
from scanner.loader import load_patterns


@dataclass
class MatchResult:
    """Result of matching a pattern to lessons"""
    matched_lessons: List[str] = field(default_factory=list)
    similarity_score: float = 0.0
    is_covered: bool = False
    match_method: str = ''  # 'regex', 'token', 'none'


@dataclass
class FileCoverage:
    """Coverage metrics for a single file"""
    file_path: str
    total_patterns: int = 0
    covered_patterns: int = 0
    coverage_percent: float = 0.0
    coverage_weighted: float = 0.0

    # By severity
    critical_total: int = 0
    critical_covered: int = 0
    high_total: int = 0
    high_covered: int = 0
    suggest_total: int = 0
    suggest_covered: int = 0

    # By pattern type
    coverage_by_type: Dict[str, Tuple[int, int]] = field(default_factory=dict)  # type -> (covered, total)


@dataclass
class ProjectCoverage:
    """Coverage metrics for entire project"""
    project_path: str
    files_scanned: int = 0
    total_patterns: int = 0
    covered_patterns: int = 0
    coverage_percent: float = 0.0

    # File-level stats
    files_100_percent: int = 0
    files_80_percent: int = 0
    files_below_80: int = 0

    # By category
    coverage_by_category: Dict[str, Tuple[int, int]] = field(default_factory=dict)  # category -> (covered, total)

    file_coverages: List[FileCoverage] = field(default_factory=list)


class CoverageMatcher:
    """Match code patterns to existing lessons"""

    def __init__(self, platform: Optional[str] = None):
        self.platform = platform
        self.lessons = self._load_lessons()
        self.lesson_patterns = self._build_lesson_patterns()

    def _load_lessons(self) -> List[Dict]:
        """Load all lessons"""
        return load_patterns(platform=self.platform, scope_type=None)

    def _build_lesson_patterns(self) -> Dict[str, Dict]:
        """
        Build lookup dict: lesson_id -> {pattern, tokens, category, severity}
        """
        patterns = {}

        for lesson in self.lessons:
            lesson_id = lesson.get('id', '')
            pattern_str = lesson.get('scan', {}).get('pattern', '')
            category = lesson.get('category', '')
            severity = lesson.get('severity', '')

            if not pattern_str:
                continue

            # Extract tokens for similarity matching
            tokens = _extract_tokens(pattern_str)

            patterns[lesson_id] = {
                'pattern': pattern_str,
                'tokens': tokens,
                'category': category,
                'severity': severity,
                'lesson': lesson
            }

        return patterns

    def match_pattern(self, pattern: CodePattern) -> MatchResult:
        """
        Match a code pattern to existing lessons.

        Returns:
            MatchResult with matched lessons and similarity score
        """
        # Try regex match first (exact)
        for lesson_id, lesson_data in self.lesson_patterns.items():
            lesson_pattern = lesson_data['pattern']

            try:
                if re.search(lesson_pattern, pattern.context):
                    return MatchResult(
                        matched_lessons=[lesson_id],
                        similarity_score=1.0,
                        is_covered=True,
                        match_method='regex'
                    )
            except re.error:
                # Invalid regex, skip
                pass

        # Try token similarity (fuzzy)
        pattern_tokens = _extract_tokens(pattern.context)

        if not pattern_tokens:
            return MatchResult(is_covered=False, match_method='none')

        best_match = None
        best_score = 0.0

        for lesson_id, lesson_data in self.lesson_patterns.items():
            lesson_tokens = lesson_data['tokens']

            similarity = _jaccard_similarity(pattern_tokens, lesson_tokens)

            if similarity > best_score:
                best_score = similarity
                best_match = lesson_id

        # Threshold: 0.5 = covered
        if best_score >= 0.5:
            return MatchResult(
                matched_lessons=[best_match] if best_match else [],
                similarity_score=best_score,
                is_covered=True,
                match_method='token'
            )

        return MatchResult(
            similarity_score=best_score,
            is_covered=False,
            match_method='none'
        )

    def calculate_file_coverage(self, inventory: FileInventory) -> FileCoverage:
        """
        Calculate coverage metrics for a file.

        Returns:
            FileCoverage with detailed metrics
        """
        coverage = FileCoverage(file_path=inventory.file_path)

        if not inventory.patterns:
            return coverage

        coverage.total_patterns = inventory.total_patterns

        # Track by severity
        severity_counts = {'CRITICAL': [0, 0], 'HIGH': [0, 0], 'SUGGEST': [0, 0]}

        # Track by pattern type
        type_counts = {}

        for pattern in inventory.patterns:
            # Match to lessons
            match = self.match_pattern(pattern)

            # Update severity counts
            severity = pattern.severity
            if severity in severity_counts:
                severity_counts[severity][1] += 1  # total
                if match.is_covered:
                    severity_counts[severity][0] += 1  # covered

            # Update type counts
            ptype = pattern.pattern_type
            if ptype not in type_counts:
                type_counts[ptype] = [0, 0]
            type_counts[ptype][1] += 1
            if match.is_covered:
                type_counts[ptype][0] += 1

            # Update overall
            if match.is_covered:
                coverage.covered_patterns += 1

        # Calculate percentages
        if coverage.total_patterns > 0:
            coverage.coverage_percent = (coverage.covered_patterns / coverage.total_patterns) * 100

        # Weighted coverage (CRITICAL=50%, HIGH=30%, SUGGEST=20%)
        critical_cov, critical_tot = severity_counts['CRITICAL']
        high_cov, high_tot = severity_counts['HIGH']
        suggest_cov, suggest_tot = severity_counts['SUGGEST']

        coverage.critical_total = critical_tot
        coverage.critical_covered = critical_cov
        coverage.high_total = high_tot
        coverage.high_covered = high_cov
        coverage.suggest_total = suggest_tot
        coverage.suggest_covered = suggest_cov

        weighted = 0.0
        if critical_tot > 0:
            weighted += (critical_cov / critical_tot) * 0.5
        if high_tot > 0:
            weighted += (high_cov / high_tot) * 0.3
        if suggest_tot > 0:
            weighted += (suggest_cov / suggest_tot) * 0.2

        coverage.coverage_weighted = weighted * 100

        # Store by-type breakdown
        coverage.coverage_by_type = {k: tuple(v) for k, v in type_counts.items()}

        return coverage

    def calculate_project_coverage(self, file_coverages: List[FileCoverage], project_path: str) -> ProjectCoverage:
        """
        Calculate project-level coverage from file coverages.

        Returns:
            ProjectCoverage with aggregated metrics
        """
        project = ProjectCoverage(project_path=project_path)

        if not file_coverages:
            return project

        project.files_scanned = len(file_coverages)

        # Aggregate totals
        for fc in file_coverages:
            project.total_patterns += fc.total_patterns
            project.covered_patterns += fc.covered_patterns

            # Count files by coverage tier
            if fc.coverage_percent >= 100:
                project.files_100_percent += 1
            elif fc.coverage_percent >= 80:
                project.files_80_percent += 1
            else:
                project.files_below_80 += 1

        # Calculate overall coverage
        if project.total_patterns > 0:
            project.coverage_percent = (project.covered_patterns / project.total_patterns) * 100

        project.file_coverages = file_coverages

        return project


def calculate_coverage(inventory: FileInventory, platform: Optional[str] = None) -> FileCoverage:
    """
    Convenience function to calculate coverage for a file.

    Args:
        inventory: FileInventory from inventory.py
        platform: 'wp' or 'nextjs' (optional)

    Returns:
        FileCoverage with metrics
    """
    matcher = CoverageMatcher(platform=platform)
    return matcher.calculate_file_coverage(inventory)


if __name__ == '__main__':
    import sys
    from .inventory import extract_inventory

    if len(sys.argv) < 2:
        print("Usage: python coverage.py <file_path>")
        sys.exit(1)

    file_path = sys.argv[1]

    # Extract inventory
    print(f"Extracting patterns from {file_path}...")
    inventory = extract_inventory(file_path)

    # Calculate coverage
    print(f"Matching patterns to lessons...")
    coverage = calculate_coverage(inventory)

    # Print report
    print()
    print(f"Coverage Report: {coverage.file_path}")
    print(f"Total patterns: {coverage.total_patterns}")
    print(f"Covered: {coverage.covered_patterns} ({coverage.coverage_percent:.1f}%)")
    print(f"Weighted: {coverage.coverage_weighted:.1f}%")
    print()

    print("By Severity:")
    print(f"  CRITICAL: {coverage.critical_covered}/{coverage.critical_total} ({coverage.critical_covered/coverage.critical_total*100 if coverage.critical_total > 0 else 0:.1f}%)")
    print(f"  HIGH: {coverage.high_covered}/{coverage.high_total} ({coverage.high_covered/coverage.high_total*100 if coverage.high_total > 0 else 0:.1f}%)")
    print(f"  SUGGEST: {coverage.suggest_covered}/{coverage.suggest_total} ({coverage.suggest_covered/coverage.suggest_total*100 if coverage.suggest_total > 0 else 0:.1f}%)")
    print()

    if coverage.coverage_by_type:
        print("By Pattern Type:")
        for ptype, (covered, total) in sorted(coverage.coverage_by_type.items()):
            pct = (covered / total * 100) if total > 0 else 0
            print(f"  {ptype}: {covered}/{total} ({pct:.1f}%)")
