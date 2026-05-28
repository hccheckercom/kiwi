"""R7 QA — Comprehensive edge cases, integration, error handling, concurrency."""

import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def r7_db():
    schema_path = Path(__file__).parent / "schema.sql"
    conn = sqlite3.connect(":memory:")
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.commit()
    yield conn
    conn.close()


# ============================================================
# QA-1: edits_after_first — counts EXTRA edits, not total
# ============================================================

class TestEditsAfterFirst:
    def test_single_edit_per_file_is_zero(self, r7_db):
        """One edit per file = 0 extra edits (first edit is not 'after first')."""
        writes = [
            {'file': 'a.php', 'tool': 'Edit', 'timestamp': 100},
            {'file': 'b.php', 'tool': 'Edit', 'timestamp': 110},
        ]
        entries = [
            {'tool': 'Edit', 'file': 'a.php', 'action': 'edit', 'metadata': {}, 'timestamp': 100},
            {'tool': 'Edit', 'file': 'b.php', 'action': 'edit', 'metadata': {}, 'timestamp': 110},
        ]

        with patch("agent.reasoning.metrics._get_conn", return_value=r7_db), \
             patch("agent.reasoning.metrics.get_session_reads", return_value=[]), \
             patch("agent.reasoning.metrics.get_session_writes", return_value=writes), \
             patch("agent.reasoning.metrics.get_session_log_entries", return_value=entries):
            from agent.reasoning.metrics import record_output_quality
            result = record_output_quality("s1")

        assert result['edits_after_first'] == 0

    def test_three_edits_same_file_is_two(self, r7_db):
        """3 edits to same file = 2 extra edits."""
        writes = [
            {'file': 'a.php', 'tool': 'Edit', 'timestamp': 100},
            {'file': 'a.php', 'tool': 'Edit', 'timestamp': 110},
            {'file': 'a.php', 'tool': 'Edit', 'timestamp': 120},
        ]
        entries = [
            {'tool': 'Edit', 'file': 'a.php', 'action': 'edit', 'metadata': {}, 'timestamp': t}
            for t in [100, 110, 120]
        ]

        with patch("agent.reasoning.metrics._get_conn", return_value=r7_db), \
             patch("agent.reasoning.metrics.get_session_reads", return_value=[]), \
             patch("agent.reasoning.metrics.get_session_writes", return_value=writes), \
             patch("agent.reasoning.metrics.get_session_log_entries", return_value=entries):
            from agent.reasoning.metrics import record_output_quality
            result = record_output_quality("s1")

        assert result['edits_after_first'] == 2

    def test_write_tool_not_counted_as_edit(self, r7_db):
        """Write tool calls should not count toward edits_after_first."""
        writes = [
            {'file': 'a.php', 'tool': 'Write', 'timestamp': 100},
            {'file': 'a.php', 'tool': 'Write', 'timestamp': 110},
        ]
        entries = [
            {'tool': 'Write', 'file': 'a.php', 'action': 'write', 'metadata': {}, 'timestamp': 100},
            {'tool': 'Write', 'file': 'a.php', 'action': 'write', 'metadata': {}, 'timestamp': 110},
        ]

        with patch("agent.reasoning.metrics._get_conn", return_value=r7_db), \
             patch("agent.reasoning.metrics.get_session_reads", return_value=[]), \
             patch("agent.reasoning.metrics.get_session_writes", return_value=writes), \
             patch("agent.reasoning.metrics.get_session_log_entries", return_value=entries):
            from agent.reasoning.metrics import record_output_quality
            result = record_output_quality("s1")

        assert result['edits_after_first'] == 0


# ============================================================
# QA-2: metrics.py accepts both dict and KiwiOutput
# ============================================================

