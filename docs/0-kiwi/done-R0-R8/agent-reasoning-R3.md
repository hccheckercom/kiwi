# Phase R3 — Trust Calibration

## Mục đích

Trust score tự điều chỉnh dựa trên Claude's actual behavior.
Giảm nhanh khi sai, tăng chậm khi đúng. Dùng binary signals thay vì semantic comparison.

## Dependencies

- **R0 (Session Capture)** — `session_logger.py`: `get_session_reads()`, `get_session_writes()`, `_get_conn()`
- **R2 (Passive Learning)** — `learner.py`: `_compute_session_quality()` populates `output_quality` table
- **Schema** — `schema.sql`: tables `session_log`, `sessions`, `trust_baselines`, `output_quality`

## Audit R0-R2 — Actual State

| File | Exports used by R3 |
|------|-------------------|
| `session_logger.py` | `get_session_reads(sid)`, `get_session_writes(sid)`, `_get_conn()`, `mark_session_processed()` |
| `learner.py` | `learn_from_session(sid)`, `calibrate_trust_baselines()` |
| `trust_scorer.py` | `_blend_with_baseline(task_type, computed)` — reads `trust_baselines` table |
| `context_assembler.py` | `AssembledContext`, `infer_task_type()` |
| `output.py` | `KiwiOutput` — fields: `content`, `trust_score`, `trust_breakdown`, `recommendation`, `verify_hint` |
| `__init__.py` | `kiwi_reason(task, theme_path)` → calls `_auto_learn_recent()` then assembles |

**KiwiOutput.content keys:** `target`, `files_needed`, `spec`, `lessons`, `data_bindings`, `style_pattern`, `reference_pages`

## Files tạo/sửa

```
agent/reasoning/
├── calibrator.py          # NEW — feedback loop, trust adjustment
├── schema.sql             # MODIFY — add calibration_events + brief_log tables
├── __init__.py            # MODIFY — wire calibrator into post-session pipeline
└── session_logger.py      # MODIFY — add save_brief_output() + get_session_log_entries()
```

## Schema Migration

```sql
-- Thêm vào schema.sql

CREATE TABLE IF NOT EXISTS calibration_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    signals TEXT,
    trust_before REAL,
    trust_after REAL,
    delta REAL,
    reason TEXT,
    created_at REAL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS brief_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE,
    task_type TEXT NOT NULL,
    files_needed TEXT,
    trust_score REAL,
    recommendation TEXT,
    created_at REAL DEFAULT (strftime('%s','now'))
);

CREATE INDEX IF NOT EXISTS idx_ce_session ON calibration_events(session_id);
CREATE INDEX IF NOT EXISTS idx_ce_task ON calibration_events(task_type);
CREATE INDEX IF NOT EXISTS idx_bl_session ON brief_log(session_id);
```

## Brief Storage — Giải quyết "get_brief_for_session"

Hiện tại không có cơ chế lưu brief đã output cho session. Cần thêm:

```python
# Thêm vào session_logger.py

def save_brief_output(session_id: str, brief: "KiwiOutput"):
    """Store brief output for later calibration. Called from kiwi_reason()."""
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO brief_log "
        "(session_id, task_type, files_needed, trust_score, recommendation, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            session_id,
            brief.content.get('target', 'generic'),
            json.dumps(brief.content.get('files_needed', []), ensure_ascii=False),
            brief.trust_score,
            brief.recommendation,
            time.time(),
        ),
    )
    conn.commit()


def get_brief_for_session(session_id: str) -> dict | None:
    """Retrieve stored brief for calibration."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT task_type, files_needed, trust_score, recommendation "
        "FROM brief_log WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    if not row:
        return None
    return {
        'task_type': row[0],
        'files_needed': json.loads(row[1]) if row[1] else [],
        'trust_score': row[2],
        'recommendation': row[3],
    }


def get_session_log_entries(session_id: str) -> list[dict]:
    """Get all log entries for a session, ordered by timestamp."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT tool, file_path, action, metadata, timestamp FROM session_log "
        "WHERE session_id = ? ORDER BY timestamp",
        (session_id,),
    ).fetchall()
    return [
        {
            'tool': r[0],
            'file': r[1],
            'action': r[2],
            'metadata': json.loads(r[3]) if r[3] else {},
            'timestamp': r[4],
        }
        for r in rows
    ]
```

## Calibrator — Main Logic

