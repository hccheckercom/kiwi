"""R6 — Tests for Graduated Autonomy: level determination, code generation, approval tracking."""

import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def r6_db(tmp_path):
    """Fresh in-memory DB with full schema including R6 tables."""
    schema_path = Path(__file__).parent / "schema.sql"
    conn = sqlite3.connect(":memory:")
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.commit()
    yield conn
    conn.close()


# ============================================================
# Module 1: Autonomy — Level Determination
# ============================================================

class TestAutonomyLevels:
    def test_low_trust_brief_only(self):
        from agent.reasoning.autonomy import determine_output_level
        assert determine_output_level(0.5, 'home_page') == 'brief_only'
        assert determine_output_level(0.3, 'fix_css') == 'brief_only'

    def test_medium_trust_skeleton(self):
        from agent.reasoning.autonomy import determine_output_level
        assert determine_output_level(0.7, 'fix_css') == 'skeleton'
        assert determine_output_level(0.65, 'hero_component') == 'skeleton'

    def test_high_trust_draft(self):
        from agent.reasoning.autonomy import determine_output_level
        assert determine_output_level(0.9, 'fix_css') == 'draft'
        assert determine_output_level(0.88, 'header_component') == 'draft'

    def test_very_high_trust_ready(self):
        from agent.reasoning.autonomy import determine_output_level
        assert determine_output_level(0.96, 'fix_css') == 'ready'
        assert determine_output_level(0.99, 'hero_component') == 'ready'

    def test_complexity_penalty_checkout(self):
        from agent.reasoning.autonomy import determine_output_level
        # 0.89 - 0.05 = 0.84 → skeleton
        assert determine_output_level(0.89, 'checkout_page') == 'skeleton'
        # 0.9 - 0.05 = 0.85 → draft (boundary inclusive)
        assert determine_output_level(0.9, 'checkout_page') == 'draft'

    def test_complexity_penalty_account(self):
        from agent.reasoning.autonomy import determine_output_level
        # 0.89 - 0.05 = 0.84 → skeleton
        assert determine_output_level(0.89, 'account_page') == 'skeleton'

    def test_default_penalty_unknown_task(self):
        from agent.reasoning.autonomy import determine_output_level
        # Unknown task gets 0.02 penalty
        # 0.62 - 0.02 = 0.60 → skeleton
        assert determine_output_level(0.62, 'unknown_task') == 'skeleton'
        # 0.61 - 0.02 = 0.59 → brief_only
        assert determine_output_level(0.61, 'unknown_task') == 'brief_only'

    def test_generate_graduated_output_brief_only(self):
        from agent.reasoning.autonomy import generate_graduated_output
        from agent.reasoning.output import KiwiOutput

        brief = KiwiOutput(
            content={'target': 'checkout_page'},
            trust_score=0.4,
            trust_breakdown={},
        )

        output = generate_graduated_output(brief, 'themes/test')

        assert output.level == 'brief_only'
        assert output.code is None

    def test_generate_graduated_output_skeleton(self, r6_db):
        from agent.reasoning.autonomy import generate_graduated_output
        from agent.reasoning.output import KiwiOutput

        brief = KiwiOutput(
            content={'target': 'home_page', 'style_pattern': 'py-8 md:py-12'},
            trust_score=0.7,
            trust_breakdown={},
        )

        with patch("agent.reasoning.code_drafter._get_conn", return_value=r6_db), \
             patch("agent.reasoning.approval_tracker._get_conn", return_value=r6_db):
            output = generate_graduated_output(brief, 'themes/test')

        assert output.level == 'skeleton'
        assert output.code is not None
        assert 'wezone_is_active' in output.code

    def test_quality_check_blocks_bad_code(self, r6_db):
        from agent.reasoning.autonomy import generate_graduated_output
        from agent.reasoning.output import KiwiOutput

        brief = KiwiOutput(
            content={'target': 'home_page', 'style_pattern': ''},
            trust_score=0.7,
            trust_breakdown={},
        )

        bad_skeleton = "<?php wc_get_product(1); ?>"

        with patch("agent.reasoning.code_drafter._get_conn", return_value=r6_db), \
             patch("agent.reasoning.approval_tracker._get_conn", return_value=r6_db), \
             patch("agent.reasoning.code_drafter.generate_skeleton", return_value=bad_skeleton):
            output = generate_graduated_output(brief, 'themes/test')

        assert output.level == 'brief_only'
        assert output.code is None


# ============================================================
# Module 2: Code Drafter
# ============================================================

