"""R6 — Comprehensive QA: edge cases, integration, error handling, concurrency."""

import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from dataclasses import asdict

import pytest


@pytest.fixture
def r6_db():
    schema_path = Path(__file__).parent / "schema.sql"
    conn = sqlite3.connect(":memory:")
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.commit()
    yield conn
    conn.close()


# ============================================================
# QA-1: Edge Cases in Level Determination
# ============================================================

class TestLevelEdgeCases:
    def test_exact_boundary_06(self):
        from agent.reasoning.autonomy import determine_output_level
        # 0.6 exactly → skeleton (>= 0.6)
        assert determine_output_level(0.6, 'fix_css') == 'skeleton'

    def test_exact_boundary_085(self):
        from agent.reasoning.autonomy import determine_output_level
        assert determine_output_level(0.85, 'fix_css') == 'draft'

    def test_exact_boundary_095(self):
        from agent.reasoning.autonomy import determine_output_level
        assert determine_output_level(0.95, 'fix_css') == 'ready'

    def test_just_below_06(self):
        from agent.reasoning.autonomy import determine_output_level
        assert determine_output_level(0.599, 'fix_css') == 'brief_only'

    def test_zero_trust(self):
        from agent.reasoning.autonomy import determine_output_level
        assert determine_output_level(0.0, 'home_page') == 'brief_only'

    def test_negative_trust(self):
        from agent.reasoning.autonomy import determine_output_level
        assert determine_output_level(-0.1, 'home_page') == 'brief_only'

    def test_trust_above_1(self):
        from agent.reasoning.autonomy import determine_output_level
        assert determine_output_level(1.5, 'fix_css') == 'ready'

    def test_empty_task_type(self):
        from agent.reasoning.autonomy import determine_output_level
        # Empty string → default penalty 0.02
        assert determine_output_level(0.7, '') == 'skeleton'

    def test_none_task_type_in_content(self, r6_db):
        from agent.reasoning.autonomy import generate_graduated_output
        from agent.reasoning.output import KiwiOutput

        brief = KiwiOutput(
            content={},  # no 'target' key
            trust_score=0.7,
            trust_breakdown={},
        )

        with patch("agent.reasoning.code_drafter._get_conn", return_value=r6_db), \
             patch("agent.reasoning.approval_tracker._get_conn", return_value=r6_db):
            output = generate_graduated_output(brief, 'themes/test')

        # Should not crash, defaults to 'generic'
        assert output.level == 'skeleton'
        assert output.code is not None


# ============================================================
# QA-2: Approval Tracker Demotion Logic
# ============================================================

class TestDemotionLogic:
    def test_ready_demoted_to_draft_when_blocked(self, r6_db):
        """When 'ready' is blocked, should demote to 'draft'."""
        # Insert 5 rejections for 'ready' level
        for i in range(5):
            r6_db.execute(
                "INSERT INTO draft_outcomes (session_id, task_type, level, outcome, changes_made, created_at) "
                "VALUES (?, 'home_page', 'ready', 'rejected', 0, ?)",
                (f's{i}', time.time()),
            )
        r6_db.commit()

        from agent.reasoning.autonomy import generate_graduated_output
        from agent.reasoning.output import KiwiOutput

        brief = KiwiOutput(
            content={'target': 'home_page', 'style_pattern': ''},
            trust_score=0.96,  # Would normally be 'ready'
            trust_breakdown={},
        )

        with patch("agent.reasoning.code_drafter._get_conn", return_value=r6_db), \
             patch("agent.reasoning.approval_tracker._get_conn", return_value=r6_db):
            output = generate_graduated_output(brief, 'themes/test')

        assert output.level == 'draft'

    def test_draft_demoted_to_skeleton_when_blocked(self, r6_db):
        """When 'draft' is blocked, should demote to 'skeleton'."""
        for i in range(5):
            r6_db.execute(
                "INSERT INTO draft_outcomes (session_id, task_type, level, outcome, changes_made, created_at) "
                "VALUES (?, 'cart_page', 'draft', 'rejected', 0, ?)",
                (f's{i}', time.time()),
            )
        r6_db.commit()

        from agent.reasoning.autonomy import generate_graduated_output
        from agent.reasoning.output import KiwiOutput

        brief = KiwiOutput(
            content={'target': 'cart_page', 'style_pattern': ''},
            trust_score=0.9,  # Would normally be 'draft' (0.9 - 0.03 = 0.87)
            trust_breakdown={},
        )

        with patch("agent.reasoning.code_drafter._get_conn", return_value=r6_db), \
             patch("agent.reasoning.approval_tracker._get_conn", return_value=r6_db):
            output = generate_graduated_output(brief, 'themes/test')

        assert output.level == 'skeleton'

    def test_skeleton_never_demoted(self, r6_db):
        """Skeleton level is never checked by should_attempt_level."""
        from agent.reasoning.autonomy import generate_graduated_output
        from agent.reasoning.output import KiwiOutput

        brief = KiwiOutput(
            content={'target': 'home_page', 'style_pattern': ''},
            trust_score=0.7,  # skeleton level
            trust_breakdown={},
        )

        with patch("agent.reasoning.code_drafter._get_conn", return_value=r6_db), \
             patch("agent.reasoning.approval_tracker._get_conn", return_value=r6_db):
            output = generate_graduated_output(brief, 'themes/test')

        assert output.level == 'skeleton'


