"""Tests for R3 — Trust Calibrator."""

import json
import sqlite3
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.reasoning.session_logger import _get_conn, DB_PATH
from agent.reasoning.calibrator import (
    calibrate_trust_from_session,
    _get_trust_baseline,
    _set_trust_baseline,
    CALIBRATION_RULES,
)


def _reset_db():
    """Fresh DB for each test."""
    import agent.reasoning.session_logger as sl
    if sl._conn is not None:
        try:
            sl._conn.close()
        except Exception:
            pass
        sl._conn = None
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = _get_conn()
    return conn


def _seed_session(conn, session_id, reads, writes, brief=None, kiwi_block_after=False):
    """Insert test data into session_log + brief_log."""
    conn.execute(
        "INSERT OR IGNORE INTO sessions (session_id, started_at, files_read, files_written) "
        "VALUES (?, ?, ?, ?)",
        (session_id, time.time(), len(reads), len(writes)),
    )

    ts = time.time()
    for r in reads:
        conn.execute(
            "INSERT INTO session_log (session_id, tool, file_path, action, metadata, timestamp) "
            "VALUES (?, 'Read', ?, 'read', NULL, ?)",
            (session_id, r, ts),
        )
        ts += 0.1

    for w in writes:
        conn.execute(
            "INSERT INTO session_log (session_id, tool, file_path, action, metadata, timestamp) "
            "VALUES (?, 'Edit', ?, 'edit', NULL, ?)",
            (session_id, w, ts),
        )
        ts += 0.1

    if kiwi_block_after:
        conn.execute(
            "INSERT INTO session_log (session_id, tool, file_path, action, metadata, timestamp) "
            "VALUES (?, 'Bash', NULL, 'shell', ?, ?)",
            (session_id, json.dumps({"kiwi_block": True}), ts),
        )

    if brief:
        conn.execute(
            "INSERT OR REPLACE INTO brief_log "
            "(session_id, task_type, files_needed, trust_score, recommendation, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                session_id,
                brief["task_type"],
                json.dumps(brief.get("files_needed", [])),
                brief.get("trust_score", 0.7),
                brief.get("recommendation", "verify_partial"),
                time.time(),
            ),
        )

    conn.commit()


def test_no_brief_returns_early():
    conn = _reset_db()
    _seed_session(conn, "s-no-brief", ["a.php"], ["b.php", "c.php"])
    result = calibrate_trust_from_session("s-no-brief")
    assert result["status"] == "no_brief", f"Expected no_brief, got {result}"
    print("PASS: test_no_brief_returns_early")


def test_skip_short_session():
    conn = _reset_db()
    _seed_session(
        conn, "s-short", ["a.php"], ["b.php"],
        brief={"task_type": "checkout_page", "files_needed": ["a.php"]},
    )
    result = calibrate_trust_from_session("s-short")
    assert result["status"] == "skipped" and result["reason"] == "too_short", f"Got {result}"
    print("PASS: test_skip_short_session")


def test_trust_increases_on_all_positive():
    conn = _reset_db()
    _set_trust_baseline("product_page", 0.7)

    # Claude only reads briefed files + 1 extra (within threshold) → all positive
    _seed_session(
        conn, "s-positive",
        reads=["spec.md", "config.php", "extra.php"],
        writes=["a.php", "b.php"],
        brief={"task_type": "product_page", "files_needed": ["spec.md", "config.php", "tokens.json"]},
    )
    result = calibrate_trust_from_session("s-positive")
    assert result["reason"] == "all_positive", f"Got {result}"
    assert result["trust_after"] == 0.75, f"Expected 0.75, got {result['trust_after']}"
    print("PASS: test_trust_increases_on_all_positive")


def test_trust_decreases_on_all_negative():
    conn = _reset_db()
    _set_trust_baseline("checkout_page", 0.8)

    # Signal 1: brief has 3 files, Claude reads 5 EXTRA files not in brief → insufficient
    briefed = ["spec.md", "config.php", "tokens.json"]
    extra_reads = ["other1.php", "other2.php", "other3.php", "other4.php"]
    _seed_session(
        conn, "s-negative",
        reads=briefed + extra_reads,  # 4 extra > max(3 briefed, 3) → insufficient
        writes=["a.php", "a.php", "a.php", "b.php"],
        brief={"task_type": "checkout_page", "files_needed": briefed},
        kiwi_block_after=True,
    )
    # Need > 2 edits on same file for Signal 2
    ts = time.time() + 100
    conn.execute(
        "INSERT INTO session_log (session_id, tool, file_path, action, metadata, timestamp) "
        "VALUES (?, 'Edit', ?, 'edit', NULL, ?)",
        ("s-negative", "a.php", ts),
    )
    conn.execute(
        "INSERT INTO session_log (session_id, tool, file_path, action, metadata, timestamp) "
        "VALUES (?, 'Edit', ?, 'edit', NULL, ?)",
        ("s-negative", "a.php", ts + 1),
    )
    conn.commit()

    result = calibrate_trust_from_session("s-negative")
    assert result["reason"] == "all_negative", f"Got {result}"
    assert result["trust_after"] == 0.65, f"Expected 0.65, got {result['trust_after']}"
    print("PASS: test_trust_decreases_on_all_negative")


