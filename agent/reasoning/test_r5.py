"""R5 — Tests for Performance Guard, Warning Feedback, Multi-Pattern, Cold Start, Auto-Promote."""

import json
import sqlite3
import tempfile
import time
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def r5_db(tmp_path):
    """Fresh in-memory DB with full R5 schema."""
    schema_path = Path(__file__).parent / "schema.sql"
    conn = sqlite3.connect(":memory:")
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.commit()
    yield conn
    conn.close()


# ============================================================
# Module 5: Performance Guard
# ============================================================

class TestPerformanceGuard:
    def test_throttle_cooldown(self):
        import agent.reasoning as reasoning
        reasoning._last_learn_ts = time.time()
        reasoning._learn_skip_count = 0

        with patch("agent.reasoning.session_logger.get_unprocessed_sessions") as mock:
            reasoning._auto_learn_recent(max_sessions=3)
            mock.assert_not_called()

    def test_skip_after_slow(self):
        import agent.reasoning as reasoning
        reasoning._last_learn_ts = 0
        reasoning._learn_skip_count = 3

        with patch("agent.reasoning.session_logger.get_unprocessed_sessions") as mock:
            reasoning._auto_learn_recent(max_sessions=3)
            mock.assert_not_called()
            assert reasoning._learn_skip_count == 2

    def test_normal_execution(self):
        import agent.reasoning as reasoning
        reasoning._last_learn_ts = 0
        reasoning._learn_skip_count = 0

        with patch("agent.reasoning.session_logger.get_unprocessed_sessions", return_value=[]), \
             patch("agent.reasoning.session_logger._get_conn"):
            reasoning._auto_learn_recent(max_sessions=3)
            assert reasoning._last_learn_ts > 0


# ============================================================
# Module 1: Warning Feedback Loop
# ============================================================

class TestWarningFeedback:
    def test_evaluate_success_marks_not_useful(self, r5_db):
        r5_db.execute(
            "INSERT INTO warnings_issued (session_id, task_type, warning_type, message, created_at) "
            "VALUES ('s1', 'home_page', 'low_data', 'test', ?)",
            (time.time(),),
        )
        r5_db.commit()

        with patch("agent.reasoning.proactive_warnings._get_conn", return_value=r5_db):
            from agent.reasoning.proactive_warnings import evaluate_warnings_post_session
            evaluate_warnings_post_session("s1", 0)

        row = r5_db.execute("SELECT was_useful FROM warnings_issued WHERE session_id = 's1'").fetchone()
        assert row[0] == 0

    def test_evaluate_failure_marks_predictive_useful(self, r5_db):
        r5_db.execute(
            "INSERT INTO warnings_issued (session_id, task_type, warning_type, message, created_at) "
            "VALUES ('s2', 'checkout_page', 'high_failure', 'test', ?)",
            (time.time(),),
        )
        r5_db.execute(
            "INSERT INTO warnings_issued (session_id, task_type, warning_type, message, created_at) "
            "VALUES ('s2', 'checkout_page', 'low_data', 'test', ?)",
            (time.time(),),
        )
        r5_db.commit()

        with patch("agent.reasoning.proactive_warnings._get_conn", return_value=r5_db):
            from agent.reasoning.proactive_warnings import evaluate_warnings_post_session
            evaluate_warnings_post_session("s2", 2)

        rows = r5_db.execute(
            "SELECT warning_type, was_useful FROM warnings_issued WHERE session_id = 's2' ORDER BY id"
        ).fetchall()
        assert rows[0] == ("high_failure", 1)
        assert rows[1] == ("low_data", 0)

    def test_ambiguous_leaves_null(self, r5_db):
        r5_db.execute(
            "INSERT INTO warnings_issued (session_id, task_type, warning_type, message, created_at) "
            "VALUES ('s3', 'home_page', 'novel_task', 'test', ?)",
            (time.time(),),
        )
        r5_db.commit()

        with patch("agent.reasoning.proactive_warnings._get_conn", return_value=r5_db):
            from agent.reasoning.proactive_warnings import evaluate_warnings_post_session
            evaluate_warnings_post_session("s3", 1)

        row = r5_db.execute("SELECT was_useful FROM warnings_issued WHERE session_id = 's3'").fetchone()
        assert row[0] is None

    def test_suppression_after_noise(self, r5_db):
        for i in range(10):
            r5_db.execute(
                "INSERT INTO warnings_issued (session_id, task_type, warning_type, message, was_useful, created_at) "
                "VALUES (?, 'home_page', 'low_data', 'test', 0, ?)",
                (f"s{i}", time.time()),
            )
        r5_db.execute(
            "INSERT INTO context_patterns (task_type, files_read, files_written, theme, session_id, created_at) "
            "VALUES ('home_page', '[]', '[]', 'theme_a', 'x', ?)",
            (time.time(),),
        )
        r5_db.commit()

        with patch("agent.reasoning.proactive_warnings._get_conn", return_value=r5_db), \
             patch("agent.reasoning.session_logger.get_session_id", return_value="test"):
            from agent.reasoning.proactive_warnings import check_warnings
            warnings = check_warnings("home_page", "theme_a", 0.5)
            types = [w["type"] for w in warnings]
            assert "low_data" not in types


