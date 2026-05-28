"""R8 — Tests for Selective Thinking: gates, cache, budget, integration."""

import json
import sqlite3
import time
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.reasoning.session_logger import _get_conn, get_session_id
from agent.reasoning.think_cache import get_cached, save_cached, invalidate_cache
from agent.reasoning.think_prompts import get_prompt
from agent.reasoning.thinker import (
    should_think, think, _make_cache_key, _parse_response,
    ThinkResult, THINK_TRIGGERS, MAX_THINKS_PER_SESSION,
    _get_session_think_count,
)


@pytest.fixture(autouse=True)
def reset_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_reasoning.db"
    schema_path = Path(__file__).parent / "schema.sql"

    conn = sqlite3.connect(str(db_path))
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.commit()

    monkeypatch.setattr("agent.reasoning.session_logger.DB_PATH", db_path)
    monkeypatch.setattr("agent.reasoning.session_logger._conn", None)

    import agent.reasoning.thinker as thinker_mod
    thinker_mod._last_think_ts = 0.0

    yield conn
    conn.close()


@pytest.fixture
def mock_session_id(monkeypatch):
    monkeypatch.setattr("agent.reasoning.session_logger._session_id", "test-session-001")
    return "test-session-001"


class TestShouldThink:
    def test_unknown_trigger_returns_false(self, mock_session_id):
        assert should_think('unknown_trigger', {}) is False

    def test_no_anthropic_returns_false(self, monkeypatch, mock_session_id):
        monkeypatch.setattr("agent.reasoning.thinker._HAS_ANTHROPIC", False)
        ctx = {'patterns': [{'confidence': 0.8}, {'confidence': 0.75}]}
        assert should_think('pattern_conflict', ctx) is False

    def test_pattern_conflict_close_gap(self, mock_session_id, monkeypatch):
        monkeypatch.setattr("agent.reasoning.thinker._HAS_ANTHROPIC", True)
        ctx = {'patterns': [{'confidence': 0.8}, {'confidence': 0.75}]}
        assert should_think('pattern_conflict', ctx) is True

    def test_pattern_conflict_wide_gap(self, mock_session_id, monkeypatch):
        monkeypatch.setattr("agent.reasoning.thinker._HAS_ANTHROPIC", True)
        ctx = {'patterns': [{'confidence': 0.9}, {'confidence': 0.5}]}
        assert should_think('pattern_conflict', ctx) is False

    def test_pattern_conflict_single_pattern(self, mock_session_id, monkeypatch):
        monkeypatch.setattr("agent.reasoning.thinker._HAS_ANTHROPIC", True)
        ctx = {'patterns': [{'confidence': 0.8}]}
        assert should_think('pattern_conflict', ctx) is False

    def test_borderline_trust_near_threshold(self, mock_session_id, monkeypatch):
        monkeypatch.setattr("agent.reasoning.thinker._HAS_ANTHROPIC", True)
        ctx = {'trust_score': 0.58, 'threshold': 0.6}
        assert should_think('borderline_trust', ctx) is True

    def test_borderline_trust_far_from_threshold(self, mock_session_id, monkeypatch):
        monkeypatch.setattr("agent.reasoning.thinker._HAS_ANTHROPIC", True)
        ctx = {'trust_score': 0.45, 'threshold': 0.6}
        assert should_think('borderline_trust', ctx) is False

    def test_novel_validation_enough_occurrences(self, mock_session_id, monkeypatch):
        monkeypatch.setattr("agent.reasoning.thinker._HAS_ANTHROPIC", True)
        ctx = {'times_seen': 3}
        assert should_think('novel_validation', ctx) is True

    def test_novel_validation_too_few(self, mock_session_id, monkeypatch):
        monkeypatch.setattr("agent.reasoning.thinker._HAS_ANTHROPIC", True)
        ctx = {'times_seen': 2}
        assert should_think('novel_validation', ctx) is False

    def test_style_ambiguity_no_knowledge(self, mock_session_id, monkeypatch):
        monkeypatch.setattr("agent.reasoning.thinker._HAS_ANTHROPIC", True)
        ctx = {'style_knowledge_count': 0}
        assert should_think('style_ambiguity', ctx) is True

    def test_style_ambiguity_has_knowledge(self, mock_session_id, monkeypatch):
        monkeypatch.setattr("agent.reasoning.thinker._HAS_ANTHROPIC", True)
        ctx = {'style_knowledge_count': 5}
        assert should_think('style_ambiguity', ctx) is False

    def test_cooldown_blocks(self, mock_session_id, monkeypatch):
        monkeypatch.setattr("agent.reasoning.thinker._HAS_ANTHROPIC", True)
        import agent.reasoning.thinker as t
        t._last_think_ts = time.time()
        ctx = {'patterns': [{'confidence': 0.8}, {'confidence': 0.75}]}
        assert should_think('pattern_conflict', ctx) is False

    def test_budget_blocks_after_max(self, mock_session_id, monkeypatch, reset_db):
        monkeypatch.setattr("agent.reasoning.thinker._HAS_ANTHROPIC", True)
        conn = _get_conn()
        for i in range(MAX_THINKS_PER_SESSION):
            conn.execute(
                "INSERT INTO think_events (session_id, trigger, tokens_used, cached, created_at) "
                "VALUES (?, 'pattern_conflict', 100, 0, ?)",
                ("test-session-001", time.time()),
            )
        conn.commit()
        ctx = {'patterns': [{'confidence': 0.8}, {'confidence': 0.75}]}
        assert should_think('pattern_conflict', ctx) is False