# ============================================================
# QA-3: Code Quality Guard — Comprehensive
# ============================================================

class TestCodeQualityComprehensive:
    def test_multiline_woocommerce_detection(self):
        from agent.reasoning.code_drafter import check_code_quality
        code = """<?php
if ( ! function_exists( 'wezone_is_active' ) ) return;
$product = wc_get_product( $id );
?>"""
        assert check_code_quality(code) is False

    def test_product_arrow_in_comment_still_blocks(self):
        from agent.reasoning.code_drafter import check_code_quality
        # Even in comments, regex will match — this is intentional (conservative)
        code = """<?php
if ( ! function_exists( 'wezone_is_active' ) ) return;
// $product->name is wrong
?>"""
        assert check_code_quality(code) is False

    def test_bem_in_tailwind_class_not_false_positive(self):
        from agent.reasoning.code_drafter import check_code_quality
        # Tailwind classes like 'md:grid-cols-2' should NOT trigger BEM detection
        code = """<?php
if ( ! function_exists( 'wezone_is_active' ) ) return;
?>
<div class="md:grid-cols-2 py-8">test</div>"""
        assert check_code_quality(code) is True

    def test_double_underscore_in_php_magic_method(self):
        from agent.reasoning.code_drafter import check_code_quality
        # __construct is a PHP magic method, not BEM
        # Pattern is __\w+--\w+ which requires -- after __word
        code = """<?php
if ( ! function_exists( 'wezone_is_active' ) ) return;
class Test { public function __construct() {} }
?>"""
        assert check_code_quality(code) is True

    def test_actual_bem_class(self):
        from agent.reasoning.code_drafter import check_code_quality
        code = """<?php
if ( ! function_exists( 'wezone_is_active' ) ) return;
?>
<div class="__block--modifier">test</div>"""
        assert check_code_quality(code) is False

    def test_empty_code(self):
        from agent.reasoning.code_drafter import check_code_quality
        assert check_code_quality("") is True

    def test_only_html_no_php(self):
        from agent.reasoning.code_drafter import check_code_quality
        code = "<div class='py-8'><p>Hello</p></div>"
        assert check_code_quality(code) is True

    def test_wezone_is_active_in_different_format(self):
        from agent.reasoning.code_drafter import check_code_quality
        # Different spacing/format should still pass
        code = "<?php if(!function_exists('wezone_is_active'))return; ?><div>ok</div>"
        assert check_code_quality(code) is True


# ============================================================
# QA-4: Style Token Swap — Edge Cases
# ============================================================

class TestStyleSwapEdgeCases:
    def test_no_source_style(self):
        from agent.reasoning.code_drafter import _swap_style_tokens
        code = '<div class="rounded-lg py-8">'
        result = _swap_style_tokens(code, {}, {'radius': '2xl'})
        # No source → no swap
        assert result == code

    def test_same_values_no_change(self):
        from agent.reasoning.code_drafter import _swap_style_tokens
        code = '<div class="rounded-lg">'
        result = _swap_style_tokens(code, {'radius': 'lg'}, {'radius': 'lg'})
        assert result == code

    def test_multiple_occurrences_swapped(self):
        from agent.reasoning.code_drafter import _swap_style_tokens
        code = '<div class="rounded-lg"><span class="rounded-lg">'
        result = _swap_style_tokens(code, {'radius': 'lg'}, {'radius': '2xl'})
        assert result.count('rounded-2xl') == 2
        assert 'rounded-lg' not in result

    def test_spacing_swap_needs_trailing_space(self):
        from agent.reasoning.code_drafter import _swap_style_tokens
        # py-8 at end of string (no trailing space) should NOT be swapped
        code = 'class="py-8"'
        result = _swap_style_tokens(code, {'spacing_base': '8'}, {'spacing_base': '10'})
        # The regex requires \s after the number, " is not \s
        assert 'py-8' in result  # unchanged because no trailing whitespace

    def test_spacing_swap_with_trailing_space(self):
        from agent.reasoning.code_drafter import _swap_style_tokens
        code = 'class="py-8 md:py-12"'
        result = _swap_style_tokens(code, {'spacing_base': '8'}, {'spacing_base': '10'})
        assert 'py-10' in result

    def test_unknown_style_key_ignored(self):
        from agent.reasoning.code_drafter import _swap_style_tokens
        code = '<div class="text-lg">'
        result = _swap_style_tokens(code, {'font_size': 'lg'}, {'font_size': 'xl'})
        # Unknown key → no swap logic
        assert result == code