```python
# File: agent/reasoning/calibrator.py

"""R3 — Trust Calibrator: adjusts trust baselines from session behavior signals."""

import json
import time
from .session_logger import (
    _get_conn,
    get_session_reads,
    get_session_writes,
    get_brief_for_session,
    get_session_log_entries,
)

CALIBRATION_RULES = {
    'positive_delta': 0.05,
    'negative_delta_mild': -0.08,
    'negative_delta_severe': -0.15,
    'min_trust': 0.1,
    'max_trust': 0.95,
    'initial_trust': 0.5,
    'max_events': 500,  # FIFO eviction cap
}


def calibrate_trust_from_session(session_id: str) -> dict:
    """
    Post-session: check if Claude trusted the brief.
    Uses 3 binary signals. Returns calibration event dict.
    """
    brief = get_brief_for_session(session_id)
    if not brief:
        return {'status': 'no_brief', 'action': 'none'}

    # Edge case checks
    skip_reason = _check_edge_cases(session_id, brief)
    if skip_reason:
        return {'status': 'skipped', 'reason': skip_reason}

    reads = get_session_reads(session_id)
    writes = get_session_writes(session_id)
    task_type = brief['task_type']
    briefed_files = brief.get('files_needed', [])

    # === SIGNAL 1: Brief Ignored ===
    # Claude re-read > 50% of files that brief already listed
    read_paths = {r['file'] for r in reads if r['file']}
    briefed_set = set(briefed_files)
    overlap = read_paths & briefed_set
    brief_ignored = len(overlap) > len(briefed_set) * 0.5 if briefed_set else False

    # === SIGNAL 2: Multiple Rewrites ===
    # Claude edited same file > 2 times → trial-and-error
    file_edit_counts = {}
    for w in writes:
        if w.get('tool') == 'Edit':
            file_edit_counts[w['file']] = file_edit_counts.get(w['file'], 0) + 1
    multiple_rewrites = any(count > 2 for count in file_edit_counts.values())

    # === SIGNAL 3: Kiwi Violations After Code ===
    kiwi_violations = _check_post_code_violations(session_id)

    # === Calibration Logic (asymmetric) ===
    negative_signals = sum([brief_ignored, multiple_rewrites, kiwi_violations])

    current_trust = _get_trust_baseline(task_type)

    if negative_signals == 0:
        delta = CALIBRATION_RULES['positive_delta']
        reason = "all_positive"
    elif negative_signals == 1:
        delta = 0.0
        reason = "mixed_signals"
    elif negative_signals == 2:
        delta = CALIBRATION_RULES['negative_delta_mild']
        reason = "mostly_negative"
    else:
        delta = CALIBRATION_RULES['negative_delta_severe']
        reason = "all_negative"

    new_trust = max(
        CALIBRATION_RULES['min_trust'],
        min(CALIBRATION_RULES['max_trust'], current_trust + delta),
    )
    _set_trust_baseline(task_type, new_trust)

    event = {
        'session_id': session_id,
        'task_type': task_type,
        'signals': {
            'brief_ignored': brief_ignored,
            'multiple_rewrites': multiple_rewrites,
            'kiwi_violations': kiwi_violations,
        },
        'trust_before': current_trust,
        'trust_after': new_trust,
        'delta': delta,
        'reason': reason,
    }
    _save_calibration_event(event)

    return event


def _check_edge_cases(session_id: str, brief: dict) -> str | None:
    """Return skip reason if session shouldn't be calibrated."""
    writes = get_session_writes(session_id)

    # Too short — not enough signal
    if len(writes) < 2:
        return 'too_short'

    # Task changed mid-session: wrote files unrelated to brief target
    brief_files = set(brief.get('files_needed', []))
    actual_files = {w['file'] for w in writes if w['file']}
    if brief_files and not (brief_files & actual_files):
        # Check if any written file is in the same directory as briefed files
        brief_dirs = {'/'.join(f.replace('\\', '/').split('/')[:-1]) for f in brief_files}
        actual_dirs = {'/'.join(f.replace('\\', '/').split('/')[:-1]) for f in actual_files}
        if not (brief_dirs & actual_dirs):
            return 'task_changed'

    return None


def _check_post_code_violations(session_id: str) -> bool:
    """Check if Kiwi scan found CRITICAL violations after code was written."""
    entries = get_session_log_entries(session_id)

    has_write = False
    for entry in entries:
        if entry['tool'] in ('Write', 'Edit'):
            has_write = True
        elif has_write and entry.get('metadata', {}).get('kiwi_block'):
            return True

    return False


# --- DB helpers (use existing connection from session_logger) ---

def _get_trust_baseline(task_type: str) -> float:
    conn = _get_conn()
    row = conn.execute(
        "SELECT trust_score FROM trust_baselines WHERE task_type = ?",
        (task_type,),
    ).fetchone()
    return row[0] if row else CALIBRATION_RULES['initial_trust']


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
            event['session_id'],
            event['task_type'],
            json.dumps(event['signals']),
            event['trust_before'],
            event['trust_after'],
            event['delta'],
            event['reason'],
            time.time(),
        ),
    )
    # FIFO eviction
    max_events = CALIBRATION_RULES['max_events']
    count = conn.execute("SELECT COUNT(*) FROM calibration_events").fetchone()[0]
    if count > max_events:
        conn.execute(
            "DELETE FROM calibration_events WHERE id IN ("
            "  SELECT id FROM calibration_events ORDER BY created_at ASC LIMIT ?"
            ")",
            (count - max_events,),
        )
    conn.commit()
```

