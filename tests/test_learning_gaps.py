"""Unit tests for Gap Detector"""

import pytest
from pathlib import Path

from learning.gaps import (
    GapDetector,
    detect_gaps,
    CoverageGap,
    GapReport
)
from learning.inventory import CodePattern, FileInventory


@pytest.fixture
def sample_inventory_with_gaps():
    """Create inventory with patterns that should trigger gaps"""
    inventory = FileInventory(file_path='/test.php', language='php')

    # Patterns likely to be gaps (uncovered)
    patterns = [
        # API call without error handling
        CodePattern(
            pattern_type='function_call',
            pattern_name='wp_remote_post',
            context='$response = wp_remote_post($url, $data);',
            line=10,
            severity='CRITICAL',
            file_path='/test.php',
            language='php'
        ),
        # Direct superglobal access
        CodePattern(
            pattern_type='security_op',
            pattern_name='$_POST',
            context='$value = $_POST["key"];',
            line=20,
            severity='CRITICAL',
            file_path='/test.php',
            language='php'
        ),
        # Unprepared DB query
        CodePattern(
            pattern_type='db_op',
            pattern_name='$wpdb->query',
            context='$wpdb->query("SELECT * FROM table WHERE id = $id");',
            line=30,
            severity='HIGH',
            file_path='/test.php',
            language='php'
        ),
    ]

    for p in patterns:
        inventory.add_pattern(p)

    return inventory


class TestGapDetector:
    """Test GapDetector class"""

    def test_init(self):
        """Test detector initialization"""
        detector = GapDetector(platform='wp')
        assert detector.matcher is not None

    def test_detect_gaps(self, sample_inventory_with_gaps):
        """Test gap detection"""
        detector = GapDetector(platform='wp')
        report = detector.detect_gaps(sample_inventory_with_gaps)

        assert isinstance(report, GapReport)
        assert report.file_path == '/test.php'
        assert report.total_gaps >= 0
        assert len(report.gaps) == report.total_gaps

    def test_gap_severity_counts(self, sample_inventory_with_gaps):
        """Test gap severity breakdown"""
        detector = GapDetector(platform='wp')
        report = detector.detect_gaps(sample_inventory_with_gaps)

        # Check counts add up
        assert report.total_gaps == (
            report.critical_gaps + report.high_gaps + report.suggest_gaps
        )

    def test_infer_gap_type_api(self):
        """Test gap type inference for API calls"""
        detector = GapDetector(platform='wp')

        pattern = CodePattern(
            pattern_type='function_call',
            pattern_name='wp_remote_post',
            context='wp_remote_post($url)',
            line=10,
            severity='CRITICAL',
            file_path='/test.php',
            language='php'
        )

        gap_type = detector._infer_gap_type(pattern)
        assert gap_type == 'uncovered_api'

    def test_infer_gap_type_security(self):
        """Test gap type inference for security ops"""
        detector = GapDetector(platform='wp')

        pattern = CodePattern(
            pattern_type='security_op',
            pattern_name='$_POST',
            context='$_POST["key"]',
            line=10,
            severity='CRITICAL',
            file_path='/test.php',
            language='php'
        )

        gap_type = detector._infer_gap_type(pattern)
        assert gap_type == 'uncovered_security'

    def test_infer_gap_type_db(self):
        """Test gap type inference for DB ops"""
        detector = GapDetector(platform='wp')

        pattern = CodePattern(
            pattern_type='db_op',
            pattern_name='$wpdb->query',
            context='$wpdb->query("SELECT")',
            line=10,
            severity='HIGH',
            file_path='/test.php',
            language='php'
        )

        gap_type = detector._infer_gap_type(pattern)
        assert gap_type == 'uncovered_db'

    def test_infer_gap_severity(self):
        """Test gap severity inference"""
        detector = GapDetector(platform='wp')

        # API gap = CRITICAL
        pattern_api = CodePattern(
            pattern_type='function_call',
            pattern_name='fetch',
            context='fetch(url)',
            line=10,
            severity='CRITICAL',
            file_path='/test.js',
            language='javascript'
        )
        severity = detector._infer_gap_severity(pattern_api, 'uncovered_api')
        assert severity == 'CRITICAL'

        # DB gap = HIGH
        pattern_db = CodePattern(
            pattern_type='db_op',
            pattern_name='$wpdb->query',
            context='$wpdb->query()',
            line=10,
            severity='HIGH',
            file_path='/test.php',
            language='php'
        )
        severity = detector._infer_gap_severity(pattern_db, 'uncovered_db')
        assert severity == 'HIGH'

    def test_calculate_confidence(self):
        """Test confidence calculation"""
        detector = GapDetector(platform='wp')

        from learning.coverage import MatchResult

        pattern = CodePattern(
            pattern_type='security_op',
            pattern_name='wp_remote_post',
            context='wp_remote_post($url)',
            line=10,
            severity='CRITICAL',
            file_path='/test.php',
            language='php'
        )

        # High-risk pattern with low similarity = high confidence
        match = MatchResult(similarity_score=0.1, is_covered=False, match_method='none')
        confidence = detector._calculate_confidence(pattern, match, 'uncovered_api')

        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.5  # Should be high confidence

    def test_generate_lesson_suggestion(self):
        """Test lesson suggestion generation"""
        detector = GapDetector(platform='wp')

        pattern = CodePattern(
            pattern_type='function_call',
            pattern_name='wp_remote_post',
            context='$response = wp_remote_post($url, $data);',
            line=10,
            severity='CRITICAL',
            file_path='/test.php',
            language='php'
        )

        suggestion = detector._generate_lesson_suggestion(pattern, 'uncovered_api')

        assert isinstance(suggestion, dict)
        assert 'title' in suggestion
        assert 'category' in suggestion
        assert 'severity' in suggestion
        assert 'pattern' in suggestion
        assert 'why' in suggestion
        assert 'bad_code' in suggestion
        assert 'good_code' in suggestion
        assert 'scope' in suggestion
        assert 'platform' in suggestion
        assert 'tags' in suggestion

        # Check content
        assert 'wp_remote_post' in suggestion['title']
        assert suggestion['severity'] == 'CRITICAL'
        assert suggestion['platform'] == 'wp'

    def test_empty_inventory(self):
        """Test gap detection on empty inventory"""
        inventory = FileInventory(file_path='/empty.php', language='php')
        detector = GapDetector(platform='wp')
        report = detector.detect_gaps(inventory)

        assert report.total_gaps == 0
        assert report.critical_gaps == 0
        assert report.high_gaps == 0
        assert report.suggest_gaps == 0
        assert len(report.gaps) == 0


