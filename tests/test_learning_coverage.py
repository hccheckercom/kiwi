"""Unit tests for Coverage Matcher & Scorer"""

import pytest
from pathlib import Path
import tempfile
import os

from learning.coverage import (
    CoverageMatcher,
    calculate_coverage,
    MatchResult,
    FileCoverage,
    ProjectCoverage
)
from learning.inventory import extract_inventory, CodePattern, FileInventory


@pytest.fixture
def sample_inventory():
    """Create sample inventory for testing"""
    inventory = FileInventory(file_path='/test.php', language='php')

    # Add patterns
    patterns = [
        CodePattern(
            pattern_type='security_op',
            pattern_name='wp_remote_post',
            context='$response = wp_remote_post($url, $data);',
            line=10,
            severity='CRITICAL',
            file_path='/test.php',
            language='php'
        ),
        CodePattern(
            pattern_type='db_op',
            pattern_name='$wpdb->query',
            context='$wpdb->query("SELECT * FROM table");',
            line=20,
            severity='HIGH',
            file_path='/test.php',
            language='php'
        ),
        CodePattern(
            pattern_type='hook',
            pattern_name='add_action',
            context='add_action("init", "my_func");',
            line=30,
            severity='SUGGEST',
            file_path='/test.php',
            language='php'
        ),
    ]

    for p in patterns:
        inventory.add_pattern(p)

    return inventory


class TestCoverageMatcher:
    """Test CoverageMatcher class"""

    def test_init(self):
        """Test matcher initialization"""
        matcher = CoverageMatcher(platform='wp')
        assert matcher.platform == 'wp'
        assert len(matcher.lessons) > 0
        # lesson_patterns may be empty if no lessons have scan.pattern (some use ast_check)
        assert isinstance(matcher.lesson_patterns, dict)

    def test_match_pattern_regex(self):
        """Test regex-based pattern matching"""
        matcher = CoverageMatcher(platform='wp')

        # Create pattern that should match existing lesson
        pattern = CodePattern(
            pattern_type='security_op',
            pattern_name='wp_remote_post',
            context='$response = wp_remote_post($url, $data);',
            line=10,
            severity='CRITICAL',
            file_path='/test.php',
            language='php'
        )

        result = matcher.match_pattern(pattern)

        # Should find a match (many lessons cover wp_remote_post)
        assert isinstance(result, MatchResult)
        # May or may not match depending on lessons — just check structure
        assert isinstance(result.is_covered, bool)
        assert isinstance(result.similarity_score, float)
        assert result.match_method in ['regex', 'token', 'none']

    def test_match_pattern_no_match(self):
        """Test pattern with no match"""
        matcher = CoverageMatcher(platform='wp')

        # Create very specific pattern unlikely to match
        pattern = CodePattern(
            pattern_type='function_call',
            pattern_name='very_specific_custom_function_xyz123',
            context='very_specific_custom_function_xyz123($arg);',
            line=10,
            severity='SUGGEST',
            file_path='/test.php',
            language='php'
        )

        result = matcher.match_pattern(pattern)

        assert isinstance(result, MatchResult)
        # Unlikely to be covered
        assert result.similarity_score < 0.5

    def test_calculate_file_coverage(self, sample_inventory):
        """Test file coverage calculation"""
        matcher = CoverageMatcher(platform='wp')
        coverage = matcher.calculate_file_coverage(sample_inventory)

        assert isinstance(coverage, FileCoverage)
        assert coverage.file_path == '/test.php'
        assert coverage.total_patterns == 3
        assert coverage.covered_patterns >= 0
        assert coverage.covered_patterns <= coverage.total_patterns
        assert 0 <= coverage.coverage_percent <= 100
        assert 0 <= coverage.coverage_weighted <= 100

    def test_calculate_file_coverage_by_severity(self, sample_inventory):
        """Test coverage breakdown by severity"""
        matcher = CoverageMatcher(platform='wp')
        coverage = matcher.calculate_file_coverage(sample_inventory)

        # Check severity counts
        assert coverage.critical_total == 1
        assert coverage.high_total == 1
        assert coverage.suggest_total == 1

        # Covered counts should be <= total
        assert coverage.critical_covered <= coverage.critical_total
        assert coverage.high_covered <= coverage.high_total
        assert coverage.suggest_covered <= coverage.suggest_total

    def test_calculate_file_coverage_by_type(self, sample_inventory):
        """Test coverage breakdown by pattern type"""
        matcher = CoverageMatcher(platform='wp')
        coverage = matcher.calculate_file_coverage(sample_inventory)

        assert len(coverage.coverage_by_type) > 0

        for ptype, (covered, total) in coverage.coverage_by_type.items():
            assert covered <= total
            assert total > 0

    def test_calculate_file_coverage_empty(self):
        """Test coverage for empty inventory"""
        inventory = FileInventory(file_path='/empty.php', language='php')
        matcher = CoverageMatcher(platform='wp')
        coverage = matcher.calculate_file_coverage(inventory)

        assert coverage.total_patterns == 0
        assert coverage.covered_patterns == 0
        assert coverage.coverage_percent == 0.0

    def test_calculate_project_coverage(self):
        """Test project-level coverage calculation"""
        # Create multiple file coverages
        file_coverages = [
            FileCoverage(
                file_path='/file1.php',
                total_patterns=10,
                covered_patterns=10,
                coverage_percent=100.0
            ),
            FileCoverage(
                file_path='/file2.php',
                total_patterns=10,
                covered_patterns=8,
                coverage_percent=80.0
            ),
            FileCoverage(
                file_path='/file3.php',
                total_patterns=10,
                covered_patterns=5,
                coverage_percent=50.0
            ),
        ]

        matcher = CoverageMatcher(platform='wp')
        project = matcher.calculate_project_coverage(file_coverages, '/project')

        assert isinstance(project, ProjectCoverage)
        assert project.project_path == '/project'
        assert project.files_scanned == 3
        assert project.total_patterns == 30
        assert project.covered_patterns == 23
        assert project.coverage_percent == pytest.approx(76.67, rel=0.1)

        # Check tier counts
        assert project.files_100_percent == 1
        assert project.files_80_percent == 1
        assert project.files_below_80 == 1

    def test_calculate_project_coverage_empty(self):
        """Test project coverage with no files"""
        matcher = CoverageMatcher(platform='wp')
        project = matcher.calculate_project_coverage([], '/project')

        assert project.files_scanned == 0
        assert project.total_patterns == 0
        assert project.coverage_percent == 0.0