# ============================================================
# Module 2: Multi-Pattern Cross-Theme
# ============================================================

class TestMultiPatternCrossTheme:
    def test_different_structures_stored_separately(self, r5_db):
        with patch("agent.reasoning.cross_theme._get_conn", return_value=r5_db):
            from agent.reasoning.cross_theme import record_pattern_outcome, find_transferable_pattern

            record_pattern_outcome("checkout_page", "theme_a", {"layout": "2-col", "sidebar": True}, ["wz_cart"], True)
            record_pattern_outcome("checkout_page", "theme_a", {"layout": "2-col", "sidebar": True}, ["wz_cart"], True)
            record_pattern_outcome("checkout_page", "theme_b", {"layout": "1-col"}, ["wz_checkout"], True)
            record_pattern_outcome("checkout_page", "theme_b", {"layout": "1-col"}, ["wz_checkout"], True)

            count = r5_db.execute("SELECT COUNT(*) FROM cross_theme_patterns WHERE task_type = 'checkout_page'").fetchone()[0]
            assert count == 2

    def test_best_pattern_returned(self, r5_db):
        with patch("agent.reasoning.cross_theme._get_conn", return_value=r5_db):
            from agent.reasoning.cross_theme import record_pattern_outcome, find_transferable_pattern

            for _ in range(5):
                record_pattern_outcome("home_page", "theme_a", {"hero": True, "grid": True}, ["wz_hero"], True)
            for _ in range(2):
                record_pattern_outcome("home_page", "theme_b", {"slider": True}, ["wz_slider"], True)
            record_pattern_outcome("home_page", "theme_b", {"slider": True}, ["wz_slider"], False)

            result = find_transferable_pattern("home_page", "theme_c")
            assert result is not None
            assert result["confidence"] == 1.0
            assert "hero" in result["structure"]

    def test_eviction_at_max(self, r5_db):
        with patch("agent.reasoning.cross_theme._get_conn", return_value=r5_db):
            from agent.reasoning.cross_theme import record_pattern_outcome

            record_pattern_outcome("task", "t1", {"a": 1}, [], True)
            record_pattern_outcome("task", "t1", {"a": 1}, [], True)
            record_pattern_outcome("task", "t2", {"b": 1}, [], True)
            record_pattern_outcome("task", "t2", {"b": 1}, [], True)
            record_pattern_outcome("task", "t3", {"c": 1}, [], True)
            record_pattern_outcome("task", "t3", {"c": 1}, [], True)
            # 4th pattern should evict the worst
            record_pattern_outcome("task", "t4", {"d": 1}, [], True)
            record_pattern_outcome("task", "t4", {"d": 1}, [], True)

            count = r5_db.execute("SELECT COUNT(*) FROM cross_theme_patterns WHERE task_type = 'task'").fetchone()[0]
            assert count <= 3

    def test_layout_hash_deterministic(self):
        from agent.reasoning.cross_theme import _layout_hash
        h1 = _layout_hash({"b": 1, "a": 2, "c": 3})
        h2 = _layout_hash({"a": 2, "c": 3, "b": 1})
        assert h1 == h2


# ============================================================
# Module 4: Cold Start Accelerator
# ============================================================

class TestColdStart:
    def test_needs_bootstrap_empty(self, r5_db):
        with patch("agent.reasoning.cold_start._get_conn", return_value=r5_db):
            from agent.reasoning.cold_start import needs_bootstrap
            assert needs_bootstrap("themes/new-theme") is True

    def test_needs_bootstrap_has_data(self, r5_db):
        r5_db.execute(
            "INSERT INTO context_patterns (task_type, files_read, files_written, theme, session_id, created_at) "
            "VALUES ('home_page', '[]', '[]', 'new-theme', 's1', ?)",
            (time.time(),),
        )
        r5_db.commit()

        with patch("agent.reasoning.cold_start._get_conn", return_value=r5_db):
            from agent.reasoning.cold_start import needs_bootstrap
            assert needs_bootstrap("themes/new-theme") is False

    def test_detect_industry_from_config(self, tmp_path):
        inc = tmp_path / "inc"
        inc.mkdir()
        (inc / "store-config.php").write_text("<?php\n'industry' => 'beauty',\n", encoding="utf-8")

        from agent.reasoning.cold_start import detect_industry
        assert detect_industry(str(tmp_path)) == "beauty"

    def test_detect_industry_from_input(self, tmp_path):
        docs = tmp_path / "docs" / "_blueprint"
        docs.mkdir(parents=True)
        (docs / "01-INPUT.md").write_text("# Input\nIndustry: fashion\n", encoding="utf-8")

        from agent.reasoning.cold_start import detect_industry
        assert detect_industry(str(tmp_path)) == "fashion"

    def test_bootstrap_copies_styles(self, r5_db, tmp_path):
        inc = tmp_path / "inc"
        inc.mkdir()
        (inc / "store-config.php").write_text("<?php\n'industry' => 'beauty',\n", encoding="utf-8")

        r5_db.execute(
            "INSERT INTO style_knowledge (theme, pattern_key, value, times_seen, last_seen) "
            "VALUES ('existing-beauty', 'radius', 'lg', 5, ?)",
            (time.time(),),
        )
        r5_db.commit()

        theme_name = tmp_path.name

        with patch("agent.reasoning.cold_start._get_conn", return_value=r5_db), \
             patch("agent.reasoning.cold_start.get_industry_themes", return_value=["existing-beauty"]):
            from agent.reasoning.cold_start import bootstrap_from_industry
            result = bootstrap_from_industry(str(tmp_path))

        assert result["bootstrapped"] is True
        assert result["styles"] >= 1

        row = r5_db.execute(
            "SELECT value FROM style_knowledge WHERE theme = ? AND pattern_key = 'radius'",
            (theme_name,),
        ).fetchone()
        assert row[0] == "lg"