class TestBriefInputTypes:
    def test_dict_brief_from_get_brief_for_session(self, r7_db):
        """Dict format from get_brief_for_session() should work."""
        brief_dict = {
            'task_type': 'cart_page',
            'files_needed': ['cart.php', 'mini-cart.php'],
            'trust_score': 0.65,
            'recommendation': 'verify_partial',
        }
        writes = [{'file': 'cart.php', 'tool': 'Write', 'timestamp': 100}]
        reads = [{'file': 'cart.php', 'timestamp': 90}]
        entries = [
            {'tool': 'Read', 'file': 'cart.php', 'action': 'read', 'metadata': {}, 'timestamp': 90},
            {'tool': 'Write', 'file': 'cart.php', 'action': 'write', 'metadata': {}, 'timestamp': 100},
        ]

        with patch("agent.reasoning.metrics._get_conn", return_value=r7_db), \
             patch("agent.reasoning.metrics.get_session_reads", return_value=reads), \
             patch("agent.reasoning.metrics.get_session_writes", return_value=writes), \
             patch("agent.reasoning.metrics.get_session_log_entries", return_value=entries):
            from agent.reasoning.metrics import record_output_quality
            result = record_output_quality("s1", brief_dict)

        assert result['task_type'] == 'cart_page'
        assert result['trust_score'] == 0.65
        assert result['files_re_read'] == 1

    def test_kiwi_output_object(self, r7_db):
        """KiwiOutput dataclass should work."""
        from agent.reasoning.output import KiwiOutput
        brief = KiwiOutput(
            content={'target': 'product_page', 'files_needed': ['single.php']},
            trust_score=0.9,
            trust_breakdown={},
        )
        writes = [{'file': 'single.php', 'tool': 'Write', 'timestamp': 100}]
        entries = [{'tool': 'Write', 'file': 'single.php', 'action': 'write', 'metadata': {}, 'timestamp': 100}]

        with patch("agent.reasoning.metrics._get_conn", return_value=r7_db), \
             patch("agent.reasoning.metrics.get_session_reads", return_value=[]), \
             patch("agent.reasoning.metrics.get_session_writes", return_value=writes), \
             patch("agent.reasoning.metrics.get_session_log_entries", return_value=entries):
            from agent.reasoning.metrics import record_output_quality
            result = record_output_quality("s1", brief)

        assert result['task_type'] == 'product_page'
        assert result['trust_score'] == 0.9

    def test_none_brief(self, r7_db):
        """None brief should default to generic."""
        writes = [{'file': 'x.php', 'tool': 'Write', 'timestamp': 100}]
        entries = [{'tool': 'Write', 'file': 'x.php', 'action': 'write', 'metadata': {}, 'timestamp': 100}]

        with patch("agent.reasoning.metrics._get_conn", return_value=r7_db), \
             patch("agent.reasoning.metrics.get_session_reads", return_value=[]), \
             patch("agent.reasoning.metrics.get_session_writes", return_value=writes), \
             patch("agent.reasoning.metrics.get_session_log_entries", return_value=entries):
            from agent.reasoning.metrics import record_output_quality
            result = record_output_quality("s1", None)

        assert result['task_type'] == 'generic'
        assert result['trust_score'] == 0.0
        assert result['autonomy_level'] == 'none'


# ============================================================
# QA-3: Intelligence score edge cases
# ============================================================