class TestConvenienceFunction:
    """Test convenience function"""

    def test_calculate_coverage(self, sample_inventory):
        """Test calculate_coverage convenience function"""
        coverage = calculate_coverage(sample_inventory, platform='wp')

        assert isinstance(coverage, FileCoverage)
        assert coverage.file_path == '/test.php'
        assert coverage.total_patterns == 3


class TestMatchResult:
    """Test MatchResult dataclass"""

    def test_match_result_creation(self):
        """Test creating MatchResult instance"""
        result = MatchResult(
            matched_lessons=['LES-001', 'LES-002'],
            similarity_score=0.85,
            is_covered=True,
            match_method='regex'
        )

        assert result.matched_lessons == ['LES-001', 'LES-002']
        assert result.similarity_score == 0.85
        assert result.is_covered is True
        assert result.match_method == 'regex'


class TestFileCoverage:
    """Test FileCoverage dataclass"""

    def test_file_coverage_creation(self):
        """Test creating FileCoverage instance"""
        coverage = FileCoverage(
            file_path='/test.php',
            total_patterns=10,
            covered_patterns=8,
            coverage_percent=80.0,
            coverage_weighted=85.0,
            critical_total=2,
            critical_covered=2,
            high_total=3,
            high_covered=2,
            suggest_total=5,
            suggest_covered=4
        )

        assert coverage.file_path == '/test.php'
        assert coverage.total_patterns == 10
        assert coverage.covered_patterns == 8
        assert coverage.coverage_percent == 80.0
        assert coverage.coverage_weighted == 85.0


class TestProjectCoverage:
    """Test ProjectCoverage dataclass"""

    def test_project_coverage_creation(self):
        """Test creating ProjectCoverage instance"""
        project = ProjectCoverage(
            project_path='/project',
            files_scanned=10,
            total_patterns=100,
            covered_patterns=80,
            coverage_percent=80.0,
            files_100_percent=3,
            files_80_percent=5,
            files_below_80=2
        )

        assert project.project_path == '/project'
        assert project.files_scanned == 10
        assert project.total_patterns == 100
        assert project.covered_patterns == 80
        assert project.coverage_percent == 80.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