# ============================================================
# QA-5: Integration — kiwi_reason with include_code
# ============================================================

class TestKiwiReasonIntegration:
    def test_include_code_false_no_graduated(self, r6_db):
        """include_code=False should not generate graduated output."""
        from agent.reasoning.output import KiwiOutput

        with patch("agent.reasoning.assemble_context") as mock_ctx, \
             patch("agent.reasoning.compute_trust_score", return_value=(0.8, {})), \
             patch("agent.reasoning.session_logger._get_conn", return_value=r6_db), \
             patch("agent.reasoning.session_logger.get_session_id", return_value="test"), \
             patch("agent.reasoning.session_logger.save_brief_output"):

            mock_ctx.return_value = MagicMock(
                task_type='home_page',
                theme={'name': 'test'},
                spec={'found': True},
                bindings={'wz_hero': True},
                files_needed=['a.php', 'b.php'],
                reference_pages=['ref1'],
                lessons=['L1'],
            )

            from agent.reasoning import kiwi_reason
            output = kiwi_reason("test task", "themes/test", include_code=False)

        assert output.graduated is None

    def test_include_code_true_low_trust_no_graduated(self, r6_db):
        """include_code=True but trust < 0.6 should not generate graduated output."""
        with patch("agent.reasoning.assemble_context") as mock_ctx, \
             patch("agent.reasoning.compute_trust_score", return_value=(0.4, {})), \
             patch("agent.reasoning.session_logger._get_conn", return_value=r6_db), \
             patch("agent.reasoning.session_logger.get_session_id", return_value="test"), \
             patch("agent.reasoning.session_logger.save_brief_output"):

            mock_ctx.return_value = MagicMock(
                task_type='home_page',
                theme={'name': 'test'},
                spec=None,
                bindings={},
                files_needed=[],
                reference_pages=[],
                lessons=[],
            )

            from agent.reasoning import kiwi_reason
            output = kiwi_reason("test task", "themes/test", include_code=True)

        assert output.graduated is None

    def test_include_code_true_high_trust_generates(self, r6_db):
        """include_code=True + trust >= 0.6 should generate graduated output."""
        with patch("agent.reasoning.assemble_context") as mock_ctx, \
             patch("agent.reasoning.compute_trust_score", return_value=(0.75, {})), \
             patch("agent.reasoning.session_logger._get_conn", return_value=r6_db), \
             patch("agent.reasoning.session_logger.get_session_id", return_value="test"), \
             patch("agent.reasoning.session_logger.save_brief_output"), \
             patch("agent.reasoning.code_drafter._get_conn", return_value=r6_db), \
             patch("agent.reasoning.approval_tracker._get_conn", return_value=r6_db):

            mock_ctx.return_value = MagicMock(
                task_type='home_page',
                theme={'name': 'test'},
                spec={'found': True},
                bindings={'wz_hero': True},
                files_needed=['a.php'],
                reference_pages=['ref1'],
                lessons=['L1'],
            )

            from agent.reasoning import kiwi_reason
            output = kiwi_reason("test task", "themes/test", include_code=True)

        assert output.graduated is not None
        assert output.graduated.level == 'skeleton'
        assert output.graduated.code is not None

    def test_graduated_output_exception_doesnt_crash(self, r6_db):
        """If graduated output generation fails, kiwi_reason still returns."""
        with patch("agent.reasoning.assemble_context") as mock_ctx, \
             patch("agent.reasoning.compute_trust_score", return_value=(0.8, {})), \
             patch("agent.reasoning.session_logger._get_conn", return_value=r6_db), \
             patch("agent.reasoning.session_logger.get_session_id", return_value="test"), \
             patch("agent.reasoning.session_logger.save_brief_output"), \
             patch("agent.reasoning.autonomy.generate_graduated_output", side_effect=RuntimeError("boom")):

            mock_ctx.return_value = MagicMock(
                task_type='home_page',
                theme={'name': 'test'},
                spec={'found': True},
                bindings={},
                files_needed=[],
                reference_pages=[],
                lessons=[],
            )

            from agent.reasoning import kiwi_reason
            output = kiwi_reason("test task", "themes/test", include_code=True)

        # Should not crash, graduated stays None
        assert output.graduated is None


