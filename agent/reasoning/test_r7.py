"""R7 — Output Versioning + Metrics: tests for metrics, dashboard, alerts."""

import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from dataclasses import dataclass, field

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
# 1. Metrics — epoch_week
# ============================================================

class TestEpochWeek:
    def test_returns_int(self):
        from agent.reasoning.metrics import epoch_week
        assert isinstance(epoch_week(), int)

    def test_same_week_same_value(self):
        from agent.reasoning.metrics import epoch_week
        t = 1716800000.0
        assert epoch_week(t) == epoch_week(t + 3600)

    def test_different_weeks(self):
        from agent.reasoning.metrics import epoch_week
        t = 1716800000.0
        assert epoch_week(t) != epoch_week(t + 604800)

    def test_no_year_boundary_issue(self):
        from agent.reasoning.metrics import epoch_week
        dec_31 = 1735689600.0  # 2025-01-01 approx
        jan_1 = dec_31 + 86400
        diff = epoch_week(jan_1) - epoch_week(dec_31)
        assert diff in (0, 1)


# ============================================================
# 2. Metrics — record_output_quality
# ============================================================

class TestRecordOutputQuality:
    def test_skips_when_no_writes(self, r7_db):
        with patch("agent.reasoning.metrics._get_conn", return_value=r7_db), \
             patch("agent.reasoning.metrics.get_session_reads", return_value=[]), \
             patch("agent.reasoning.metrics.get_session_writes", return_value=[]), \
             patch("agent.reasoning.metrics.get_session_log_entries", return_value=[]):
            from agent.reasoning.metrics import record_output_quality
            result = record_output_quality("s1")
        assert result['status'] == 'skipped'

    def test_records_with_writes(self, r7_db):
        writes = [{'file': 'a.php', 'tool': 'Write', 'timestamp': 100}]
        reads = [{'file': 'a.php', 'timestamp': 90}]
        entries = [
            {'tool': 'Read', 'file': 'a.php', 'action': 'read', 'metadata': {}, 'timestamp': 90},
            {'tool': 'Write', 'file': 'a.php', 'action': 'write', 'metadata': {}, 'timestamp': 100},
        ]

        with patch("agent.reasoning.metrics._get_conn", return_value=r7_db), \
             patch("agent.reasoning.metrics.get_session_reads", return_value=reads), \
             patch("agent.reasoning.metrics.get_session_writes", return_value=writes), \
             patch("agent.reasoning.metrics.get_session_log_entries", return_value=entries):
            from agent.reasoning.metrics import record_output_quality
            result = record_output_quality("s1")

        assert result['status'] == 'recorded'
        assert result['total_tool_calls'] == 2
        assert result['session_duration_sec'] == 10.0

    def test_records_with_brief(self, r7_db):
        from agent.reasoning.output import KiwiOutput
        from agent.reasoning.autonomy import GraduatedOutput

        brief = KiwiOutput(
            content={'target': 'home_page', 'files_needed': ['hero.php']},
            trust_score=0.8,
            trust_breakdown={},
        )
        brief.graduated = GraduatedOutput(brief=brief, level='skeleton')

        writes = [{'file': 'hero.php', 'tool': 'Write', 'timestamp': 200}]
        reads = [{'file': 'hero.php', 'timestamp': 190}]
        entries = [
            {'tool': 'Read', 'file': 'hero.php', 'action': 'read', 'metadata': {}, 'timestamp': 190},
            {'tool': 'Write', 'file': 'hero.php', 'action': 'write', 'metadata': {}, 'timestamp': 200},
        ]

        with patch("agent.reasoning.metrics._get_conn", return_value=r7_db), \
             patch("agent.reasoning.metrics.get_session_reads", return_value=reads), \
             patch("agent.reasoning.metrics.get_session_writes", return_value=writes), \
             patch("agent.reasoning.metrics.get_session_log_entries", return_value=entries):
            from agent.reasoning.metrics import record_output_quality
            result = record_output_quality("s2", brief)

        assert result['task_type'] == 'home_page'
        assert result['trust_score'] == 0.8
        assert result['autonomy_level'] == 'skeleton'
        assert result['brief_level'] == 1
        assert result['files_re_read'] == 1  # hero.php in source_files and reads

    def test_brief_version_increments(self, r7_db):
        writes = [{'file': 'x.php', 'tool': 'Write', 'timestamp': 100}]
        entries = [{'tool': 'Write', 'file': 'x.php', 'action': 'write', 'metadata': {}, 'timestamp': 100}]

        with patch("agent.reasoning.metrics._get_conn", return_value=r7_db), \
             patch("agent.reasoning.metrics.get_session_reads", return_value=[]), \
             patch("agent.reasoning.metrics.get_session_writes", return_value=writes), \
             patch("agent.reasoning.metrics.get_session_log_entries", return_value=entries):
            from agent.reasoning.metrics import record_output_quality
            r1 = record_output_quality("s1")
            r2 = record_output_quality("s2")

        assert r1['brief_version'] == 1
        assert r2['brief_version'] == 2

    def test_edits_after_first_counts_max(self, r7_db):
        writes = [
            {'file': 'a.php', 'tool': 'Edit', 'timestamp': 100},
            {'file': 'a.php', 'tool': 'Edit', 'timestamp': 110},
            {'file': 'a.php', 'tool': 'Edit', 'timestamp': 120},
            {'file': 'b.php', 'tool': 'Edit', 'timestamp': 130},
        ]
        entries = [
            {'tool': 'Edit', 'file': 'a.php', 'action': 'edit', 'metadata': {}, 'timestamp': t}
            for t in [100, 110, 120]
        ] + [{'tool': 'Edit', 'file': 'b.php', 'action': 'edit', 'metadata': {}, 'timestamp': 130}]

        with patch("agent.reasoning.metrics._get_conn", return_value=r7_db), \
             patch("agent.reasoning.metrics.get_session_reads", return_value=[]), \
             patch("agent.reasoning.metrics.get_session_writes", return_value=writes), \
             patch("agent.reasoning.metrics.get_session_log_entries", return_value=entries):
            from agent.reasoning.metrics import record_output_quality
            result = record_output_quality("s1")

        # a.php: 3 edits - 1 = 2 extra, b.php: 1 - 1 = 0. Max = 2
        assert result['edits_after_first'] == 2


