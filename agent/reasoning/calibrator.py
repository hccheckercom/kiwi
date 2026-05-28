"""R3 — Trust Calibrator: adjusts trust baselines from session behavior signals."""

import json
import time
from collections import Counter
from pathlib import Path

from .session_logger import (
    _get_conn,
    get_session_reads,
    get_session_writes,
    get_brief_for_session,
    get_session_log_entries,
)

CALIBRATION_RULES = {
    "positive_delta": 0.05,
    "negative_delta_mild": -0.08,
    "negative_delta_severe": -0.15,
    "min_trust": 0.1,
    "max_trust": 0.95,
    "initial_trust": 0.5,
    "max_events": 500,
    "decay_after_days": 14,
    "decay_rate": 0.03,
    "decay_floor": 0.4,
}


def calibrate_trust_from_session(session_id: str) -> dict:
    """Post-session: check if Claude trusted the brief. 3 binary signals."""
    brief = get_brief_for_session(session_id)
    if not brief:
        return {"status": "no_brief", "action": "none"}

    reads = get_session_reads(session_id)
    writes = get_session_writes(session_id)

    skip_reason = _check_edge_cases(writes, brief)
    if skip_reason:
        return {"status": "skipped", "reason": skip_reason}

    task_type = brief["task_type"]
    briefed_files = brief.get("files_needed", [])

    # Signal 1: Brief Insufficient — Claude read many files NOT in the brief
    # If brief was trusted, Claude only reads what brief recommends.
    # Extra reads = brief didn't cover enough = low trust.
    read_paths = {r["file"] for r in reads if r["file"]}
    briefed_set = set(briefed_files)
    extra_reads = read_paths - briefed_set
    # Threshold: more extra reads than briefed files = brief was insufficient
    brief_insufficient = len(extra_reads) > max(len(briefed_set), 3) if briefed_set else False

    # Signal 2: Multiple Rewrites — same file edited > 2 times
    file_edit_counts = {}
    for w in writes:
        if w.get("tool") == "Edit":
            file_edit_counts[w["file"]] = file_edit_counts.get(w["file"], 0) + 1
    multiple_rewrites = any(count > 2 for count in file_edit_counts.values())

    # Signal 3: Kiwi Violations After Code
    kiwi_violations = _check_post_code_violations(session_id)

    # Asymmetric calibration
    negative_signals = sum([brief_insufficient, multiple_rewrites, kiwi_violations])
    current_trust = _get_trust_baseline(task_type)

    if negative_signals == 0:
        delta = CALIBRATION_RULES["positive_delta"]
        reason = "all_positive"
    elif negative_signals == 1:
        delta = 0.0
        reason = "mixed_signals"
    elif negative_signals == 2:
        delta = CALIBRATION_RULES["negative_delta_mild"]
        reason = "mostly_negative"
    else:
        delta = CALIBRATION_RULES["negative_delta_severe"]
        reason = "all_negative"

    new_trust = max(
        CALIBRATION_RULES["min_trust"],
        min(CALIBRATION_RULES["max_trust"], current_trust + delta),
    )
    _set_trust_baseline(task_type, new_trust)

    event = {
        "session_id": session_id,
        "task_type": task_type,
        "signals": {
            "brief_insufficient": brief_insufficient,
            "multiple_rewrites": multiple_rewrites,
            "kiwi_violations": kiwi_violations,
        },
        "trust_before": current_trust,
        "trust_after": new_trust,
        "delta": delta,
        "reason": reason,
    }
    _save_calibration_event(event)
    return event


def _check_edge_cases(writes: list, brief: dict) -> str | None:
    if len(writes) < 2:
        return "too_short"

    brief_files = set(brief.get("files_needed", []))
    actual_files = {w["file"] for w in writes if w["file"]}
    if brief_files and not (brief_files & actual_files):
        brief_dirs = {"/".join(f.replace("\\", "/").split("/")[:-1]) for f in brief_files}
        actual_dirs = {"/".join(f.replace("\\", "/").split("/")[:-1]) for f in actual_files}
        if not (brief_dirs & actual_dirs):
            return "task_changed"

    return None


def _check_post_code_violations(session_id: str) -> bool:
    entries = get_session_log_entries(session_id)
    has_write = False
    for entry in entries:
        if entry["tool"] in ("Write", "Edit"):
            has_write = True
        elif has_write:
            if entry["tool"] == "KiwiBlock":
                return True
            if entry.get("metadata", {}).get("kiwi_block"):
                return True
    return False