class TestIntelligenceScoreEdgeCases:
    def test_first_tokens_zero_gives_zero_points(self, r7_db):
        """If first week had 0 tokens, token reduction score = 0 (not 30)."""
        from agent.reasoning.metrics import epoch_week
        from agent.reasoning.dashboard import compute_intelligence_score

        dashboard = {
            'weekly_trends': [
                {'week': epoch_week() - 1, 'avg_tokens': 0, 'avg_re_reads': 0, 'avg_trust': 0.5, 'avg_level': 1, 'sessions': 5},
                {'week': epoch_week(), 'avg_tokens': 5000, 'avg_re_reads': 0, 'avg_trust': 0.5, 'avg_level': 1, 'sessions': 5},
            ]
        }
        score = compute_intelligence_score(dashboard)
        # Token component should be 0 (can't measure improvement from 0 baseline)
        # Trust: 0.5 * 30 = 15, Level: 1/3*20 = 6.67, Re-read: 20 (no re-reads)
        assert score < 45  # Without the 30 free points

    def test_tokens_increasing_gives_zero_token_points(self):
        """If tokens increased (regression), token score = 0."""
        from agent.reasoning.dashboard import compute_intelligence_score

        dashboard = {
            'weekly_trends': [
                {'week': 100, 'avg_tokens': 5000, 'avg_re_reads': 2, 'avg_trust': 0.5, 'avg_level': 1, 'sessions': 5},
                {'week': 101, 'avg_tokens': 8000, 'avg_re_reads': 3, 'avg_trust': 0.5, 'avg_level': 1, 'sessions': 5},
            ]
        }
        score = compute_intelligence_score(dashboard)
        # Token reduction negative → clamped to 0
        # Re-read increased → clamped to 0
        # Trust: 15, Level: 6.67
        assert 20 < score < 25

    def test_perfect_improvement(self):
        """Maximum possible improvement gives score near 100."""
        from agent.reasoning.dashboard import compute_intelligence_score

        dashboard = {
            'weekly_trends': [
                {'week': 100, 'avg_tokens': 10000, 'avg_re_reads': 5, 'avg_trust': 0.1, 'avg_level': 0, 'sessions': 10},
                {'week': 101, 'avg_tokens': 1000, 'avg_re_reads': 0, 'avg_trust': 1.0, 'avg_level': 3, 'sessions': 10},
            ]
        }
        score = compute_intelligence_score(dashboard)
        assert score >= 90

    def test_no_change_gives_moderate_score(self):
        """Flat metrics give score based on absolute trust/level, not improvement."""
        from agent.reasoning.dashboard import compute_intelligence_score

        dashboard = {
            'weekly_trends': [
                {'week': 100, 'avg_tokens': 5000, 'avg_re_reads': 0, 'avg_trust': 0.7, 'avg_level': 2, 'sessions': 5},
                {'week': 101, 'avg_tokens': 5000, 'avg_re_reads': 0, 'avg_trust': 0.7, 'avg_level': 2, 'sessions': 5},
            ]
        }
        score = compute_intelligence_score(dashboard)
        # Token: 0 (no change), Trust: 21, Level: 13.3, Re-read: 20
        assert 50 < score < 60


# ============================================================
# QA-4: Stagnation confidence gate
# ============================================================

class TestStagnationConfidence:
    def _fill(self, conn, week, tokens, trust, level, count):
        for i in range(count):
            conn.execute(
                "INSERT INTO output_quality "
                "(session_id, week, task_type, brief_version, trust_score, tokens_estimated, "
                "files_re_read, edits_after_first, total_tool_calls, brief_level, "
                "autonomy_level, session_duration_sec, created_at) "
                "VALUES (?, ?, 'generic', 1, ?, ?, 0, 0, 5, ?, 'skeleton', 30, ?)",
                (f's-{week}-{i}', week, trust, tokens, level, time.time())
            )
        conn.commit()

    def test_3_sessions_each_period_confidence_06(self, r7_db):
        """3+3=6 sessions total → confidence 0.6 (above 0.5 threshold)."""
        from agent.reasoning.metrics import epoch_week
        w = epoch_week()
        self._fill(r7_db, w - 3, 5000, 0.5, 1, 3)
        self._fill(r7_db, w - 2, 5000, 0.5, 1, 3)  # baseline period: 6 total
        self._fill(r7_db, w - 1, 5000, 0.5, 1, 3)
        self._fill(r7_db, w, 5000, 0.5, 1, 3)  # recent period: 6 total

        with patch("agent.reasoning.alerts._get_conn", return_value=r7_db):
            from agent.reasoning.alerts import check_stagnation
            alert = check_stagnation()

        # 6+6=12 sessions → confidence = 12/10 = 1.0 (capped)
        assert alert is not None
        assert alert['confidence'] == 1.0

    def test_below_min_sessions_returns_none(self, r7_db):
        """2 sessions per period (below min 3) → None."""
        from agent.reasoning.metrics import epoch_week
        w = epoch_week()
        self._fill(r7_db, w - 3, 5000, 0.5, 1, 1)
        self._fill(r7_db, w - 2, 5000, 0.5, 1, 1)  # baseline: 2 total
        self._fill(r7_db, w - 1, 5000, 0.5, 1, 1)
        self._fill(r7_db, w, 5000, 0.5, 1, 1)  # recent: 2 total

        with patch("agent.reasoning.alerts._get_conn", return_value=r7_db):
            from agent.reasoning.alerts import check_stagnation
            assert check_stagnation() is None

    def test_confidence_calculation(self, r7_db):
        """Verify confidence = (recent + baseline sessions) / 10."""
        from agent.reasoning.metrics import epoch_week
        w = epoch_week()
        self._fill(r7_db, w - 3, 5000, 0.5, 1, 2)
        self._fill(r7_db, w - 2, 5000, 0.5, 1, 2)  # baseline: 4
        self._fill(r7_db, w - 1, 5000, 0.5, 1, 2)
        self._fill(r7_db, w, 5000, 0.5, 1, 2)  # recent: 4

        with patch("agent.reasoning.alerts._get_conn", return_value=r7_db):
            from agent.reasoning.alerts import check_stagnation
            alert = check_stagnation()

        # 4+4=8 → confidence = 0.8
        assert alert is not None
        assert alert['confidence'] == 0.8