class TestCodeDrafter:
    def test_generic_skeleton_no_data(self, r6_db):
        from agent.reasoning.code_drafter import generate_skeleton
        from agent.reasoning.output import KiwiOutput

        brief = KiwiOutput(
            content={'target': 'cart_page', 'style_pattern': 'py-6 md:py-10'},
            trust_score=0.7,
            trust_breakdown={},
        )

        with patch("agent.reasoning.code_drafter._get_conn", return_value=r6_db):
            code = generate_skeleton(brief, 'themes/test')

        assert 'wezone_is_active' in code
        assert 'cart_page' in code
        assert 'generic skeleton' in code

    def test_skeleton_with_cross_theme_data(self, r6_db):
        from agent.reasoning.code_drafter import generate_skeleton
        from agent.reasoning.output import KiwiOutput

        r6_db.execute(
            "INSERT INTO cross_theme_patterns "
            "(task_type, layout_hash, structure, themes_applied, bindings, success_count, failure_count, last_updated) "
            "VALUES (?, ?, ?, ?, ?, 5, 0, ?)",
            ('home_page', 'abc123', json.dumps({
                'sections': ['hero', 'categories', 'products'],
                'layout_type': '2-col',
                'components_used': ['wz_hero', 'wz_product_grid'],
            }), json.dumps(['theme_a']), json.dumps([]), time.time()),
        )
        r6_db.commit()

        brief = KiwiOutput(
            content={'target': 'home_page', 'style_pattern': 'py-8'},
            trust_score=0.7,
            trust_breakdown={},
        )

        with patch("agent.reasoning.code_drafter._get_conn", return_value=r6_db):
            code = generate_skeleton(brief, 'themes/test')

        assert 'wezone_is_active' in code
        assert '2-col' in code or 'grid-cols-2' in code
        assert "wz_component('wz_hero'" in code

    def test_draft_no_reference_falls_back_to_skeleton(self, r6_db):
        from agent.reasoning.code_drafter import generate_draft
        from agent.reasoning.output import KiwiOutput

        brief = KiwiOutput(
            content={'target': 'search_page', 'style_pattern': ''},
            trust_score=0.9,
            trust_breakdown={},
        )

        with patch("agent.reasoning.code_drafter._get_conn", return_value=r6_db):
            result = generate_draft(brief, 'themes/test')

        assert 'no_reference_found' in result['changes']
        assert 'wezone_is_active' in result['code']

    def test_check_code_quality_passes_good_code(self):
        from agent.reasoning.code_drafter import check_code_quality

        good = """<?php
if ( ! function_exists( 'wezone_is_active' ) ) return;
?>
<section class="py-8">
  <div class="max-w-7xl mx-auto px-4">
    <?php wz_component('hero', $args); ?>
  </div>
</section>
"""
        assert check_code_quality(good) is True

    def test_check_code_quality_blocks_woocommerce(self):
        from agent.reasoning.code_drafter import check_code_quality
        assert check_code_quality("<?php wc_get_product(1); if(!function_exists('wezone_is_active')) return; ?>") is False

    def test_check_code_quality_blocks_wc_global(self):
        from agent.reasoning.code_drafter import check_code_quality
        assert check_code_quality("<?php WC()->cart; if(!function_exists('wezone_is_active')) return; ?>") is False

    def test_check_code_quality_blocks_wrong_accessor(self):
        from agent.reasoning.code_drafter import check_code_quality
        assert check_code_quality("<?php echo $product->name; if(!function_exists('wezone_is_active')) return; ?>") is False

    def test_check_code_quality_blocks_bem(self):
        from agent.reasoning.code_drafter import check_code_quality
        assert check_code_quality("<?php if(!function_exists('wezone_is_active')) return; ?><div class='block__element--mod'>") is False

    def test_check_code_quality_blocks_missing_guard(self):
        from agent.reasoning.code_drafter import check_code_quality
        assert check_code_quality("<?php echo 'hello'; ?>") is False

    def test_check_code_quality_allows_non_php(self):
        from agent.reasoning.code_drafter import check_code_quality
        assert check_code_quality("<div class='py-8'>hello</div>") is True

    def test_style_swap(self):
        from agent.reasoning.code_drafter import _swap_style_tokens

        code = '<div class="rounded-lg py-8 max-w-7xl shadow-md">'
        source = {'radius': 'lg', 'spacing_base': '8', 'container': '7xl', 'shadow': 'md'}
        target = {'radius': '2xl', 'spacing_base': '10', 'container': '6xl', 'shadow': 'lg'}

        result = _swap_style_tokens(code, source, target)
        assert 'rounded-2xl' in result
        assert 'max-w-6xl' in result
        assert 'shadow-lg' in result

    def test_style_similarity(self):
        from agent.reasoning.code_drafter import _compute_style_similarity

        assert _compute_style_similarity({}, {}) == 0.0
        assert _compute_style_similarity({'a': '1'}, {'a': '1'}) == 1.0
        assert _compute_style_similarity({'a': '1', 'b': '2'}, {'a': '1', 'b': '3'}) == 0.5

    def test_determine_target_path(self):
        from agent.reasoning.code_drafter import _determine_target_path

        result = _determine_target_path('checkout_page', 'themes/sfvn')
        assert result.endswith('templates/checkout.php') or result.endswith('templates\\checkout.php')

    def test_generate_final_includes_target_path(self, r6_db):
        from agent.reasoning.code_drafter import generate_final
        from agent.reasoning.output import KiwiOutput

        brief = KiwiOutput(
            content={'target': 'cart_page', 'style_pattern': ''},
            trust_score=0.96,
            trust_breakdown={},
        )

        with patch("agent.reasoning.code_drafter._get_conn", return_value=r6_db):
            result = generate_final(brief, 'themes/test')

        assert 'target_path' in result
        assert 'cart' in result['target_path']


