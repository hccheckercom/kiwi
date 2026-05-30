#!/usr/bin/env python3
"""Kiwi post-edit hook — guardrail check + session logging + auto-learn."""

import json
import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LEARNING_ERROR_LOG = Path(__file__).parent.parent / "memory" / "learning_errors.log"
LEARNING_ERROR_LOG_MAX_BYTES = 2 * 1024 * 1024  # 2 MB rotation cap


def _log_learning_error(stage: str, exc: BaseException) -> None:
    """Append learning error to log so user can detect silent failure.

    Never raises — must not break the hook even if logging itself fails.
    """
    try:
        LEARNING_ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        if LEARNING_ERROR_LOG.exists() and LEARNING_ERROR_LOG.stat().st_size > LEARNING_ERROR_LOG_MAX_BYTES:
            backup = LEARNING_ERROR_LOG.with_suffix(".log.old")
            try:
                if backup.exists():
                    backup.unlink()
                LEARNING_ERROR_LOG.rename(backup)
            except OSError:
                pass
        with LEARNING_ERROR_LOG.open("a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] stage={stage} {type(exc).__name__}: {exc}\n")
            f.write(traceback.format_exc())
            f.write("---\n")
        try:
            from agent.reasoning.session_logger import _get_conn
            conn = _get_conn()
            conn.execute(
                "CREATE TABLE IF NOT EXISTS learning_health ("
                "stage TEXT PRIMARY KEY, "
                "fail_count INTEGER DEFAULT 0, "
                "last_failure_at REAL, "
                "last_error TEXT)"
            )
            conn.execute(
                "INSERT INTO learning_health (stage, fail_count, last_failure_at, last_error) "
                "VALUES (?, 1, ?, ?) "
                "ON CONFLICT(stage) DO UPDATE SET "
                "fail_count = fail_count + 1, "
                "last_failure_at = excluded.last_failure_at, "
                "last_error = excluded.last_error",
                (stage, time.time(), f"{type(exc).__name__}: {exc}"[:500]),
            )
            conn.commit()
        except Exception:
            pass
    except Exception:
        pass


def _learning_disabled() -> bool:
    """Honor opt-out flag for trial users (BUG #13). Default: enabled."""
    if os.environ.get("KIWI_LEARNING_DISABLED", "").strip() in ("1", "true", "yes"):
        return True
    flag_file = Path(__file__).parent.parent / "memory" / ".learning_disabled"
    return flag_file.exists()


def _log_session(tool: str, file_path: str):
    """Log tool call to reasoning DB for learning."""
    try:
        from agent.reasoning.session_logger import log_tool_call
        log_tool_call(tool, file_path)
    except Exception as e:
        _log_learning_error("log_session", e)


def _try_auto_learn():
    """Auto-trigger learning if session has 5+ new writes since last learn.

    Race-safe: atomic UPDATE-WHERE acts as compare-and-swap claim. Only one
    concurrent hook subprocess wins per (writes_threshold) tick.

    Errors are logged to learning_errors.log instead of swallowed.
    """
    if _learning_disabled():
        return
    try:
        from agent.reasoning.session_logger import _get_conn, get_session_id
        conn = _get_conn()
        sid = get_session_id()

        _ensure_learning_state(conn)

        row = conn.execute(
            "SELECT files_written FROM sessions WHERE session_id = ?",
            (sid,),
        ).fetchone()
        if not row:
            return
        writes = row[0] or 0

        conn.execute(
            "INSERT OR IGNORE INTO session_learn_state (session_id, last_learned_writes, last_learned_at) "
            "VALUES (?, 0, strftime('%s', 'now'))",
            (sid,),
        )

        cursor = conn.execute(
            "UPDATE session_learn_state "
            "SET last_learned_writes = ?, last_learned_at = strftime('%s', 'now') "
            "WHERE session_id = ? AND ? - last_learned_writes >= 5",
            (writes, sid, writes),
        )
        conn.commit()

        if cursor.rowcount == 0:
            return

        from agent.reasoning.learner import learn_from_session
        learn_from_session(sid)

        conn.execute(
            "UPDATE sessions SET processed = 0 WHERE session_id = ?",
            (sid,),
        )
        conn.commit()

        # Close the learning loop: turn promotable novel patterns into pending
        # lesson suggestions. Without this, learn_from_session populates
        # novel_patterns but nothing ever reaches promotion_suggestions, so the
        # "Kiwi learns" loop never completes. use_llm_validation=False keeps the
        # edit path 0-token; suggestions are human-reviewed at the dashboard.
        try:
            from agent.reasoning.auto_promoter import auto_promote_check, auto_bless_mature
            auto_promote_check(use_llm_validation=False)
            # Auto-bless conventions repeated enough to be intentional, so
            # kiwi_context/kiwi_reason inject them as enforced knowledge without
            # waiting for a human to approve each one at the dashboard.
            auto_bless_mature(min_seen=10)
        except Exception as e:
            _log_learning_error("auto_promote", e)
    except Exception as e:
        _log_learning_error("auto_learn", e)