def _get_trust_baseline(task_type: str) -> float:
    conn = _get_conn()
    row = conn.execute(
        "SELECT trust_score FROM trust_baselines WHERE task_type = ?",
        (task_type,),
    ).fetchone()
    return row[0] if row else CALIBRATION_RULES["initial_trust"]


def _set_trust_baseline(task_type: str, trust: float):
    conn = _get_conn()
    now = time.time()
    conn.execute(
        "INSERT INTO trust_baselines (task_type, trust_score, last_calibrated, calibration_count) "
        "VALUES (?, ?, ?, 1) "
        "ON CONFLICT(task_type) DO UPDATE SET "
        "trust_score = ?, last_calibrated = ?, calibration_count = calibration_count + 1",
        (task_type, trust, now, trust, now),
    )
    conn.commit()


def _save_calibration_event(event: dict):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO calibration_events "
        "(session_id, task_type, signals, trust_before, trust_after, delta, reason, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            event["session_id"],
            event["task_type"],
            json.dumps(event["signals"]),
            event["trust_before"],
            event["trust_after"],
            event["delta"],
            event["reason"],
            time.time(),
        ),
    )
    max_events = CALIBRATION_RULES["max_events"]
    count = conn.execute("SELECT COUNT(*) FROM calibration_events").fetchone()[0]
    if count > max_events:
        conn.execute(
            "DELETE FROM calibration_events WHERE id IN ("
            "  SELECT id FROM calibration_events ORDER BY created_at ASC LIMIT ?"
            ")",
            (count - max_events,),
        )
    conn.commit()


# ============================================================
# Trust Baseline Decay
# ============================================================

def decay_stale_baselines() -> dict:
    """Decay trust baselines not calibrated in > 14 days.
    Rationale: stale baselines may reflect outdated code/spec state.
    Decay toward 0.4 (neutral-low) at 0.03/call until re-calibrated."""
    conn = _get_conn()
    now = time.time()
    cutoff = now - (CALIBRATION_RULES["decay_after_days"] * 86400)
    floor = CALIBRATION_RULES["decay_floor"]
    rate = CALIBRATION_RULES["decay_rate"]

    rows = conn.execute(
        "SELECT task_type, trust_score, last_calibrated FROM trust_baselines "
        "WHERE last_calibrated < ? AND trust_score > ?",
        (cutoff, floor),
    ).fetchall()

    decayed = []
    for task_type, score, last_cal in rows:
        new_score = max(floor, score - rate)
        conn.execute(
            "UPDATE trust_baselines SET trust_score = ? WHERE task_type = ?",
            (new_score, task_type),
        )
        decayed.append({"task_type": task_type, "before": score, "after": new_score})

    if decayed:
        conn.commit()

    return {"decayed": len(decayed), "details": decayed}


# ============================================================
# Pattern Mining — auto-suggest files_needed
# ============================================================

def mine_file_patterns(min_sessions: int = 5) -> dict:
    """Aggregate context_patterns → find files commonly read before writing.
    Returns suggested files_needed per task_type (only if 5+ sessions of data)."""
    conn = _get_conn()

    task_types = conn.execute(
        "SELECT task_type, COUNT(*) as cnt FROM context_patterns "
        "GROUP BY task_type HAVING cnt >= ?",
        (min_sessions,),
    ).fetchall()

    suggestions = {}
    for task_type, count in task_types:
        rows = conn.execute(
            "SELECT files_read, files_written FROM context_patterns "
            "WHERE task_type = ? ORDER BY created_at DESC LIMIT 20",
            (task_type,),
        ).fetchall()

        read_counter = Counter()
        write_counter = Counter()
        for files_read_json, files_written_json in rows:
            try:
                reads = json.loads(files_read_json)
                writes = json.loads(files_written_json)
                read_counter.update(reads)
                write_counter.update(writes)
            except (json.JSONDecodeError, TypeError):
                continue

        # Files read in >= 60% of sessions for this task_type
        threshold = max(3, int(len(rows) * 0.6))
        common_reads = [f for f, c in read_counter.most_common(15) if c >= threshold]

        # Filter: only suggest files that still exist
        valid_reads = [f for f in common_reads if Path(f).exists()]

        if valid_reads:
            suggestions[task_type] = {
                "files_needed": valid_reads[:10],
                "confidence": min(count / 20, 1.0),
                "sessions_analyzed": count,
            }

    return suggestions