# ============================================================
# QA-6: Draft with Real Reference File
# ============================================================

class TestDraftWithReference:
    def test_draft_reads_reference_and_swaps(self, r6_db, tmp_path):
        """Full draft flow: find reference, read file, swap styles."""
        from agent.reasoning.code_drafter import generate_draft
        from agent.reasoning.output import KiwiOutput

        # Setup: reference theme file
        ref_file = tmp_path / "ref.php"
        ref_file.write_text("""<?php
if ( ! function_exists( 'wezone_is_active' ) ) return;
?>
<section class="py-8 md:py-12">
  <div class="max-w-7xl mx-auto px-4 rounded-lg shadow-md">
    <?php wz_component('hero', $args); ?>
  </div>
</section>
""", encoding='utf-8')

        # Insert cross-theme pattern pointing to ref theme
        r6_db.execute(
            "INSERT INTO cross_theme_patterns "
            "(task_type, layout_hash, structure, themes_applied, bindings, success_count, failure_count, last_updated) "
            "VALUES ('home_page', 'h1', ?, ?, ?, 5, 0, ?)",
            (json.dumps({'layout_type': 'single-col'}), json.dumps(['ref_theme']),
             json.dumps([]), time.time()),
        )
        # Insert style knowledge for both themes
        r6_db.execute(
            "INSERT INTO style_knowledge (theme, pattern_key, value, times_seen, last_seen) "
            "VALUES ('ref_theme', 'radius', 'lg', 5, ?)",
            (time.time(),),
        )
        r6_db.execute(
            "INSERT INTO style_knowledge (theme, pattern_key, value, times_seen, last_seen) "
            "VALUES ('ref_theme', 'shadow', 'md', 5, ?)",
            (time.time(),),
        )
        r6_db.execute(
            "INSERT INTO style_knowledge (theme, pattern_key, value, times_seen, last_seen) "
            "VALUES ('target', 'radius', '2xl', 3, ?)",
            (time.time(),),
        )
        r6_db.execute(
            "INSERT INTO style_knowledge (theme, pattern_key, value, times_seen, last_seen) "
            "VALUES ('target', 'shadow', 'lg', 3, ?)",
            (time.time(),),
        )
        r6_db.commit()

        brief = KiwiOutput(
            content={'target': 'home_page', 'style_pattern': ''},
            trust_score=0.9,
            trust_breakdown={},
        )

        with patch("agent.reasoning.code_drafter._get_conn", return_value=r6_db), \
             patch("agent.reasoning.code_drafter._find_task_file", return_value=str(ref_file)):
            result = generate_draft(brief, 'themes/target')

        assert 'rounded-2xl' in result['code']
        assert 'shadow-lg' in result['code']
        assert 'rounded-lg' not in result['code']
        assert 'shadow-md' not in result['code']
        assert 'wezone_is_active' in result['code']
        assert len(result['changes']) >= 2

    def test_draft_reference_file_missing(self, r6_db, tmp_path):
        """If reference file doesn't exist, fallback to skeleton."""
        from agent.reasoning.code_drafter import generate_draft
        from agent.reasoning.output import KiwiOutput

        r6_db.execute(
            "INSERT INTO cross_theme_patterns "
            "(task_type, layout_hash, structure, themes_applied, bindings, success_count, failure_count, last_updated) "
            "VALUES ('home_page', 'h1', ?, ?, ?, 5, 0, ?)",
            (json.dumps({}), json.dumps(['ref_theme']), json.dumps([]), time.time()),
        )
        r6_db.execute(
            "INSERT INTO style_knowledge (theme, pattern_key, value, times_seen, last_seen) "
            "VALUES ('ref_theme', 'radius', 'lg', 5, ?)",
            (time.time(),),
        )
        r6_db.commit()

        brief = KiwiOutput(
            content={'target': 'home_page', 'style_pattern': ''},
            trust_score=0.9,
            trust_breakdown={},
        )

        with patch("agent.reasoning.code_drafter._get_conn", return_value=r6_db), \
             patch("agent.reasoning.code_drafter._find_task_file", return_value="/nonexistent/path.php"):
            result = generate_draft(brief, 'themes/target')

        assert 'reference_file_missing' in result['changes']