class TestThinkCache:
    def test_save_and_get(self, reset_db):
        save_cached("key1", "pattern_conflict", "hero", "theme1", {
            'decision': 'use_pattern_0',
            'reasoning': 'better fit',
            'confidence': 0.85,
        })
        result = get_cached("key1", "pattern_conflict")
        assert result is not None
        assert result['decision'] == 'use_pattern_0'
        assert result['confidence'] == 0.85

    def test_expired_returns_none(self, reset_db):
        conn = _get_conn()
        conn.execute(
            "INSERT INTO think_cache (cache_key, trigger, task_type, theme, decision, reasoning, confidence, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("old_key", "pattern_conflict", "hero", "t1", "d", "r", 0.5, time.time() - 7200),
        )
        conn.commit()
        result = get_cached("old_key", "pattern_conflict")
        assert result is None

    def test_invalidate_by_theme(self, reset_db):
        save_cached("k1", "pattern_conflict", "hero", "theme_a", {
            'decision': 'd', 'reasoning': 'r', 'confidence': 0.5,
        })
        save_cached("k2", "pattern_conflict", "hero", "theme_b", {
            'decision': 'd', 'reasoning': 'r', 'confidence': 0.5,
        })
        invalidate_cache(theme="theme_a")
        assert get_cached("k1", "pattern_conflict") is None
        assert get_cached("k2", "pattern_conflict") is not None

    def test_extra_field_roundtrip(self, reset_db):
        save_cached("k_extra", "style_ambiguity", "bootstrap", "new_theme", {
            'decision': 'inferred',
            'reasoning': 'from industry',
            'confidence': 0.8,
            'extra': {'tokens': {'radius': 'lg', 'shadow': 'md'}},
        })
        result = get_cached("k_extra", "style_ambiguity")
        assert result['extra'] == {'tokens': {'radius': 'lg', 'shadow': 'md'}}


