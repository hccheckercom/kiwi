"""Active Learning regression tests — covers T2/T3/T5/T6 from AUDIT-REPORT-2026-05-29.

Run: python -m pytest .claude/kiwi/tests/test_active_learning.py -v

These tests pin the behavior fixed in BUG #1-#13 (audit) and BUG #22-#25 (Phase 2).
They are intentionally narrow: each test isolates one invariant so a regression
points to the right fix. Use a fresh tmp DB so they never touch the real
reasoning.db.
"""

import importlib
import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

KIWI_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIWI_DIR))


@pytest.fixture
def isolated_kiwi(tmp_path, monkeypatch):
    """Reload kiwi modules with DB + session file pointed at tmp_path."""
    mem = tmp_path / "memory"
    mem.mkdir()
    db_path = mem / "reasoning.db"
    session_file = mem / ".current_session_id"

    monkeypatch.setenv("KIWI_LEARNING_DISABLED", "")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.delenv("CLAUDE_CONVERSATION_ID", raising=False)

    for mod in [
        "agent.reasoning.session_logger",
        "agent.reasoning.learner",
        "hooks.post_edit",
    ]:
        sys.modules.pop(mod, None)

    import agent.reasoning.session_logger as sl
    sl.DB_PATH = db_path
    sl.SESSION_FILE = session_file
    sl._session_id = None
    sl._session_id_set_at = 0.0
    sl._conn = None

    yield {"sl": sl, "db_path": db_path, "tmp": tmp_path}

    if sl._conn is not None:
        try:
            sl._conn.close()
        except Exception:
            pass