def _ensure_learning_state(conn):
    """Create or migrate session_learn_state table.

    Single source of truth for the schema — `IF NOT EXISTS` only checks the
    table name, so we ALSO verify each expected column and ALTER as needed
    (BUG #9 fix).
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS session_learn_state ("
        "session_id TEXT PRIMARY KEY, "
        "last_learned_writes INTEGER DEFAULT 0, "
        "last_learned_at INTEGER, "
        "last_learned_files TEXT DEFAULT '[]'"
        ")"
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(session_learn_state)").fetchall()}
    if "last_learned_files" not in cols:
        conn.execute(
            "ALTER TABLE session_learn_state ADD COLUMN last_learned_files TEXT DEFAULT '[]'"
        )
        conn.commit()


def _read_payload():
    """Read hook payload from stdin (Claude Code protocol). Fallback to env var."""
    try:
        stdin_data = sys.stdin.read()
        if stdin_data:
            return json.loads(stdin_data)
    except Exception:
        pass
    raw = os.environ.get("TOOL_INPUT", "")
    if not raw:
        return None
    try:
        return {"tool_input": json.loads(raw), "tool_name": os.environ.get("TOOL_NAME", "Edit")}
    except json.JSONDecodeError:
        return None


def main():
    payload = _read_payload()
    if not payload:
        return

    tool_input = payload.get("tool_input") or payload
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except json.JSONDecodeError:
            return

    file_path = tool_input.get("file_path", "")
    if not file_path:
        return

    tool_name = payload.get("tool_name") or os.environ.get("TOOL_NAME", "Edit")
    _log_session(tool_name, file_path)

    # Auto-learn every 5 writes
    _try_auto_learn()

    if not any(file_path.endswith(ext) for ext in (".php", ".css", ".js", ".jsx", ".tsx", ".ts")):
        return

    from agent.guardrail import check_file, format_result

    result = check_file(file_path, severity="CRITICAL")
    output = format_result(result)
    if output:
        # Log kiwi_block to session for R3 calibration
        try:
            from agent.reasoning.session_logger import log_tool_call
            log_tool_call("KiwiBlock", file_path=file_path, metadata={"kiwi_block": True, "violations": len(result.get("violations", []))})
        except Exception:
            pass

        print("\n" + "="*70)
        print("⛔ KIWI POST-EDIT BLOCK")
        print("="*70)
        print(output)
        print("\n💡 Cách fix:")
        print("   1. Đọc violation details ở trên")
        print("   2. Gọi: kiwi_fix(lesson_id='...', file='...', apply=false) để preview")
        print("   3. Nếu OK → kiwi_fix(..., apply=true) để apply")
        print("   4. Hoặc fix thủ công theo Good example trong lesson")
        print("="*70 + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[kiwi] post_edit hook error: {e}", file=sys.stderr)