# ============================================================
# Module 3: Approval Tracker
# ============================================================

class TestApprovalTracker:
    def test_record_approved_increases_trust(self, r6_db):
        r6_db.execute(
            "INSERT INTO trust_baselines (task_type, trust_score, last_calibrated, calibration_count) "
            "VALUES ('home_page', 0.7, ?, 5)",
            (time.time(),),
        )
        r6_db.commit()

        with patch("agent.reasoning.approval_tracker._get_conn", return_value=r6_db), \
             patch("agent.reasoning.calibrator._get_conn", return_value=r6_db):
            from agent.reasoning.approval_tracker import record_draft_outcome
            record_draft_outcome('s1', 'home_page', 'skeleton', 'approved', 0)

        row = r6_db.execute("SELECT trust_score FROM trust_baselines WHERE task_type = 'home_page'").fetchone()
        assert row[0] == pytest.approx(0.78, abs=0.01)

    def test_record_rejected_decreases_trust(self, r6_db):
        r6_db.execute(
            "INSERT INTO trust_baselines (task_type, trust_score, last_calibrated, calibration_count) "
            "VALUES ('cart_page', 0.8, ?, 5)",
            (time.time(),),
        )
        r6_db.commit()

        with patch("agent.reasoning.approval_tracker._get_conn", return_value=r6_db), \
             patch("agent.reasoning.calibrator._get_conn", return_value=r6_db):
            from agent.reasoning.approval_tracker import record_draft_outcome
            record_draft_outcome('s2', 'cart_page', 'draft', 'rejected', 0)

        row = r6_db.execute("SELECT trust_score FROM trust_baselines WHERE task_type = 'cart_page'").fetchone()
        assert row[0] == pytest.approx(0.68, abs=0.01)

    def test_trust_capped_at_095(self, r6_db):
        r6_db.execute(
            "INSERT INTO trust_baselines (task_type, trust_score, last_calibrated, calibration_count) "
            "VALUES ('fix_css', 0.93, ?, 10)",
            (time.time(),),
        )
        r6_db.commit()

        with patch("agent.reasoning.approval_tracker._get_conn", return_value=r6_db), \
             patch("agent.reasoning.calibrator._get_conn", return_value=r6_db):
            from agent.reasoning.approval_tracker import record_draft_outcome
            record_draft_outcome('s3', 'fix_css', 'ready', 'approved', 0)

        row = r6_db.execute("SELECT trust_score FROM trust_baselines WHERE task_type = 'fix_css'").fetchone()
        assert row[0] <= 0.95

    def test_trust_floored_at_04(self, r6_db):
        r6_db.execute(
            "INSERT INTO trust_baselines (task_type, trust_score, last_calibrated, calibration_count) "
            "VALUES ('search_page', 0.42, ?, 5)",
            (time.time(),),
        )
        r6_db.commit()

        with patch("agent.reasoning.approval_tracker._get_conn", return_value=r6_db), \
             patch("agent.reasoning.calibrator._get_conn", return_value=r6_db):
            from agent.reasoning.approval_tracker import record_draft_outcome
            record_draft_outcome('s4', 'search_page', 'skeleton', 'rejected', 0)

        row = r6_db.execute("SELECT trust_score FROM trust_baselines WHERE task_type = 'search_page'").fetchone()
        assert row[0] >= 0.4

    def test_should_attempt_level_no_data(self, r6_db):
        with patch("agent.reasoning.approval_tracker._get_conn", return_value=r6_db):
            from agent.reasoning.approval_tracker import should_attempt_level
            assert should_attempt_level('home_page', 'skeleton') is True

    def test_should_attempt_level_blocked_after_rejections(self, r6_db):
        for i in range(5):
            r6_db.execute(
                "INSERT INTO draft_outcomes (session_id, task_type, level, outcome, changes_made, created_at) "
                "VALUES (?, 'checkout_page', 'draft', 'rejected', 0, ?)",
                (f's{i}', time.time()),
            )
        r6_db.commit()

        with patch("agent.reasoning.approval_tracker._get_conn", return_value=r6_db):
            from agent.reasoning.approval_tracker import should_attempt_level
            assert should_attempt_level('checkout_page', 'draft') is False

    def test_should_attempt_level_allowed_with_good_rate(self, r6_db):
        for i in range(4):
            r6_db.execute(
                "INSERT INTO draft_outcomes (session_id, task_type, level, outcome, changes_made, created_at) "
                "VALUES (?, 'home_page', 'skeleton', 'approved', 0, ?)",
                (f's{i}', time.time()),
            )
        r6_db.execute(
            "INSERT INTO draft_outcomes (session_id, task_type, level, outcome, changes_made, created_at) "
            "VALUES ('s5', 'home_page', 'skeleton', 'rejected', 0, ?)",
            (time.time(),),
        )
        r6_db.commit()

        with patch("agent.reasoning.approval_tracker._get_conn", return_value=r6_db):
            from agent.reasoning.approval_tracker import should_attempt_level
            # 4/5 = 0.8 > 0.3 threshold for skeleton
            assert should_attempt_level('home_page', 'skeleton') is True

    def test_success_rate_calculation(self, r6_db):
        r6_db.execute(
            "INSERT INTO draft_outcomes (session_id, task_type, level, outcome, changes_made, created_at) "
            "VALUES ('s1', 'home_page', 'draft', 'approved', 0, ?)",
            (time.time(),),
        )
        r6_db.execute(
            "INSERT INTO draft_outcomes (session_id, task_type, level, outcome, changes_made, created_at) "
            "VALUES ('s2', 'home_page', 'draft', 'modified', 2, ?)",
            (time.time(),),
        )
        r6_db.execute(
            "INSERT INTO draft_outcomes (session_id, task_type, level, outcome, changes_made, created_at) "
            "VALUES ('s3', 'home_page', 'draft', 'rejected', 0, ?)",
            (time.time(),),
        )
        r6_db.commit()

        with patch("agent.reasoning.approval_tracker._get_conn", return_value=r6_db):
            from agent.reasoning.approval_tracker import get_draft_success_rate
            rate = get_draft_success_rate('home_page', 'draft')
            # 2 success (approved + modified) / 3 total
            assert rate == pytest.approx(2/3, abs=0.01)