class TestThinkPrompts:
    def test_pattern_conflict_prompt(self):
        ctx = {
            'n': 2,
            'task_type': 'hero_component',
            'patterns_desc': 'Pattern A: full-width\nPattern B: contained',
            'theme': 'beauty-shop',
            'industry': 'beauty',
            'style_summary': 'rounded-lg, shadow-sm',
        }
        prompt = get_prompt('pattern_conflict', ctx)
        assert prompt is not None
        assert 'hero_component' in prompt
        assert 'beauty' in prompt

    def test_borderline_trust_prompt(self):
        ctx = {
            'task_type': 'checkout_page',
            'theme': 'my-theme',
            'trust_score': 0.58,
            'threshold': 0.6,
            'signals': 'penalty=0.05',
        }
        prompt = get_prompt('borderline_trust', ctx)
        assert 'checkout_page' in prompt
        assert '0.58' in prompt

    def test_missing_key_returns_none(self):
        assert get_prompt('pattern_conflict', {'n': 2}) is None

    def test_unknown_trigger_returns_none(self):
        assert get_prompt('nonexistent', {}) is None


class TestCacheKey:
    def test_different_patterns_different_keys(self):
        ctx1 = {'patterns': [{'confidence': 0.8}, {'confidence': 0.7}]}
        ctx2 = {'patterns': [{'confidence': 0.9}, {'confidence': 0.85}]}
        assert _make_cache_key('pattern_conflict', ctx1) != _make_cache_key('pattern_conflict', ctx2)

    def test_same_input_same_key(self):
        ctx = {'patterns': [{'confidence': 0.8}, {'confidence': 0.7}]}
        assert _make_cache_key('pattern_conflict', ctx) == _make_cache_key('pattern_conflict', ctx)

    def test_borderline_rounds_trust(self):
        ctx1 = {'trust_score': 0.581}
        ctx2 = {'trust_score': 0.584}
        assert _make_cache_key('borderline_trust', ctx1) == _make_cache_key('borderline_trust', ctx2)

    def test_novel_uses_pattern_text(self):
        ctx1 = {'pattern': 'wz_component("hero")'}
        ctx2 = {'pattern': 'wz_component("footer")'}
        assert _make_cache_key('novel_validation', ctx1) != _make_cache_key('novel_validation', ctx2)


class TestParseResponse:
    def test_valid_json(self):
        response = '{"decision": "0", "reasoning": "better fit", "confidence": 0.85}'
        result = _parse_response('pattern_conflict', response, 42)
        assert result.decision == '0'
        assert result.confidence == 0.85
        assert result.tokens_used == 42

    def test_style_ambiguity_extracts_tokens(self):
        response = json.dumps({
            'decision': 'inferred',
            'reasoning': 'beauty industry',
            'confidence': 0.8,
            'tokens': {'radius': 'xl', 'spacing_base': '6', 'container': '7xl', 'shadow': 'lg'},
        })
        result = _parse_response('style_ambiguity', response, 55)
        assert result.extra == {'tokens': {'radius': 'xl', 'spacing_base': '6', 'container': '7xl', 'shadow': 'lg'}}

    def test_invalid_json_fallback(self):
        response = "I think pattern 0 is better because it matches the industry."
        result = _parse_response('pattern_conflict', response, 30)
        assert result.confidence == 0.3
        assert result.tokens_used == 30
        assert len(result.decision) <= 100


