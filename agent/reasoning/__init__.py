"""Kiwi Reasoning Layer — R6: Graduated Autonomy."""

import time

from .context_assembler import assemble_context, AssembledContext
from .trust_scorer import compute_trust_score
from .output import format_output, KiwiOutput
from .adaptive_brief import apply_adaptive_depth
from .proactive_warnings import check_warnings
from .cross_theme import find_transferable_pattern
from .session_logger import get_session_id, save_brief_output

_last_learn_ts: float = 0.0
_learn_skip_count: int = 0
_LEARN_COOLDOWN: float = 30.0
_LEARN_LATENCY_CAP_MS: float = 100.0
_LEARN_SKIP_AFTER_SLOW: int = 5


def kiwi_reason(task: str, theme_path: str, include_code: bool = False) -> KiwiOutput:
    """Task → Brief + Trust Score + Adaptive Depth + Warnings + Code. 0 LLM token. ~50ms."""
    _auto_learn_recent(max_sessions=3)
    _cold_start_if_needed(theme_path)
    context = assemble_context(task, theme_path)
    trust_score, breakdown = compute_trust_score(context, theme_path)

    try:
        brief_config = apply_adaptive_depth(context, trust_score)
    except Exception:
        brief_config = None

    theme_name = context.theme.get('name', 'unknown') if isinstance(context.theme, dict) else 'unknown'

    warnings = []
    try:
        warnings = check_warnings(context.task_type, theme_name, trust_score)
    except Exception:
        pass

    transfer = None
    try:
        transfer = find_transferable_pattern(context.task_type, theme_name)
    except Exception:
        pass

    output = format_output(context, trust_score, breakdown)
    output.warnings = warnings
    output.transfer = transfer
    output.brief_config = brief_config

    # R6: Graduated autonomy — generate code when trust is sufficient
    if include_code and trust_score >= 0.6:
        try:
            from .autonomy import generate_graduated_output
            output.graduated = generate_graduated_output(output, theme_path)
        except Exception:
            pass

    try:
        save_brief_output(get_session_id(), output)
    except Exception:
        pass

    return output


def _auto_learn_recent(max_sessions: int = 3):
    """Piggyback: learn + calibrate from unprocessed sessions. Throttled."""
    global _last_learn_ts, _learn_skip_count

    now = time.time()
    if _learn_skip_count > 0:
        _learn_skip_count -= 1
        return
    if (now - _last_learn_ts) < _LEARN_COOLDOWN:
        return

    try:
        from .session_logger import get_unprocessed_sessions, _get_conn
        from .learner import learn_from_session, calibrate_trust_baselines
        from .calibrator import calibrate_trust_from_session, decay_stale_baselines
        from .proactive_warnings import evaluate_warnings_post_session

        t0 = time.time()
        sessions = get_unprocessed_sessions(min_writes=1)
        learned_count = 0
        for s in sessions[:max_sessions]:
            learn_from_session(s["session_id"])
            cal_result = calibrate_trust_from_session(s["session_id"])
            if isinstance(cal_result, dict) and "signals" in cal_result:
                signals = cal_result["signals"]
                neg_count = sum(1 for v in signals.values() if v)
                evaluate_warnings_post_session(s["session_id"], neg_count)
            learned_count += 1

        if learned_count > 0:
            try:
                from .auto_promoter import auto_promote_check
                auto_promote_check()
            except Exception:
                pass

            try:
                from .metrics import record_output_quality
                from .session_logger import get_brief_for_session
                for s in sessions[:learned_count]:
                    brief_data = get_brief_for_session(s["session_id"])
                    record_output_quality(s["session_id"], brief_data)
            except Exception:
                pass

            conn = _get_conn()
            total = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE processed = 1"
            ).fetchone()[0]
            if total > 0 and total % 10 == 0:
                calibrate_trust_baselines()
                decay_stale_baselines()

        elapsed_ms = (time.time() - t0) * 1000
        _last_learn_ts = now
        if elapsed_ms > _LEARN_LATENCY_CAP_MS:
            _learn_skip_count = _LEARN_SKIP_AFTER_SLOW
    except Exception:
        _last_learn_ts = now


_cold_start_done: set = set()


def _cold_start_if_needed(theme_path: str):
    """Bootstrap new themes from same-industry data. Runs once per theme per session."""
    global _cold_start_done
    if theme_path in _cold_start_done:
        return
    _cold_start_done.add(theme_path)

    try:
        from .cold_start import needs_bootstrap, bootstrap_from_industry
        if needs_bootstrap(theme_path):
            bootstrap_from_industry(theme_path)
    except Exception:
        pass