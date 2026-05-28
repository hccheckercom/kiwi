"""R7 — Output Quality Metrics: track Kiwi's intelligence over time. 0 LLM token."""

import time

from .session_logger import (
    _get_conn,
    get_session_reads,
    get_session_writes,
    get_session_log_entries,
)

LEVEL_MAP = {'none': 0, 'brief_only': 0, 'skeleton': 1, 'draft': 2, 'ready': 3}


def epoch_week(ts: float = None) -> int:
    return int((ts or time.time()) / 604800)


def record_output_quality(session_id: str, brief=None) -> dict:
    """Record quality metrics for a session. Runs after learn + calibrate."""
    conn = _get_conn()

    reads = get_session_reads(session_id)
    writes = get_session_writes(session_id)
    entries = get_session_log_entries(session_id)

    if not writes:
        return {'status': 'skipped', 'reason': 'no_writes'}

    task_type = 'generic'
    source_files = []
    autonomy_level = 'none'
    trust_score = 0.0

    if brief is not None:
        if isinstance(brief, dict):
            task_type = brief.get('task_type', 'generic')
            source_files = brief.get('files_needed', [])
            trust_score = brief.get('trust_score', 0.0)
        else:
            task_type = brief.content.get('target', 'generic') if hasattr(brief, 'content') else 'generic'
            source_files = brief.content.get('files_needed', []) if hasattr(brief, 'content') else []
            trust_score = brief.trust_score if hasattr(brief, 'trust_score') else 0.0
            if hasattr(brief, 'graduated') and brief.graduated is not None:
                autonomy_level = brief.graduated.level

    brief_level = LEVEL_MAP.get(autonomy_level, 0)

    re_reads = len([r for r in reads if r['file'] in source_files])

    file_edit_counts = {}
    for w in writes:
        if w.get('tool') == 'Edit':
            file_edit_counts[w['file']] = file_edit_counts.get(w['file'], 0) + 1
    max_edits = max((c - 1 for c in file_edit_counts.values()), default=0)

    duration = 0.0
    if entries:
        timestamps = [e['timestamp'] for e in entries if e.get('timestamp')]
        if len(timestamps) >= 2:
            duration = max(timestamps) - min(timestamps)

    total_calls = len(entries)
    tokens_estimated = total_calls * 50 + len(reads) * 200 + len(writes) * 500

    brief_count = conn.execute(
        "SELECT COUNT(*) FROM output_quality WHERE task_type = ?",
        (task_type,)
    ).fetchone()[0]

    week = epoch_week()

    conn.execute(
        "INSERT INTO output_quality "
        "(session_id, week, task_type, brief_version, trust_score, tokens_estimated, "
        "files_re_read, edits_after_first, total_tool_calls, brief_level, "
        "autonomy_level, session_duration_sec, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            session_id, week, task_type, brief_count + 1, trust_score,
            tokens_estimated, re_reads, max_edits, total_calls,
            brief_level, autonomy_level, duration, time.time(),
        )
    )
    conn.commit()

    return {
        'status': 'recorded',
        'session_id': session_id,
        'week': week,
        'task_type': task_type,
        'brief_version': brief_count + 1,
        'brief_level': brief_level,
        'trust_score': trust_score,
        'tokens_estimated': tokens_estimated,
        'files_re_read': re_reads,
        'edits_after_first': max_edits,
        'total_tool_calls': total_calls,
        'autonomy_level': autonomy_level,
        'session_duration_sec': duration,
    }


def get_think_metrics(weeks: int = 4) -> dict:
    """Get R8 thinking metrics for Intelligence Score integration."""
    conn = _get_conn()
    if not conn:
        return {'think_calls': 0, 'cache_hits': 0, 'avg_confidence': 0.0, 'cost_tokens': 0}

    cutoff = time.time() - (weeks * 7 * 86400)
    try:
        row = conn.execute(
            "SELECT COUNT(*), "
            "SUM(CASE WHEN cached = 1 THEN 1 ELSE 0 END), "
            "AVG(confidence), "
            "SUM(tokens_used) "
            "FROM think_events WHERE created_at > ?",
            (cutoff,),
        ).fetchone()

        total = row[0] or 0
        cached = row[1] or 0
        avg_conf = round(row[2] or 0.0, 3)
        tokens = row[3] or 0

        success_row = conn.execute(
            "SELECT COUNT(*) FROM think_events "
            "WHERE created_at > ? AND success = 1",
            (cutoff,),
        ).fetchone()
        successes = success_row[0] if success_row else 0

        return {
            'think_calls': total,
            'cache_hits': cached,
            'cache_hit_rate': round(cached / total, 3) if total > 0 else 0.0,
            'avg_confidence': avg_conf,
            'cost_tokens': tokens,
            'success_rate': round(successes / (total - cached), 3) if (total - cached) > 0 else 0.0,
        }
    except Exception:
        return {'think_calls': 0, 'cache_hits': 0, 'avg_confidence': 0.0, 'cost_tokens': 0}


def mark_think_success(session_id: str, trigger: str, success: bool):
    """Mark a think event as successful or not (for accuracy tracking)."""
    conn = _get_conn()
    if not conn:
        return
    try:
        row = conn.execute(
            "SELECT id FROM think_events "
            "WHERE session_id = ? AND trigger = ? AND success IS NULL "
            "ORDER BY created_at DESC LIMIT 1",
            (session_id, trigger),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE think_events SET success = ? WHERE id = ?",
                (1 if success else 0, row[0]),
            )
            conn.commit()
    except Exception:
        pass