def test_mixed_signals_no_change():
    conn = _reset_db()
    _set_trust_baseline("home_page", 0.6)

    # Signal 1 triggers: brief has 3 files, Claude reads 4 extra → 4 > max(3, 3) → insufficient
    _seed_session(
        conn, "s-mixed",
        reads=["spec.md", "extra1.php", "extra2.php", "extra3.php", "extra4.php"],
        writes=["hero.php", "slider.php"],
        brief={"task_type": "home_page", "files_needed": ["spec.md", "config.php", "tokens.json"]},
    )
    result = calibrate_trust_from_session("s-mixed")
    # 1 signal (brief_insufficient=True, rewrites=False, violations=False) → mixed
    assert result["reason"] == "mixed_signals", f"Expected mixed_signals, got {result}"
    assert result["delta"] == 0.0, f"Expected 0 delta, got {result}"
    print("PASS: test_mixed_signals_no_change")


def test_fifo_eviction():
    conn = _reset_db()
    # Insert max_events + 10
    max_ev = CALIBRATION_RULES["max_events"]
    for i in range(max_ev + 10):
        conn.execute(
            "INSERT INTO calibration_events "
            "(session_id, task_type, signals, trust_before, trust_after, delta, reason, created_at) "
            "VALUES (?, 'test', '{}', 0.5, 0.5, 0.0, 'test', ?)",
            (f"s-{i}", time.time() + i),
        )
    conn.commit()

    # Trigger eviction via a real calibration
    _set_trust_baseline("cart_page", 0.5)
    _seed_session(
        conn, "s-evict",
        reads=["x.php"],
        writes=["a.php", "b.php"],
        brief={"task_type": "cart_page", "files_needed": ["spec.md"]},
    )
    calibrate_trust_from_session("s-evict")

    count = conn.execute("SELECT COUNT(*) FROM calibration_events").fetchone()[0]
    assert count <= max_ev, f"Expected <= {max_ev}, got {count}"
    print("PASS: test_fifo_eviction")


def test_task_changed_skip():
    conn = _reset_db()
    _seed_session(
        conn, "s-changed",
        reads=["unrelated.php"],
        writes=["themes/other/page.php", "themes/other/hero.php"],
        brief={
            "task_type": "checkout_page",
            "files_needed": ["themes/sfvn/checkout.php", "themes/sfvn/config.php"],
        },
    )
    result = calibrate_trust_from_session("s-changed")
    assert result["status"] == "skipped" and result["reason"] == "task_changed", f"Got {result}"
    print("PASS: test_task_changed_skip")


def test_clamp_min_max():
    conn = _reset_db()
    # Test min clamp
    _set_trust_baseline("low_task", 0.15)

    # Signal 1: 5 extra reads > max(3 briefed, 3) → insufficient
    # Signal 2: 3+ edits on same file
    # Signal 3: kiwi_block
    _seed_session(
        conn, "s-low",
        reads=["e1.php", "e2.php", "e3.php", "e4.php", "e5.php"],
        writes=["a.php", "a.php", "a.php", "b.php"],
        brief={"task_type": "low_task", "files_needed": ["spec.md", "cfg.php", "tok.json"]},
        kiwi_block_after=True,
    )
    ts = time.time() + 200
    conn.execute(
        "INSERT INTO session_log (session_id, tool, file_path, action, metadata, timestamp) "
        "VALUES (?, 'Edit', 'a.php', 'edit', NULL, ?)", ("s-low", ts),
    )
    conn.execute(
        "INSERT INTO session_log (session_id, tool, file_path, action, metadata, timestamp) "
        "VALUES (?, 'Edit', 'a.php', 'edit', NULL, ?)", ("s-low", ts + 1),
    )
    conn.commit()

    result = calibrate_trust_from_session("s-low")
    assert result["trust_after"] >= CALIBRATION_RULES["min_trust"], f"Below min: {result}"
    assert result["trust_after"] == CALIBRATION_RULES["min_trust"], f"Expected min clamp: {result}"
    print("PASS: test_clamp_min_max")


if __name__ == "__main__":
    test_no_brief_returns_early()
    test_skip_short_session()
    test_trust_increases_on_all_positive()
    test_trust_decreases_on_all_negative()
    test_mixed_signals_no_change()
    test_fifo_eviction()
    test_task_changed_skip()
    test_clamp_min_max()
    print("\n=== ALL 8 TESTS PASSED ===")