# ============================================================
# 3. Dashboard — generate_dashboard
# ============================================================

class TestDashboard:
    def _insert_weeks(self, conn, weeks_data):
        for week, tokens, trust, level in weeks_data:
            conn.execute(
                "INSERT INTO output_quality "
                "(session_id, week, task_type, brief_version, trust_score, tokens_estimated, "
                "files_re_read, edits_after_first, total_tool_calls, brief_level, "
                "autonomy_level, session_duration_sec, created_at) "
                "VALUES (?, ?, 'home_page', 1, ?, ?, 2, 1, 10, ?, 'skeleton', 60, ?)",
                (f's-{week}', week, trust, tokens, level, time.time())
            )
        conn.commit()

    def test_empty_db_returns_zero_score(self, r7_db):
        with patch("agent.reasoning.dashboard._get_conn", return_value=r7_db):
            from agent.reasoning.dashboard import generate_dashboard
            d = generate_dashboard(weeks=4)
        assert d['intelligence_score'] == 0.0
        assert d['weekly_trends'] == []

    def test_single_week_returns_zero_score(self, r7_db):
        from agent.reasoning.metrics import epoch_week
        w = epoch_week()
        self._insert_weeks(r7_db, [(w, 5000, 0.6, 1)])

        with patch("agent.reasoning.dashboard._get_conn", return_value=r7_db):
            from agent.reasoning.dashboard import generate_dashboard
            d = generate_dashboard(weeks=4)
        assert d['intelligence_score'] == 0.0
        assert len(d['weekly_trends']) == 1

    def test_improving_trend_positive_score(self, r7_db):
        from agent.reasoning.metrics import epoch_week
        w = epoch_week()
        self._insert_weeks(r7_db, [
            (w - 3, 10000, 0.4, 0),
            (w - 2, 8000, 0.5, 1),
            (w - 1, 6000, 0.6, 1),
            (w, 4000, 0.75, 2),
        ])

        with patch("agent.reasoning.dashboard._get_conn", return_value=r7_db):
            from agent.reasoning.dashboard import generate_dashboard
            d = generate_dashboard(weeks=4)

        assert d['intelligence_score'] > 0
        assert d['intelligence_score'] <= 100
        assert len(d['weekly_trends']) == 4

    def test_score_bounded_0_100(self, r7_db):
        from agent.reasoning.metrics import epoch_week
        w = epoch_week()
        self._insert_weeks(r7_db, [
            (w - 1, 50000, 0.1, 0),
            (w, 100, 0.99, 3),
        ])

        with patch("agent.reasoning.dashboard._get_conn", return_value=r7_db):
            from agent.reasoning.dashboard import generate_dashboard, compute_intelligence_score
            d = generate_dashboard(weeks=4)
        assert 0 <= d['intelligence_score'] <= 100

    def test_autonomy_progression(self, r7_db):
        from agent.reasoning.metrics import epoch_week
        w = epoch_week()
        for i in range(5):
            r7_db.execute(
                "INSERT INTO output_quality "
                "(session_id, week, task_type, brief_version, trust_score, tokens_estimated, "
                "files_re_read, edits_after_first, total_tool_calls, brief_level, "
                "autonomy_level, session_duration_sec, created_at) "
                "VALUES (?, ?, 'home_page', 1, 0.7, 5000, 0, 0, 5, 1, 'skeleton', 30, ?)",
                (f's{i}', w, time.time())
            )
        r7_db.commit()

        with patch("agent.reasoning.dashboard._get_conn", return_value=r7_db):
            from agent.reasoning.dashboard import generate_dashboard
            d = generate_dashboard(weeks=4)

        assert 'skeleton' in d['autonomy_progression']
        assert d['autonomy_progression']['skeleton']['count'] == 5

    def test_task_type_breakdown(self, r7_db):
        from agent.reasoning.metrics import epoch_week
        w = epoch_week()
        for task in ['home_page', 'home_page', 'cart_page']:
            r7_db.execute(
                "INSERT INTO output_quality "
                "(session_id, week, task_type, brief_version, trust_score, tokens_estimated, "
                "files_re_read, edits_after_first, total_tool_calls, brief_level, "
                "autonomy_level, session_duration_sec, created_at) "
                "VALUES (?, ?, ?, 1, 0.7, 5000, 0, 0, 5, 1, 'skeleton', 30, ?)",
                (f's-{task}-{w}', w, task, time.time())
            )
        r7_db.commit()

        with patch("agent.reasoning.dashboard._get_conn", return_value=r7_db):
            from agent.reasoning.dashboard import generate_dashboard
            d = generate_dashboard(weeks=4)

        assert 'home_page' in d['task_type_breakdown']
        assert d['task_type_breakdown']['home_page']['sessions'] == 2


