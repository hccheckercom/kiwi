"""Unit tests for pattern refinement engine"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from learning.refiner import (
    refine_noisy_pattern,
    extract_fp_tokens,
    add_negative_lookahead,
    test_pattern_accuracy,
    update_lesson_pattern
)


class TestExtractFPTokens:
    """Test common token extraction from false positives"""

    def test_extract_common_tokens_50_percent_threshold(self):
        fps = [
            {'match_text': 'test_function_example'},
            {'match_text': 'test_another_example'},
            {'match_text': 'test_third_case'},
        ]

        tokens = extract_fp_tokens(fps)

        assert 'test' in tokens
        assert 'example' not in tokens  # Only in 2/3 = 66%, but need exact match

    def test_extract_tokens_filters_short_tokens(self):
        fps = [
            {'match_text': 'a b test example'},
            {'match_text': 'a b test sample'},
        ]

        tokens = extract_fp_tokens(fps)

        assert 'a' not in tokens  # Too short (< 3 chars)
        assert 'b' not in tokens
        assert 'test' in tokens

    def test_empty_fps_returns_empty_set(self):
        tokens = extract_fp_tokens([])
        assert tokens == set()


class TestAddNegativeLookahead:
    """Test negative lookahead pattern generation"""

    def test_add_single_token(self):
        pattern = r'hardcoded.*password'
        exclude = {'test'}

        result = add_negative_lookahead(pattern, exclude)

        assert result == r'(?!.*(test))hardcoded.*password'

    def test_add_multiple_tokens(self):
        pattern = r'hardcoded.*password'
        exclude = {'test', 'example', 'demo'}

        result = add_negative_lookahead(pattern, exclude)

        assert '(?!.*(test|example|demo))' in result or '(?!.*(test|demo|example))' in result
        assert 'hardcoded.*password' in result

    def test_empty_exclude_returns_original(self):
        pattern = r'hardcoded.*password'

        result = add_negative_lookahead(pattern, set())

        assert result == pattern

    def test_escapes_special_regex_chars(self):
        pattern = r'test'
        exclude = {'$_GET', 'file.php'}

        result = add_negative_lookahead(pattern, exclude)

        assert r'\$_GET' in result
        assert r'file\.php' in result


class TestPatternAccuracy:
    """Test pattern accuracy calculation on history"""

    @patch('learning.refiner.get_connection')
    def test_accuracy_with_perfect_pattern(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'match_text': 'real violation', 'file': 'a.php', 'line': 10},
            {'match_text': 'another real', 'file': 'b.php', 'line': 20},
        ]
        mock_conn.return_value.execute.return_value = mock_cursor
        mock_conn.return_value.close = Mock()

        with patch('learning.refiner._get_false_positives', return_value=[]):
            accuracy = test_pattern_accuracy(r'real', 'LES-001')

        assert accuracy == 1.0

    @patch('learning.refiner.get_connection')
    def test_accuracy_with_some_fps(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'match_text': 'real violation', 'file': 'a.php', 'line': 10},
            {'match_text': 'false positive', 'file': 'b.php', 'line': 20},
        ]
        mock_conn.return_value.execute.return_value = mock_cursor
        mock_conn.return_value.close = Mock()

        fps = [{'file': 'b.php', 'line': 20}]

        with patch('learning.refiner._get_false_positives', return_value=fps):
            accuracy = test_pattern_accuracy(r'violation|positive', 'LES-001')

        assert accuracy == 1.0  # Both matched correctly

    @patch('learning.refiner.get_connection')
    def test_invalid_regex_returns_zero(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.return_value.execute.return_value = mock_cursor
        mock_conn.return_value.close = Mock()

        accuracy = test_pattern_accuracy(r'[invalid(regex', 'LES-001')

        assert accuracy == 0.0


class TestRefineNoisyPattern:
    """Test end-to-end pattern refinement"""

    @patch('learning.refiner.get_lesson_confidence')
    @patch('learning.refiner._get_false_positives')
    @patch('learning.refiner._get_lesson_pattern')
    @patch('learning.refiner.test_pattern_accuracy')
    @patch('learning.refiner.update_lesson_pattern')
    def test_refines_pattern_when_fp_rate_high(
        self, mock_update, mock_test, mock_get_pattern, mock_get_fps, mock_confidence
    ):
        mock_confidence.return_value = {
            'total_hits': 10,
            'false_positive_count': 4,
            'confidence': 0.6
        }

        mock_get_fps.return_value = [
            {'match_text': 'test_example_1'},
            {'match_text': 'test_example_2'},
            {'match_text': 'test_example_3'},
        ]

        mock_get_pattern.return_value = r'hardcoded.*password'
        mock_test.side_effect = [0.6, 0.85]  # Before, after

        result = refine_noisy_pattern('LES-001', fp_threshold=0.3)

        assert result is not None
        assert mock_update.called

    @patch('learning.refiner.get_lesson_confidence')
    def test_skips_refinement_when_fp_rate_low(self, mock_confidence):
        mock_confidence.return_value = {
            'total_hits': 10,
            'false_positive_count': 1,
            'confidence': 0.9
        }

        result = refine_noisy_pattern('LES-001', fp_threshold=0.3)

        assert result is None

    @patch('learning.refiner.get_lesson_confidence')
    @patch('learning.refiner._get_false_positives')
    def test_skips_refinement_with_too_few_fps(self, mock_get_fps, mock_confidence):
        mock_confidence.return_value = {
            'total_hits': 10,
            'false_positive_count': 4,
            'confidence': 0.6
        }

        mock_get_fps.return_value = [
            {'match_text': 'test_1'},
            {'match_text': 'test_2'},
        ]  # Only 2 FPs, need 3+

        result = refine_noisy_pattern('LES-001', fp_threshold=0.3)

        assert result is None


class TestUpdateLessonPattern:
    """Test lesson file update"""

    @patch('learning.refiner._find_lesson_file')
    @patch('learning.refiner._get_lesson_pattern')
    @patch('learning.refiner._record_refinement')
    def test_updates_lesson_file(self, mock_record, mock_get_pattern, mock_find):
        mock_file = MagicMock()
        mock_file.read_text.return_value = """---
severity: CRITICAL
pattern: old_pattern
---
Content"""
        mock_file.write_text = Mock()
        mock_find.return_value = mock_file
        mock_get_pattern.return_value = 'old_pattern'

        update_lesson_pattern('LES-001', 'new_pattern', 'Test reason')

        mock_file.write_text.assert_called_once()
        written_content = mock_file.write_text.call_args[0][0]
        assert 'pattern: new_pattern' in written_content
        assert 'old_pattern' not in written_content

    @patch('learning.refiner._find_lesson_file')
    def test_handles_missing_lesson_file(self, mock_find):
        mock_find.return_value = None

        # Should not raise exception
        update_lesson_pattern('LES-999', 'new_pattern', 'Test')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])