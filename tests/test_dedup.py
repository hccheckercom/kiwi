"""Unit tests for lesson deduplication"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from learning.dedup import (
    find_duplicate_lessons,
    calculate_lesson_similarity,
    merge_lessons,
    _string_similarity,
    _token_overlap_similarity
)


class TestStringSimilarity:
    """Test Levenshtein-based string similarity"""

    def test_identical_strings(self):
        assert _string_similarity('test', 'test') == 1.0

    def test_completely_different(self):
        similarity = _string_similarity('abc', 'xyz')
        assert similarity < 0.3

    def test_similar_strings(self):
        similarity = _string_similarity('hardcoded password', 'hardcoded_password')
        assert similarity > 0.8


class TestTokenOverlapSimilarity:
    """Test Jaccard similarity of tokens"""

    def test_identical_tokens(self):
        assert _token_overlap_similarity('test example', 'test example') == 1.0

    def test_no_overlap(self):
        assert _token_overlap_similarity('abc def', 'xyz uvw') == 0.0

    def test_partial_overlap(self):
        similarity = _token_overlap_similarity('test example code', 'test sample code')
        assert 0.5 < similarity < 0.8  # 2/4 tokens match

    def test_case_insensitive(self):
        assert _token_overlap_similarity('Test Example', 'test example') == 1.0


class TestCalculateLessonSimilarity:
    """Test multi-factor lesson similarity"""

    def test_identical_lessons(self):
        lesson_a = {
            'scan': {'pattern': 'test.*pattern'},
            'title': 'Test Pattern',
            'category': 'security'
        }
        lesson_b = {
            'scan': {'pattern': 'test.*pattern'},
            'title': 'Test Pattern',
            'category': 'security'
        }

        similarity = calculate_lesson_similarity(lesson_a, lesson_b)
        assert similarity == 1.0

    def test_different_categories_lower_score(self):
        lesson_a = {
            'scan': {'pattern': 'test.*pattern'},
            'title': 'Test Pattern',
            'category': 'security'
        }
        lesson_b = {
            'scan': {'pattern': 'test.*pattern'},
            'title': 'Test Pattern',
            'category': 'performance'
        }

        similarity = calculate_lesson_similarity(lesson_a, lesson_b)
        assert similarity < 1.0  # Category mismatch reduces score by 20%

    def test_similar_patterns_high_score(self):
        lesson_a = {
            'scan': {'pattern': 'hardcoded.*password'},
            'title': 'Hardcoded Password',
            'category': 'security'
        }
        lesson_b = {
            'scan': {'pattern': 'hardcoded.*secret'},
            'title': 'Hardcoded Secret',
            'category': 'security'
        }

        similarity = calculate_lesson_similarity(lesson_a, lesson_b)
        assert similarity > 0.7  # Similar patterns + same category


class TestFindDuplicateLessons:
    """Test duplicate lesson detection"""

    @patch('learning.dedup.load_patterns')
    def test_finds_duplicate_pair(self, mock_load):
        mock_load.return_value = [
            {
                'id': 'LES-001',
                'scan': {'pattern': 'test.*pattern'},
                'title': 'Test Pattern',
                'category': 'security'
            },
            {
                'id': 'LES-002',
                'scan': {'pattern': 'test.*pattern'},
                'title': 'Test Pattern',
                'category': 'security'
            }
        ]

        clusters = find_duplicate_lessons(threshold=0.9)

        assert len(clusters) == 1
        assert len(clusters[0]) == 2
        assert 'LES-001' in clusters[0]
        assert 'LES-002' in clusters[0]

    @patch('learning.dedup.load_patterns')
    def test_no_duplicates_returns_empty(self, mock_load):
        mock_load.return_value = [
            {
                'id': 'LES-001',
                'scan': {'pattern': 'pattern_a'},
                'title': 'Pattern A',
                'category': 'security'
            },
            {
                'id': 'LES-002',
                'scan': {'pattern': 'pattern_b'},
                'title': 'Pattern B',
                'category': 'performance'
            }
        ]

        clusters = find_duplicate_lessons(threshold=0.9)

        assert len(clusters) == 0

    @patch('learning.dedup.load_patterns')
    def test_finds_cluster_of_three(self, mock_load):
        mock_load.return_value = [
            {
                'id': 'LES-001',
                'scan': {'pattern': 'test'},
                'title': 'Test',
                'category': 'security'
            },
            {
                'id': 'LES-002',
                'scan': {'pattern': 'test'},
                'title': 'Test',
                'category': 'security'
            },
            {
                'id': 'LES-003',
                'scan': {'pattern': 'test'},
                'title': 'Test',
                'category': 'security'
            }
        ]

        clusters = find_duplicate_lessons(threshold=0.9)

        assert len(clusters) == 1
        assert len(clusters[0]) == 3


class TestMergeLessons:
    """Test lesson merging logic"""

    @patch('learning.dedup._load_lesson')
    @patch('learning.dedup._select_primary_lesson')
    @patch('learning.dedup._update_primary_lesson')
    @patch('learning.dedup._archive_old_lessons')
    @patch('learning.dedup.get_lesson_confidence')
    def test_merges_two_lessons(
        self, mock_confidence, mock_archive, mock_update, mock_select, mock_load
    ):
        lesson_1 = {
            'lesson_id': 'LES-001',
            'pattern': 'pattern_a',
            'title': 'Title A',
            'category': 'security',
            'severity': 'CRITICAL',
            'scope': '**/*.php',
            'bad_example': 'bad code 1',
            'good_example': 'good code 1'
        }

        lesson_2 = {
            'lesson_id': 'LES-002',
            'pattern': 'pattern_b',
            'title': 'Title B',
            'category': 'security',
            'severity': 'CRITICAL',
            'scope': '**/*.php',
            'bad_example': 'bad code 2',
            'good_example': 'good code 2'
        }

        mock_load.side_effect = [lesson_1, lesson_2]
        mock_select.return_value = lesson_1
        mock_confidence.return_value = {'confidence': 0.9}

        result = merge_lessons(['LES-001', 'LES-002'], dry_run=False)

        assert result is not None
        assert result['lesson_id'] == 'LES-001'
        assert '(?:pattern_a|pattern_b)' in result['pattern'] or '(?:pattern_b|pattern_a)' in result['pattern']
        assert 'LES-002' in result['merged_from']
        mock_update.assert_called_once()
        mock_archive.assert_called_once_with(['LES-002'])

    @patch('learning.dedup._load_lesson')
    def test_dry_run_does_not_modify(self, mock_load):
        lesson_1 = {
            'lesson_id': 'LES-001',
            'pattern': 'pattern_a',
            'title': 'Title A',
            'category': 'security',
            'severity': 'CRITICAL',
            'scope': '**/*.php',
            'bad_example': 'bad',
            'good_example': 'good'
        }

        mock_load.return_value = lesson_1

        with patch('learning.dedup._update_primary_lesson') as mock_update:
            with patch('learning.dedup._archive_old_lessons') as mock_archive:
                result = merge_lessons(['LES-001', 'LES-002'], dry_run=True)

                assert result is not None
                mock_update.assert_not_called()
                mock_archive.assert_not_called()

    def test_single_lesson_returns_none(self):
        result = merge_lessons(['LES-001'])
        assert result is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])