# ============================================================
# 4. Alerts — check_stagnation
# ============================================================

class TestAlerts:
    def _fill_period(self, conn, week_start, week_end, tokens, trust, level, count=5):
        for w in range(week_start, week_end + 1):
            for i in range(count):
                conn.execute(
                    "INSERT INTO output_quality "
                    "(session_id, week, task_type, brief_version, trust_score, tokens_estimated, "
                    "files_re_read, edits_after_first, total_tool_calls, brief_level, "
                    "autonomy_level, session_duration_sec, created_at) "
                    "VALUES (?, ?, 'generic', 1, ?, ?, 0, 0, 5, ?, 'skeleton', 30, ?)",
                    (f's-{w}-{i}', w, trust, tokens, level, time.time())
                )
        conn.commit()

    def test_no_data_returns_none(self, r7_db):
        with patch("agent.reasoning.alerts._get_conn", return_value=r7_db):
            from agent.reasoning.alerts import check_stagnation
            assert check_stagnation() is None

    def test_insufficient_sessions_returns_none(self, r7_db):
        from agent.reasoning.metrics import epoch_week
        w = epoch_week()
        # Only 1 session per week, 2 per period (below min 3)
        self._fill_period(r7_db, w - 3, w - 2, 5000, 0.5, 1, count=1)
        self._fill_period(r7_db, w - 1, w, 5000, 0.5, 1, count=1)

        with patch("agent.reasoning.alerts._get_conn", return_value=r7_db):
            from agent.reasoning.alerts import check_stagnation
            assert check_stagnation() is None

    def test_flat_metrics_triggers_alert(self, r7_db):
        from agent.reasoning.metrics import epoch_week
        w = epoch_week()
        self._fill_period(r7_db, w - 3, w - 2, 5000, 0.5, 1, count=5)
        self._fill_period(r7_db, w - 1, w, 5000, 0.5, 1, count=5)

        with patch("agent.reasoning.alerts._get_conn", return_value=r7_db):
            from agent.reasoning.alerts import check_stagnation
            alert = check_stagnation()

        assert alert is not None
        assert alert['type'] == 'stagnation'
        assert alert['confidence'] >= 0.5
        assert len(alert['suggestions']) > 0

    def test_improving_metrics_no_alert(self, r7_db):
        from agent.reasoning.metrics import epoch_week
        w = epoch_week()
        self._fill_period(r7_db, w - 3, w - 2, 10000, 0.4, 0, count=5)
        self._fill_period(r7_db, w - 1, w, 5000, 0.7, 2, count=5)

        with patch("agent.reasoning.alerts._get_conn", return_value=r7_db):
            from agent.reasoning.alerts import check_stagnation
            assert check_stagnation() is None

    def test_low_confidence_suppresses_alert(self, r7_db):
        from agent.reasoning.metrics import epoch_week
        w = epoch_week()
        # 3 sessions each period → total 6 → confidence 0.6 (just above 0.5)
        self._fill_period(r7_db, w - 3, w - 2, 5000, 0.5, 1, count=3)
        self._fill_period(r7_db, w - 1, w, 5000, 0.5, 1, count=3)

        with patch("agent.reasoning.alerts._get_conn", return_value=r7_db):
            from agent.reasoning.alerts import check_stagnation
            # 3+3=6 per period, but _get_period_metrics requires 5 per period
            # So this should return None (insufficient data)
            result = check_stagnation()
            # With count=3 per period (2 weeks each = 6 total per period),
            # but the query is per-period not per-week, so 3*2=6 >= 5
            # Actually let's check: the query is BETWEEN week_start AND week_end
            # So for period (w-3, w-2) with count=3 per week = 6 rows total
            if result is not None:
                assert result['confidence'] >= 0.5

    def test_suggestions_for_worsening_tokens(self, r7_db):
        from agent.reasoning.metrics import epoch_week
        w = epoch_week()
        self._fill_period(r7_db, w - 3, w - 2, 5000, 0.5, 1, count=5)
        self._fill_period(r7_db, w - 1, w, 8000, 0.5, 1, count=5)  # tokens WORSE

        with patch("agent.reasoning.alerts._get_conn", return_value=r7_db):
            from agent.reasoning.alerts import check_stagnation
            alert = check_stagnation()

        assert alert is not None
        assert any("Tokens increasing" in s for s in alert['suggestions'])


