"""R4 — Tests for Active Intelligence Layer."""

import json
import sqlite3
import tempfile
import time
import os
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def r4_db(tmp_path):
    """Create a fresh in-memory DB with full schema for R4 tests."""
    schema_path = Path(__file__).parent / "schema.sql"
    conn = sqlite3.connect(":memory:")
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.commit()
    yield conn
    conn.close()


class TestAdaptiveBrief:
    def test_high_trust_minimal(self):
        from agent.reasoning.adaptive_brief import get_brief_config
        config = get_brief_config(0.85)
        assert config.verbosity == "minimal"
        assert config.max_files == 5
        assert config.include_spec is False
        assert config.include_examples is False

    def test_medium_trust_standard(self):
        from agent.reasoning.adaptive_brief import get_brief_config
        config = get_brief_config(0.6)
        assert config.verbosity == "standard"
        assert config.max_files == 10
        assert config.include_spec is True

    def test_low_trust_detailed(self):
        from agent.reasoning.adaptive_brief import get_brief_config
        config = get_brief_config(0.3)
        assert config.verbosity == "detailed"
        assert config.max_files == 15
        assert config.include_examples is True

    def test_apply_trims_files(self):
        from agent.reasoning.adaptive_brief import apply_adaptive_depth
        from dataclasses import dataclass, field

        @dataclass
        class FakeContext:
            files_needed: list = field(default_factory=list)
            spec: dict = field(default_factory=dict)
            reference_pages: list = field(default_factory=list)

        ctx = FakeContext(
            files_needed=[f"file_{i}.php" for i in range(20)],
            spec={"path": "test.md", "found": True},
            reference_pages=["ref1.php", "ref2.php"],
        )
        config = apply_adaptive_depth(ctx, 0.9)
        assert len(ctx.files_needed) == 5
        assert ctx.spec is None
        assert ctx.reference_pages == []

    def test_apply_keeps_files_on_low_trust(self):
        from agent.reasoning.adaptive_brief import apply_adaptive_depth
        from dataclasses import dataclass, field

        @dataclass
        class FakeContext:
            files_needed: list = field(default_factory=list)
            spec: dict = field(default_factory=dict)
            reference_pages: list = field(default_factory=list)

        ctx = FakeContext(
            files_needed=[f"file_{i}.php" for i in range(10)],
            spec={"path": "test.md", "found": True},
            reference_pages=["ref1.php"],
        )
        config = apply_adaptive_depth(ctx, 0.3)
        assert len(ctx.files_needed) == 10
        assert ctx.spec is not None
        assert len(ctx.reference_pages) == 1


class TestProactiveWarnings:
    def test_novel_task_warning(self, r4_db):
        with patch("agent.reasoning.proactive_warnings._get_conn", return_value=r4_db), \
             patch("agent.reasoning.session_logger.get_session_id", return_value="test"):
            from agent.reasoning.proactive_warnings import check_warnings
            warnings = check_warnings("never_seen_task_xyz", "new_theme", 0.5)
            types = [w["type"] for w in warnings]
            assert "novel_task" in types
            # novel_task supersedes low_data — they should NOT both fire
            assert "low_data" not in types

    def test_high_failure_warning(self, r4_db):
        for i in range(5):
            r4_db.execute(
                "INSERT INTO calibration_events (session_id, task_type, signals, trust_before, trust_after, delta, reason, created_at) "
                "VALUES (?, ?, ?, 0.5, 0.4, -0.1, 'test', ?)",
                (f"s{i}", "failing_task", json.dumps({"multiple_rewrites": True, "kiwi_violations": True, "brief_insufficient": False}), time.time()),
            )
        r4_db.commit()

        with patch("agent.reasoning.proactive_warnings._get_conn", return_value=r4_db), \
             patch("agent.reasoning.session_logger.get_session_id", return_value="test"):
            from agent.reasoning.proactive_warnings import check_warnings
            warnings = check_warnings("failing_task", "theme", 0.5)
            types = [w["type"] for w in warnings]
            assert "high_failure" in types

    def test_stale_baseline_warning(self, r4_db):
        old_time = time.time() - (15 * 86400)
        r4_db.execute(
            "INSERT INTO trust_baselines (task_type, trust_score, last_calibrated, calibration_count) "
            "VALUES (?, 0.7, ?, 5)",
            ("stale_task", old_time),
        )
        r4_db.execute(
            "INSERT INTO context_patterns (task_type, files_read, files_written, theme, session_id, created_at) "
            "VALUES (?, '[]', '[]', 'theme', 's1', ?)",
            ("stale_task", time.time()),
        )
        r4_db.commit()

        with patch("agent.reasoning.proactive_warnings._get_conn", return_value=r4_db), \
             patch("agent.reasoning.session_logger.get_session_id", return_value="test"):
            from agent.reasoning.proactive_warnings import check_warnings
            warnings = check_warnings("stale_task", "theme", 0.5)
            types = [w["type"] for w in warnings]
            assert "stale_baseline" in types