class TestThinkIntegration:
    @patch("agent.reasoning.thinker._call_haiku")
    def test_think_calls_haiku_and_caches(self, mock_haiku, mock_session_id, monkeypatch, reset_db):
        monkeypatch.setattr("agent.reasoning.thinker._HAS_ANTHROPIC", True)
        mock_haiku.return_value = ('{"decision": "0", "reasoning": "fits", "confidence": 0.9}', 45)

        ctx = {
            'patterns': [{'confidence': 0.8}, {'confidence': 0.75}],
            'task_type': 'hero',
            'theme': 'test',
            'n': 2,
            'patterns_desc': 'Pattern A: full-width\nPattern B: contained',
            'industry': 'beauty',
            'style_summary': 'rounded-lg',
        }
        result = think('pattern_conflict', ctx)

        assert result is not None
        assert result.decision == '0'
        assert result.tokens_used == 45
        assert not result.cached
        mock_haiku.assert_called_once()

        # Second call should hit cache
        import agent.reasoning.thinker as t
        t._last_think_ts = 0.0
        result2 = think('pattern_conflict', ctx)
        assert result2 is not None
        assert result2.cached is True
        assert result2.tokens_used == 0

    @patch("agent.reasoning.thinker._call_haiku")
    def test_think_returns_none_on_api_failure(self, mock_haiku, mock_session_id, monkeypatch, reset_db):
        monkeypatch.setattr("agent.reasoning.thinker._HAS_ANTHROPIC", True)
        mock_haiku.side_effect = Exception("API timeout")

        ctx = {
            'patterns': [{'confidence': 0.8}, {'confidence': 0.75}],
            'task_type': 'hero',
            'theme': 'test',
            'n': 2,
            'patterns_desc': 'A vs B',
            'industry': 'tech',
            'style_summary': 'rounded-md',
        }
        result = think('pattern_conflict', ctx)
        assert result is None

    @patch("agent.reasoning.thinker._call_haiku")
    def test_think_logs_event(self, mock_haiku, mock_session_id, monkeypatch, reset_db):
        monkeypatch.setattr("agent.reasoning.thinker._HAS_ANTHROPIC", True)
        mock_haiku.return_value = ('{"decision": "generate", "reasoning": "ok", "confidence": 0.8}', 30)

        ctx = {
            'trust_score': 0.58,
            'threshold': 0.6,
            'task_type': 'checkout',
            'theme': 'shop',
            'signals': 'penalty=0.05',
        }
        think('borderline_trust', ctx)

        conn = _get_conn()
        row = conn.execute("SELECT trigger, decision, tokens_used FROM think_events").fetchone()
        assert row[0] == 'borderline_trust'
        assert row[1] == 'generate'
        assert row[2] == 30


class TestSessionBudget:
    def test_count_excludes_cached(self, mock_session_id, reset_db):
        conn = _get_conn()
        conn.execute(
            "INSERT INTO think_events (session_id, trigger, tokens_used, cached, created_at) "
            "VALUES (?, 'x', 100, 0, ?)", ("test-session-001", time.time()),
        )
        conn.execute(
            "INSERT INTO think_events (session_id, trigger, tokens_used, cached, created_at) "
            "VALUES (?, 'y', 0, 1, ?)", ("test-session-001", time.time()),
        )
        conn.commit()
        assert _get_session_think_count("test-session-001") == 1

    def test_count_per_session(self, reset_db):
        conn = _get_conn()
        conn.execute(
            "INSERT INTO think_events (session_id, trigger, tokens_used, cached, created_at) "
            "VALUES ('other-session', 'x', 100, 0, ?)", (time.time(),),
        )
        conn.commit()
        assert _get_session_think_count("test-session-001") == 0


class TestMigration:
    def test_migration_creates_tables(self, tmp_path, monkeypatch):
        db_path = tmp_path / "migrate_test.db"

        # Create DB with only base tables (no R8 tables)
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS session_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                tool TEXT NOT NULL,
                file_path TEXT,
                action TEXT,
                metadata TEXT,
                timestamp REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                started_at REAL,
                ended_at REAL,
                task_hint TEXT,
                files_read INTEGER DEFAULT 0,
                files_written INTEGER DEFAULT 0,
                theme_path TEXT,
                processed INTEGER DEFAULT 0
            );
        """)
        conn.close()

        monkeypatch.setattr("agent.reasoning.session_logger.DB_PATH", db_path)
        monkeypatch.setattr("agent.reasoning.session_logger._conn", None)

        new_conn = _get_conn()
        tables = [r[0] for r in new_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'think%'"
        ).fetchall()]
        assert 'think_events' in tables
        assert 'think_cache' in tables
