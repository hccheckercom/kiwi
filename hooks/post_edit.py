#!/usr/bin/env python3
"""Kiwi post-edit hook — guardrail check + session logging + auto-learn."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _log_session(tool: str, file_path: str):
    """Log tool call to reasoning DB for learning. Silent on failure."""
    try:
        from agent.reasoning.session_logger import log_tool_call
        log_tool_call(tool, file_path)
    except Exception:
        pass


def _try_auto_learn():
    """Auto-trigger learning if session has enough data (5+ writes). Silent on failure."""
    try:
        from agent.reasoning.session_logger import _get_conn, get_session_id
        conn = _get_conn()
        row = conn.execute(
            "SELECT files_written, processed FROM sessions WHERE session_id = ?",
            (get_session_id(),)
        ).fetchone()

        if not row:
            return

        writes, processed = row
        # Learn every 5 writes (batch learning, not every single edit)
        if writes > 0 and writes % 5 == 0 and not processed:
            from agent.reasoning.learner import learn_from_session
            learn_from_session(get_session_id())
    except Exception:
        pass


def main():
    tool_input = os.environ.get("TOOL_INPUT", "")
    if not tool_input:
        return

    try:
        data = json.loads(tool_input)
    except json.JSONDecodeError:
        return

    file_path = data.get("file_path", "")
    if not file_path:
        return

    # Always log to session (for learning)
    tool_name = os.environ.get("TOOL_NAME", "Edit")
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