class TestCrossTheme:
    def test_record_and_find(self, r4_db):
        with patch("agent.reasoning.cross_theme._get_conn", return_value=r4_db):
            from agent.reasoning.cross_theme import record_pattern_outcome, find_transferable_pattern

            record_pattern_outcome("checkout_page", "theme_a", {"layout": "2-col"}, ["wz_cart"], True)
            record_pattern_outcome("checkout_page", "theme_a", {"layout": "2-col"}, ["wz_cart"], True)

            result = find_transferable_pattern("checkout_page", "theme_b")
            assert result is not None
            assert result["is_new_for_theme"] is True
            assert result["confidence"] >= 0.7

    def test_low_success_not_transferred(self, r4_db):
        with patch("agent.reasoning.cross_theme._get_conn", return_value=r4_db):
            from agent.reasoning.cross_theme import record_pattern_outcome, find_transferable_pattern

            record_pattern_outcome("bad_task", "theme_a", {"layout": "1-col"}, [], True)
            record_pattern_outcome("bad_task", "theme_a", {"layout": "1-col"}, [], False)
            record_pattern_outcome("bad_task", "theme_a", {"layout": "1-col"}, [], False)
            record_pattern_outcome("bad_task", "theme_a", {"layout": "1-col"}, [], False)

            result = find_transferable_pattern("bad_task", "theme_b")
            assert result is None

    def test_not_enough_data(self, r4_db):
        with patch("agent.reasoning.cross_theme._get_conn", return_value=r4_db):
            from agent.reasoning.cross_theme import record_pattern_outcome, find_transferable_pattern

            record_pattern_outcome("new_task", "theme_a", {}, [], True)
            result = find_transferable_pattern("new_task", "theme_b")
            assert result is None


class TestNovelDetector:
    def test_detect_novel(self, r4_db):
        # Seed known bindings
        r4_db.execute(
            "INSERT INTO binding_knowledge (task_type, binding, theme, times_seen, last_seen) "
            "VALUES ('home_page', 'wz_get_products', 'theme', 5, ?)",
            (time.time(),),
        )
        r4_db.commit()

        with patch("agent.reasoning.novel_detector._get_conn", return_value=r4_db):
            from agent.reasoning.novel_detector import detect_novel_bindings
            novel = detect_novel_bindings(
                ["wz_get_products", "wz_new_function", "wz_another"],
                "home_page", "theme"
            )
            assert "wz_new_function" in novel
            assert "wz_another" in novel
            assert "wz_get_products" not in novel

    def test_record_and_promote(self, r4_db):
        with patch("agent.reasoning.novel_detector._get_conn", return_value=r4_db):
            from agent.reasoning.novel_detector import record_novel_pattern, get_promotable_patterns, promote_pattern

            record_novel_pattern("wz_new()", "binding", "theme", "home_page", "test.php")
            record_novel_pattern("wz_new()", "binding", "theme", "home_page", "test.php")
            record_novel_pattern("wz_new()", "binding", "theme", "home_page", "test.php")

            promotable = get_promotable_patterns(min_occurrences=3)
            assert len(promotable) == 1
            assert promotable[0]["pattern"] == "wz_new()"
            assert promotable[0]["times_seen"] == 3

            promote_pattern(promotable[0]["id"])
            promotable_after = get_promotable_patterns(min_occurrences=3)
            assert len(promotable_after) == 0

    def test_fifo_eviction(self, r4_db):
        with patch("agent.reasoning.novel_detector._get_conn", return_value=r4_db):
            with patch("agent.reasoning.novel_detector.MAX_NOVEL_PATTERNS", 5):
                from agent.reasoning.novel_detector import record_novel_pattern

                for i in range(8):
                    record_novel_pattern(f"pattern_{i}", "binding", f"theme_{i}", "task", "f.php")

                count = r4_db.execute("SELECT COUNT(*) FROM novel_patterns").fetchone()[0]
                assert count <= 5