class TestConvenienceFunction:
    """Test convenience function"""

    def test_detect_gaps(self, sample_inventory_with_gaps):
        """Test detect_gaps convenience function"""
        report = detect_gaps(sample_inventory_with_gaps, platform='wp')

        assert isinstance(report, GapReport)
        assert report.file_path == '/test.php'


class TestCoverageGap:
    """Test CoverageGap dataclass"""

    def test_coverage_gap_creation(self):
        """Test creating CoverageGap instance"""
        pattern = CodePattern(
            pattern_type='function_call',
            pattern_name='wp_remote_post',
            context='wp_remote_post($url)',
            line=10,
            severity='CRITICAL',
            file_path='/test.php',
            language='php'
        )

        gap = CoverageGap(
            pattern=pattern,
            gap_type='uncovered_api',
            severity='CRITICAL',
            confidence=0.85,
            suggested_lesson={
                'title': 'Missing error handling for wp_remote_post',
                'category': 'php-error-handling',
                'severity': 'CRITICAL',
                'pattern': 'wp_remote_post',
                'why': 'API calls can fail',
                'bad_code': 'wp_remote_post($url)',
                'good_code': 'if (is_wp_error($response)) {...}',
                'scope': '**/*.php',
                'platform': 'wp',
                'tags': ['api', 'error-handling']
            }
        )

        assert gap.pattern == pattern
        assert gap.gap_type == 'uncovered_api'
        assert gap.severity == 'CRITICAL'
        assert gap.confidence == 0.85
        assert gap.suggested_lesson['title'] == 'Missing error handling for wp_remote_post'


class TestGapReport:
    """Test GapReport dataclass"""

    def test_gap_report_creation(self):
        """Test creating GapReport instance"""
        report = GapReport(
            file_path='/test.php',
            total_gaps=10,
            critical_gaps=3,
            high_gaps=5,
            suggest_gaps=2
        )

        assert report.file_path == '/test.php'
        assert report.total_gaps == 10
        assert report.critical_gaps == 3
        assert report.high_gaps == 5
        assert report.suggest_gaps == 2
        assert len(report.gaps) == 0  # Empty by default


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