# ============================================================
# QA-7: Approval Tracker — Trust Boundary Behavior
# ============================================================

class TestApprovalBoundaries:
    def test_modified_outcome_counts_as_success(self, r6_db):
        """'modified' should count toward success rate."""
        for i in range(3):
            r6_db.execute(
                "INSERT INTO draft_outcomes (session_id, task_type, level, outcome, changes_made, created_at) "
                "VALUES (?, 'home_page', 'draft', 'modified', 3, ?)",
                (f's{i}', time.time()),
            )
        r6_db.commit()

        with patch("agent.reasoning.approval_tracker._get_conn", return_value=r6_db):
            from agent.reasoning.approval_tracker import get_draft_success_rate
            rate = get_draft_success_rate('home_page', 'draft')
            assert rate == 1.0  # modified counts as success

    def test_modified_does_not_change_trust(self, r6_db):
        """'modified' outcome should not adjust trust baseline."""
        r6_db.execute(
            "INSERT INTO trust_baselines (task_type, trust_score, last_calibrated, calibration_count) "
            "VALUES ('home_page', 0.7, ?, 5)",
            (time.time(),),
        )
        r6_db.commit()

        with patch("agent.reasoning.approval_tracker._get_conn", return_value=r6_db), \
             patch("agent.reasoning.calibrator._get_conn", return_value=r6_db):
            from agent.reasoning.approval_tracker import record_draft_outcome
            record_draft_outcome('s1', 'home_page', 'skeleton', 'modified', 2)

        row = r6_db.execute("SELECT trust_score FROM trust_baselines WHERE task_type = 'home_page'").fetchone()
        assert row[0] == 0.7  # unchanged

    def test_empty_outcomes_returns_zero_rate(self, r6_db):
        with patch("agent.reasoning.approval_tracker._get_conn", return_value=r6_db):
            from agent.reasoning.approval_tracker import get_draft_success_rate
            assert get_draft_success_rate('nonexistent', 'draft') == 0.0


# ============================================================
# QA-8: GraduatedOutput Dataclass
# ============================================================

class TestGraduatedOutputDataclass:
    def test_default_values(self):
        from agent.reasoning.autonomy import GraduatedOutput
        from agent.reasoning.output import KiwiOutput

        brief = KiwiOutput(content={}, trust_score=0.5, trust_breakdown={})
        output = GraduatedOutput(brief=brief, level='brief_only')

        assert output.code is None
        assert output.confidence == 0.0
        assert output.apply_instruction == ""
        assert output.changes_from_reference == []

    def test_changes_list_not_shared(self):
        """Ensure default_factory creates independent lists."""
        from agent.reasoning.autonomy import GraduatedOutput
        from agent.reasoning.output import KiwiOutput

        brief = KiwiOutput(content={}, trust_score=0.5, trust_breakdown={})
        o1 = GraduatedOutput(brief=brief, level='brief_only')
        o2 = GraduatedOutput(brief=brief, level='brief_only')

        o1.changes_from_reference.append("test")
        assert o2.changes_from_reference == []


# ============================================================
# QA-9: Backward Compatibility — kiwi_reason without include_code
# ============================================================

class TestBackwardCompatibility:
    def test_kiwi_reason_default_no_code(self, r6_db):
        """Calling kiwi_reason without include_code should work as before R6."""
        with patch("agent.reasoning.assemble_context") as mock_ctx, \
             patch("agent.reasoning.compute_trust_score", return_value=(0.9, {})), \
             patch("agent.reasoning.session_logger._get_conn", return_value=r6_db), \
             patch("agent.reasoning.session_logger.get_session_id", return_value="test"), \
             patch("agent.reasoning.session_logger.save_brief_output"):

            mock_ctx.return_value = MagicMock(
                task_type='home_page',
                theme={'name': 'test'},
                spec={'found': True},
                bindings={'wz_hero': True},
                files_needed=['a.php'],
                reference_pages=['ref1'],
                lessons=['L1'],
            )

            from agent.reasoning import kiwi_reason
            output = kiwi_reason("test task", "themes/test")

        # Default include_code=False → no graduated
        assert output.graduated is None
        assert output.trust_score == 0.9