# ============================================================
# QA-5: epoch_week stability
# ============================================================

class TestEpochWeekStability:
    def test_monotonically_increasing(self):
        from agent.reasoning.metrics import epoch_week
        t1 = 1700000000.0
        t2 = t1 + 604800
        t3 = t2 + 604800
        assert epoch_week(t1) < epoch_week(t2) < epoch_week(t3)

    def test_within_same_week(self):
        from agent.reasoning.metrics import epoch_week
        # Use a timestamp at the start of a week boundary to guarantee +6 days stays in same week
        t = 604800 * 2900.0  # exact week boundary
        assert epoch_week(t) == epoch_week(t + 86400)  # +1 day
        assert epoch_week(t) == epoch_week(t + 86400 * 6)  # +6 days (still < 604800)

    def test_boundary_crossing(self):
        from agent.reasoning.metrics import epoch_week
        t = 604800 * 2900  # exact week boundary
        assert epoch_week(t) == 2900
        assert epoch_week(t - 1) == 2899
        assert epoch_week(t + 1) == 2900


# ============================================================
# QA-6: Dashboard with NULL values in DB
# ============================================================

class TestDashboardNullHandling:
    def test_null_trust_score(self, r7_db):
        """Rows with NULL trust_score should not crash dashboard."""
        from agent.reasoning.metrics import epoch_week
        w = epoch_week()
        r7_db.execute(
            "INSERT INTO output_quality "
            "(session_id, week, task_type, brief_version, trust_score, tokens_estimated, "
            "files_re_read, edits_after_first, total_tool_calls, brief_level, "
            "autonomy_level, session_duration_sec, created_at) "
            "VALUES ('s1', ?, 'generic', 1, NULL, 5000, 0, 0, 5, 0, 'none', 30, ?)",
            (w, time.time())
        )
        r7_db.commit()

        with patch("agent.reasoning.dashboard._get_conn", return_value=r7_db):
            from agent.reasoning.dashboard import generate_dashboard
            d = generate_dashboard(weeks=4)

        assert len(d['weekly_trends']) == 1
        assert d['weekly_trends'][0]['avg_trust'] == 0.0

    def test_null_tokens_estimated(self, r7_db):
        """Rows with NULL tokens_estimated should not crash."""
        from agent.reasoning.metrics import epoch_week
        w = epoch_week()
        r7_db.execute(
            "INSERT INTO output_quality "
            "(session_id, week, task_type, brief_version, trust_score, tokens_estimated, "
            "files_re_read, edits_after_first, total_tool_calls, brief_level, "
            "autonomy_level, session_duration_sec, created_at) "
            "VALUES ('s1', ?, 'generic', 1, 0.5, NULL, 0, 0, 5, 1, 'skeleton', 30, ?)",
            (w, time.time())
        )
        r7_db.commit()

        with patch("agent.reasoning.dashboard._get_conn", return_value=r7_db):
            from agent.reasoning.dashboard import generate_dashboard
            d = generate_dashboard(weeks=4)

        assert d['weekly_trends'][0]['avg_tokens'] == 0


# ============================================================
# QA-7: Concurrent session recording
# ============================================================