# ============================================================
# Module 4: Schema Migration
# ============================================================

class TestSchemaMigration:
    def test_draft_outcomes_table_exists(self, r6_db):
        row = r6_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='draft_outcomes'"
        ).fetchone()
        assert row is not None

    def test_draft_outcomes_index_exists(self, r6_db):
        row = r6_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_do_task'"
        ).fetchone()
        assert row is not None

    def test_migration_creates_table(self):
        """Test that _migrate creates draft_outcomes if missing."""
        conn = sqlite3.connect(":memory:")
        # Create minimal base tables so _migrate has something to work with
        conn.executescript("""
            CREATE TABLE session_log (id INTEGER PRIMARY KEY, session_id TEXT, tool TEXT, timestamp REAL);
            CREATE TABLE sessions (session_id TEXT PRIMARY KEY, started_at REAL, ended_at REAL,
                task_hint TEXT, files_read INTEGER DEFAULT 0, files_written INTEGER DEFAULT 0,
                theme_path TEXT, processed INTEGER DEFAULT 0);
            CREATE TABLE context_patterns (id INTEGER PRIMARY KEY, task_type TEXT, files_read TEXT,
                files_written TEXT, read_order TEXT, theme TEXT, session_id TEXT, created_at REAL);
            CREATE TABLE cross_theme_patterns (id INTEGER PRIMARY KEY, task_type TEXT,
                layout_hash TEXT NOT NULL DEFAULT '', structure TEXT, themes_applied TEXT,
                bindings TEXT, success_count INTEGER DEFAULT 0, failure_count INTEGER DEFAULT 0,
                last_updated REAL);
        """)
        conn.commit()

        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='draft_outcomes'"
        ).fetchone()
        assert row is None

        from agent.reasoning.session_logger import _migrate
        _migrate(conn)

        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='draft_outcomes'"
        ).fetchone()
        assert row is not None
        conn.close()