## Integration — __init__.py Update

```python
# Sửa __init__.py: wire calibrator + save brief

def kiwi_reason(task: str, theme_path: str) -> KiwiOutput:
    """Task → Brief + Trust Score. 0 LLM token. ~50ms."""
    _auto_learn_recent(max_sessions=3)
    context = assemble_context(task, theme_path)
    trust_score, breakdown = compute_trust_score(context, theme_path)
    output = format_output(context, trust_score, breakdown)

    # R3: Save brief for later calibration
    try:
        from .session_logger import get_session_id, save_brief_output
        save_brief_output(get_session_id(), output)
    except Exception:
        pass

    return output


def _auto_learn_recent(max_sessions: int = 3):
    """Piggyback: learn + calibrate from unprocessed sessions."""
    try:
        from .session_logger import get_unprocessed_sessions
        from .learner import learn_from_session, calibrate_trust_baselines
        from .calibrator import calibrate_trust_from_session

        sessions = get_unprocessed_sessions(min_writes=1)
        learned_count = 0
        for s in sessions[:max_sessions]:
            learn_from_session(s["session_id"])
            # R3: calibrate after learning
            calibrate_trust_from_session(s["session_id"])
            learned_count += 1

        if learned_count > 0:
            from .session_logger import _get_conn
            conn = _get_conn()
            total = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE processed = 1"
            ).fetchone()[0]
            if total > 0 and total % 10 == 0:
                calibrate_trust_baselines()
    except Exception:
        pass
```

## Asymmetric Calibration — Rationale

```
Sai = nguy hiểm (Claude waste tokens, code sai) → giảm nhanh
Đúng = cần chứng minh nhiều lần → tăng chậm

Recovery math:
  -0.15 (all_negative) → cần 3 × +0.05 = 3 positive sessions minimum
  -0.08 (mostly_negative) → cần 2 × +0.05 = 2 positive sessions minimum
```

## Calibration Timeline (Expected)

```
Session 1-3:  Trust = 0.5 (initial, neutral)
Session 4-6:  Trust = 0.6-0.65 (if brief useful)
Session 7-10: Trust = 0.7-0.75 (stabilizing)
Session 11+:  Trust oscillates 0.7-0.85 (steady state)
```

## Verification Plan

```python
# test_calibrator.py

def test_trust_decreases_on_all_negative():
    """Trust drops -0.15 when all 3 signals are negative."""
    # Setup: insert brief_log + session_log entries simulating:
    #   - Claude re-read all briefed files
    #   - Claude edited same file 3+ times
    #   - Kiwi blocked after write
    # Assert: trust_baselines[task_type] decreased by 0.15

def test_trust_increases_on_all_positive():
    """Trust rises +0.05 when no negative signals."""
    # Setup: session with no re-reads, no multi-edits, no violations
    # Assert: trust_baselines[task_type] increased by 0.05

def test_skip_short_session():
    """Sessions with < 2 writes are skipped."""
    # Assert: returns {'status': 'skipped', 'reason': 'too_short'}

def test_skip_task_changed():
    """Sessions where written files don't overlap brief are skipped."""
    # Assert: returns {'status': 'skipped', 'reason': 'task_changed'}

def test_fifo_eviction():
    """calibration_events capped at 500 rows."""
    # Insert 510 events, verify only 500 remain

def test_no_brief_returns_early():
    """Sessions without stored brief return no_brief."""
    # Assert: returns {'status': 'no_brief', 'action': 'none'}
```

## Data Flow Diagram

```
kiwi_reason(task, theme)
    │
    ├─ _auto_learn_recent()
    │     ├─ learn_from_session(sid)     ← R2
    │     └─ calibrate_trust_from_session(sid)  ← R3 NEW
    │           ├─ get_brief_for_session(sid)    ← brief_log table
    │           ├─ get_session_reads(sid)        ← session_log table
    │           ├─ get_session_writes(sid)       ← session_log table
    │           ├─ compute 3 signals
    │           ├─ _set_trust_baseline()         ← trust_baselines table
    │           └─ _save_calibration_event()     ← calibration_events table
    │
    ├─ assemble_context()
    ├─ compute_trust_score()
    │     └─ _blend_with_baseline()  ← reads trust_baselines (now R3-calibrated)
    ├─ format_output()
    └─ save_brief_output(sid, output)  ← R3 NEW: persist for next calibration
```

## Checklist trước khi code

- [ ] Add `calibration_events` + `brief_log` tables to `schema.sql`
- [ ] Add `save_brief_output()`, `get_brief_for_session()`, `get_session_log_entries()` to `session_logger.py`
- [ ] Create `calibrator.py` with full logic
- [ ] Update `__init__.py` to wire calibrator + save brief
- [ ] Add migration logic (auto-create tables if missing, like existing `_table_exists` pattern)
- [ ] Write `test_calibrator.py`
- [ ] Run integration test end-to-end