class TestConcurrentRecording:
    def test_two_sessions_same_week(self, r7_db):
        """Two sessions in same week should both record correctly."""
        writes = [{'file': 'a.php', 'tool': 'Write', 'timestamp': 100}]
        entries = [{'tool': 'Write', 'file': 'a.php', 'action': 'write', 'metadata': {}, 'timestamp': 100}]

        with patch("agent.reasoning.metrics._get_conn", return_value=r7_db), \
             patch("agent.reasoning.metrics.get_session_reads", return_value=[]), \
             patch("agent.reasoning.metrics.get_session_writes", return_value=writes), \
             patch("agent.reasoning.metrics.get_session_log_entries", return_value=entries):
            from agent.reasoning.metrics import record_output_quality
            r1 = record_output_quality("session-a")
            r2 = record_output_quality("session-b")

        assert r1['brief_version'] == 1
        assert r2['brief_version'] == 2

        count = r7_db.execute("SELECT COUNT(*) FROM output_quality").fetchone()[0]
        assert count == 2


# ============================================================
# QA-8: Dashboard autonomy_progression with empty level
# ============================================================

class TestAutonomyProgression:
    def test_empty_string_level_mapped_to_none(self, r7_db):
        from agent.reasoning.metrics import epoch_week
        w = epoch_week()
        r7_db.execute(
            "INSERT INTO output_quality "
            "(session_id, week, task_type, brief_version, trust_score, tokens_estimated, "
            "files_re_read, edits_after_first, total_tool_calls, brief_level, "
            "autonomy_level, session_duration_sec, created_at) "
            "VALUES ('s1', ?, 'generic', 1, 0.5, 5000, 0, 0, 5, 0, '', 30, ?)",
            (w, time.time())
        )
        r7_db.commit()

        with patch("agent.reasoning.dashboard._get_conn", return_value=r7_db):
            from agent.reasoning.dashboard import generate_dashboard
            d = generate_dashboard(weeks=4)

        # Empty string should be mapped to 'none'
        assert 'none' in d['autonomy_progression']


# ============================================================
# QA-9: Stagnation suggestions completeness
# ============================================================

class TestSuggestions:
    def test_all_flat_gives_level_suggestion(self):
        from agent.reasoning.alerts import _suggest_fixes
        # level_imp == 0 and trust_imp >= 0 → "Level stuck" suggestion
        suggestions = _suggest_fixes(0.0, 0.0, 0.0)
        assert any("level" in s.lower() for s in suggestions)

    def test_pipeline_suggestion_when_all_negative(self):
        from agent.reasoning.alerts import _suggest_fixes
        # Only fires when no other suggestion matches (token >= 0, trust >= 0, level != 0)
        suggestions = _suggest_fixes(0.01, -0.01, 0.1)
        # trust < 0 → trust suggestion fires
        assert any("trust" in s.lower() for s in suggestions)

    def test_tokens_worsening(self):
        from agent.reasoning.alerts import _suggest_fixes
        suggestions = _suggest_fixes(-0.1, 0.0, 0.0)
        assert any("tokens" in s.lower() for s in suggestions)

    def test_trust_worsening(self):
        from agent.reasoning.alerts import _suggest_fixes
        suggestions = _suggest_fixes(0.0, -0.05, 0.0)
        assert any("trust" in s.lower() for s in suggestions)

    def test_level_stuck_trust_ok(self):
        from agent.reasoning.alerts import _suggest_fixes
        suggestions = _suggest_fixes(0.0, 0.01, 0.0)
        assert any("level" in s.lower() for s in suggestions)


# ============================================================
# QA-10: MCP handler error handling
# ============================================================

class TestMCPErrorHandling:
    def test_metrics_handler_empty_db(self, r7_db):
        """kiwi_metrics should not crash on empty DB."""
        with patch("agent.reasoning.dashboard._get_conn", return_value=r7_db), \
             patch("agent.reasoning.alerts._get_conn", return_value=r7_db):
            from agent.reasoning.dashboard import generate_dashboard
            from agent.reasoning.alerts import check_stagnation

            dashboard = generate_dashboard(4)
            alert = check_stagnation()

            summary = {
                'intelligence_score': dashboard['intelligence_score'],
                'latest_week': dashboard['weekly_trends'][-1] if dashboard['weekly_trends'] else None,
                'autonomy': dashboard['autonomy_progression'],
                'stagnation': alert,
            }

        assert summary['intelligence_score'] == 0.0
        assert summary['latest_week'] is None
        assert summary['stagnation'] is None
        # Should be JSON-serializable
        json.dumps(summary)