# ============================================================
# Module 3: Auto-Promote Pipeline
# ============================================================

class TestAutoPromote:
    def test_create_suggestion(self, r5_db):
        r5_db.execute(
            "INSERT INTO novel_patterns (pattern, pattern_type, theme, task_type, times_seen, first_seen, last_seen, promoted) "
            "VALUES ('wz_new_helper', 'binding', 'theme_a', 'home_page', 5, ?, ?, 0)",
            (time.time() - 100, time.time()),
        )
        r5_db.commit()

        with patch("agent.reasoning.auto_promoter._get_conn", return_value=r5_db), \
             patch("agent.reasoning.novel_detector._get_conn", return_value=r5_db):
            from agent.reasoning.auto_promoter import auto_promote_check
            created = auto_promote_check()

        assert len(created) == 1
        assert created[0]["pattern"] == "wz_new_helper"
        assert created[0]["category"] == "api-usage"

        promoted = r5_db.execute("SELECT promoted FROM novel_patterns WHERE pattern = 'wz_new_helper'").fetchone()
        assert promoted[0] == 1

    def test_max_promotions_per_session(self, r5_db):
        for i in range(5):
            r5_db.execute(
                "INSERT INTO novel_patterns (pattern, pattern_type, theme, task_type, times_seen, first_seen, last_seen, promoted) "
                "VALUES (?, 'binding', 'theme', 'task', 4, ?, ?, 0)",
                (f"pattern_{i}", time.time() - 100, time.time()),
            )
        r5_db.commit()

        with patch("agent.reasoning.auto_promoter._get_conn", return_value=r5_db), \
             patch("agent.reasoning.novel_detector._get_conn", return_value=r5_db):
            from agent.reasoning.auto_promoter import auto_promote_check
            created = auto_promote_check()

        assert len(created) <= 2

    def test_get_pending_suggestions(self, r5_db):
        r5_db.execute(
            "INSERT INTO promotion_suggestions (pattern, pattern_type, category, severity, theme, task_type, times_seen, status, created_at) "
            "VALUES ('wz_test', 'binding', 'api-usage', 'SUGGEST', 'theme', 'home_page', 3, 'pending', ?)",
            (time.time(),),
        )
        r5_db.commit()

        with patch("agent.reasoning.auto_promoter._get_conn", return_value=r5_db):
            from agent.reasoning.auto_promoter import get_pending_suggestions
            pending = get_pending_suggestions()

        assert len(pending) == 1
        assert pending[0]["pattern"] == "wz_test"

    def test_approve_reject(self, r5_db):
        r5_db.execute(
            "INSERT INTO promotion_suggestions (pattern, pattern_type, category, severity, theme, task_type, times_seen, status, created_at) "
            "VALUES ('p1', 'binding', 'api-usage', 'SUGGEST', 'theme', 'task', 3, 'pending', ?)",
            (time.time(),),
        )
        r5_db.execute(
            "INSERT INTO promotion_suggestions (pattern, pattern_type, category, severity, theme, task_type, times_seen, status, created_at) "
            "VALUES ('p2', 'style', 'layout-consistency', 'SUGGEST', 'theme', 'task', 4, 'pending', ?)",
            (time.time(),),
        )
        r5_db.commit()

        with patch("agent.reasoning.auto_promoter._get_conn", return_value=r5_db):
            from agent.reasoning.auto_promoter import approve_suggestion, reject_suggestion
            assert approve_suggestion(1) is True
            assert reject_suggestion(2) is True

        s1 = r5_db.execute("SELECT status FROM promotion_suggestions WHERE id = 1").fetchone()
        s2 = r5_db.execute("SELECT status FROM promotion_suggestions WHERE id = 2").fetchone()
        assert s1[0] == "approved"
        assert s2[0] == "rejected"