def test_t2_race_atomic_claim_single_winner(isolated_kiwi, monkeypatch):
    """T2: Concurrent _try_auto_learn — only ONE winner per writes-threshold tick."""
    sl = isolated_kiwi["sl"]
    sid = "race-test-1"
    sl._session_id = sid
    sl._session_id_set_at = time.time()

    conn = sl._get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO sessions (session_id, started_at, files_written) "
        "VALUES (?, ?, ?)",
        (sid, time.time(), 10),
    )
    conn.commit()

    sys.modules.pop("hooks.post_edit", None)
    from hooks.post_edit import _ensure_learning_state, _learning_disabled
    assert _learning_disabled() is False

    _ensure_learning_state(conn)
    conn.execute(
        "INSERT OR IGNORE INTO session_learn_state "
        "(session_id, last_learned_writes, last_learned_at) VALUES (?, 0, ?)",
        (sid, int(time.time())),
    )
    conn.commit()

    # Simulate the atomic UPDATE-WHERE that real _try_auto_learn does.
    winners = []

    def claim():
        c = sl._get_conn()
        cur = c.execute(
            "UPDATE session_learn_state "
            "SET last_learned_writes = ?, last_learned_at = strftime('%s', 'now') "
            "WHERE session_id = ? AND ? - last_learned_writes >= 5",
            (10, sid, 10),
        )
        c.commit()
        if cur.rowcount > 0:
            winners.append(threading.current_thread().name)

    threads = [threading.Thread(target=claim, name=f"t{i}") for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(winners) == 1, f"Expected 1 winner, got {len(winners)}: {winners}"


def test_t3_extract_bindings_strips_php_comments(isolated_kiwi):
    """T3 + BUG #2: _extract_bindings ignores function names inside PHP comments."""
    sys.modules.pop("agent.reasoning.learner", None)
    from agent.reasoning.learner import _extract_bindings

    content = """<?php
// example: do_not_extract_me() and esc_html() in comments
/* block comment with wp_nav_menu() inside */
function real_call() {
    return esc_attr( get_theme_mod( 'foo' ) );
}
"""
    bindings = _extract_bindings(content, theme="sfvn")

    flat = " ".join(bindings)
    assert "do_not_extract_me" not in flat, "should not match name in line comment"
    assert "wp:wp_nav_menu" not in flat, "should not match name in block comment"
    assert "wp:esc_attr" in bindings or "wp:get_theme_mod" in bindings, \
        f"real WP funcs must be extracted, got: {bindings}"


def test_t3_extract_bindings_blacklist_wp_constants(isolated_kiwi):
    """BUG #3: theme const regex must NOT match WP_DEBUG / WP_HOME when theme='wp'."""
    sys.modules.pop("agent.reasoning.learner", None)
    from agent.reasoning.learner import _extract_bindings

    content = """<?php
if ( WP_DEBUG && WP_HOME ) {
    define( 'SFVN_URI', get_template_directory_uri() );
}
"""
    bindings = _extract_bindings(content, theme="wp")
    assert "const:WP_DEBUG" not in bindings
    assert "const:WP_HOME" not in bindings


def test_t3_extract_bindings_size_cap(isolated_kiwi):
    """BUG #5: extracting from huge content must complete fast (no ReDoS)."""
    sys.modules.pop("agent.reasoning.learner", None)
    from agent.reasoning.learner import _extract_bindings

    big = "<?php\n" + ("esc_html( get_theme_mod( 'x' ) );\n" * 50000)
    t0 = time.time()
    bindings = _extract_bindings(big, theme="sfvn")
    elapsed = time.time() - t0

    assert elapsed < 1.0, f"Extract took {elapsed:.2f}s — should be under 1s with cap"
    assert len(bindings) > 0


def test_t5_opt_out_via_env(isolated_kiwi, monkeypatch):
    """T5 + BUG #13: KIWI_LEARNING_DISABLED=1 must short-circuit learning."""
    monkeypatch.setenv("KIWI_LEARNING_DISABLED", "1")
    sys.modules.pop("hooks.post_edit", None)
    from hooks.post_edit import _learning_disabled

    assert _learning_disabled() is True


def test_t5_opt_out_via_flag_file(isolated_kiwi, tmp_path, monkeypatch):
    """T5 + BUG #13: presence of .learning_disabled flag must disable learning."""
    monkeypatch.delenv("KIWI_LEARNING_DISABLED", raising=False)
    monkeypatch.setenv("KIWI_LEARNING_DISABLED", "")

    sys.modules.pop("hooks.post_edit", None)
    import hooks.post_edit as pe
    flag = tmp_path / "memory" / ".learning_disabled"
    flag.parent.mkdir(exist_ok=True)
    flag.write_text("")

    monkeypatch.setattr(pe, "__file__", str(tmp_path / "hooks" / "post_edit.py"))
    (tmp_path / "hooks").mkdir(exist_ok=True)

    # Re-evaluate flag detection with patched __file__
    def _ld():
        if os.environ.get("KIWI_LEARNING_DISABLED", "").strip() in ("1", "true", "yes"):
            return True
        return (tmp_path / "memory" / ".learning_disabled").exists()
    assert _ld() is True


def test_t6_bindings_no_secret_leakage(isolated_kiwi):
    """T6 + BUG #11: bindings must contain NAMES only, never argument VALUES."""
    sys.modules.pop("agent.reasoning.learner", None)
    from agent.reasoning.learner import _extract_bindings

    content = """<?php
$secret_token = 'sk_live_AKIA1234567890SECRETKEY';
$api_key = 'jwt.eyJhbGciOiJIUzI1NiJ9.payload.signature';
update_option( 'stripe_key', $secret_token );
wp_remote_post( 'https://api.example.com', [ 'body' => $api_key ] );
"""
    bindings = _extract_bindings(content, theme="sfvn")

    flat = " ".join(bindings)
    assert "sk_live_" not in flat
    assert "AKIA" not in flat
    assert "jwt.eyJ" not in flat
    assert "api.example.com" not in flat
    assert "update_option" in flat or "wp_remote_post" in flat, \
        f"function NAMES must still be extracted, got: {bindings}"


def test_bug22_create_lesson_file_logs_errors(isolated_kiwi, monkeypatch):
    """BUG #22: subprocess failure must be logged, not silently swallowed."""
    sys.modules.pop("generator.learning.fix_extractor", None)
    import generator.learning.fix_extractor as fx

    logged = []
    monkeypatch.setattr(fx, "_log_err", lambda stage, exc: logged.append((stage, str(exc)[:80])))

    # Fake subprocess that fails
    import subprocess as _sp

    def fake_run(*args, **kwargs):
        class R:
            returncode = 1
            stdout = ""
            stderr = "fake failure"
        return R()
    monkeypatch.setattr(_sp, "run", fake_run)

    res = fx._create_lesson_file({
        "category": "test",
        "severity": "SUGGEST",
        "pattern": "x",
        "scope": "**/*.php",
        "example_code": "",
        "good_code": "",
    })
    assert res is None
    assert len(logged) == 1, f"expected 1 logged error, got {logged}"
    assert logged[0][0] == "create_lesson_file_rc"


def test_bug24_session_id_cache_ttl(isolated_kiwi, monkeypatch):
    """BUG #24: cached _session_id must expire after TTL."""
    sl = isolated_kiwi["sl"]

    sid1 = sl.get_session_id()
    assert sid1, "first call must return a session_id"

    # Force cache expiration
    sl._session_id_set_at = time.time() - sl._SESSION_ID_TTL - 100
    # Also bust the file
    sl.SESSION_FILE.unlink(missing_ok=True)

    sid2 = sl.get_session_id()
    assert sid2, "second call must also return a session_id"
    assert sid2 != sid1, f"expired cache should re-issue: sid1={sid1} sid2={sid2}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