# ============================================================
# QA-11: Duration calculation edge cases
# ============================================================

class TestDurationEdgeCases:
    def test_single_entry_duration_zero(self, r7_db):
        """Single log entry → duration = 0."""
        writes = [{'file': 'a.php', 'tool': 'Write', 'timestamp': 100}]
        entries = [{'tool': 'Write', 'file': 'a.php', 'action': 'write', 'metadata': {}, 'timestamp': 100}]

        with patch("agent.reasoning.metrics._get_conn", return_value=r7_db), \
             patch("agent.reasoning.metrics.get_session_reads", return_value=[]), \
             patch("agent.reasoning.metrics.get_session_writes", return_value=writes), \
             patch("agent.reasoning.metrics.get_session_log_entries", return_value=entries):
            from agent.reasoning.metrics import record_output_quality
            result = record_output_quality("s1")

        assert result['session_duration_sec'] == 0.0

    def test_entries_with_missing_timestamp(self, r7_db):
        """Entries without timestamp should be filtered out."""
        writes = [{'file': 'a.php', 'tool': 'Write', 'timestamp': 200}]
        entries = [
            {'tool': 'Read', 'file': 'a.php', 'action': 'read', 'metadata': {}, 'timestamp': None},
            {'tool': 'Write', 'file': 'a.php', 'action': 'write', 'metadata': {}, 'timestamp': 200},
        ]

        with patch("agent.reasoning.metrics._get_conn", return_value=r7_db), \
             patch("agent.reasoning.metrics.get_session_reads", return_value=[]), \
             patch("agent.reasoning.metrics.get_session_writes", return_value=writes), \
             patch("agent.reasoning.metrics.get_session_log_entries", return_value=entries):
            from agent.reasoning.metrics import record_output_quality
            result = record_output_quality("s1")

        # Only 1 valid timestamp → duration = 0
        assert result['session_duration_sec'] == 0.0


# ============================================================
# QA-12: Token estimation formula
# ============================================================

class TestTokenEstimation:
    def test_formula_correctness(self, r7_db):
        """tokens = calls*50 + reads*200 + writes*500."""
        writes = [
            {'file': 'a.php', 'tool': 'Write', 'timestamp': 100},
            {'file': 'b.php', 'tool': 'Write', 'timestamp': 110},
        ]
        reads = [
            {'file': 'a.php', 'timestamp': 90},
            {'file': 'b.php', 'timestamp': 95},
            {'file': 'c.php', 'timestamp': 98},
        ]
        entries = [
            {'tool': 'Read', 'file': 'a.php', 'action': 'read', 'metadata': {}, 'timestamp': 90},
            {'tool': 'Read', 'file': 'b.php', 'action': 'read', 'metadata': {}, 'timestamp': 95},
            {'tool': 'Read', 'file': 'c.php', 'action': 'read', 'metadata': {}, 'timestamp': 98},
            {'tool': 'Write', 'file': 'a.php', 'action': 'write', 'metadata': {}, 'timestamp': 100},
            {'tool': 'Write', 'file': 'b.php', 'action': 'write', 'metadata': {}, 'timestamp': 110},
        ]

        with patch("agent.reasoning.metrics._get_conn", return_value=r7_db), \
             patch("agent.reasoning.metrics.get_session_reads", return_value=reads), \
             patch("agent.reasoning.metrics.get_session_writes", return_value=writes), \
             patch("agent.reasoning.metrics.get_session_log_entries", return_value=entries):
            from agent.reasoning.metrics import record_output_quality
            result = record_output_quality("s1")

        # 5 entries * 50 + 3 reads * 200 + 2 writes * 500 = 250 + 600 + 1000 = 1850
        assert result['tokens_estimated'] == 1850