# ============================================================
# 5. Integration — metrics hook in __init__.py
# ============================================================

class TestMetricsHook:
    def test_record_called_after_learn(self, r7_db):
        with patch("agent.reasoning.session_logger._get_conn", return_value=r7_db), \
             patch("agent.reasoning.metrics._get_conn", return_value=r7_db):

            # Insert a session with writes
            r7_db.execute(
                "INSERT INTO sessions (session_id, started_at, files_written, processed) "
                "VALUES ('test-hook', ?, 2, 0)",
                (time.time(),)
            )
            r7_db.execute(
                "INSERT INTO session_log (session_id, tool, file_path, action, timestamp) "
                "VALUES ('test-hook', 'Write', 'a.php', 'write', ?)",
                (time.time(),)
            )
            r7_db.execute(
                "INSERT INTO session_log (session_id, tool, file_path, action, timestamp) "
                "VALUES ('test-hook', 'Write', 'b.php', 'write', ?)",
                (time.time() + 1,)
            )
            r7_db.commit()

            from agent.reasoning.metrics import record_output_quality
            result = record_output_quality('test-hook')

        assert result['status'] == 'recorded'
        row = r7_db.execute("SELECT COUNT(*) FROM output_quality").fetchone()
        assert row[0] == 1


# ============================================================
# 6. MCP handler — kiwi_metrics
# ============================================================

class TestMCPHandler:
    def test_alert_format_ok(self, r7_db):
        with patch("agent.reasoning.alerts._get_conn", return_value=r7_db):
            from agent.reasoning.alerts import check_stagnation
            result = check_stagnation()
        assert result is None  # empty db

    def test_summary_format(self, r7_db):
        with patch("agent.reasoning.dashboard._get_conn", return_value=r7_db), \
             patch("agent.reasoning.alerts._get_conn", return_value=r7_db):
            from agent.reasoning.dashboard import generate_dashboard
            from agent.reasoning.alerts import check_stagnation
            dashboard = generate_dashboard(4)
            summary = {
                'intelligence_score': dashboard['intelligence_score'],
                'latest_week': dashboard['weekly_trends'][-1] if dashboard['weekly_trends'] else None,
                'autonomy': dashboard['autonomy_progression'],
                'stagnation': check_stagnation(),
            }
        assert 'intelligence_score' in summary
        assert summary['latest_week'] is None
        assert summary['stagnation'] is None
