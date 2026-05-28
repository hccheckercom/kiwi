# Phase R0 — Session Capture Infrastructure [3 ngày]

## Mục đích

Toàn bộ learning pipeline (R2, R3, R4) phụ thuộc vào session log.
Không có data → không có gì để học. Đây là PREREQUISITE.

## Vấn đề hiện tại

- Claude Code không export structured session logs mặc định
- `post_edit.py` hook chỉ thấy 1 file tại 1 thời điểm, không thấy toàn bộ session flow
- Không có mechanism capture "Claude đọc file A trước file B" (read order)
- Không biết session bắt đầu/kết thúc khi nào

## Giải pháp: Extend PostToolUse hook

Không cần full content — chỉ cần **tool name + file path + timestamp** là đủ.

### Schema

```sql
-- File: agent/reasoning/session_db.py
CREATE TABLE session_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,       -- UUID, tạo mới mỗi khi Claude Code start
    tool TEXT NOT NULL,             -- 'Read', 'Write', 'Edit', 'Grep', 'Glob', 'Bash'
    file_path TEXT,                 -- file liên quan (nullable cho Bash)
    action TEXT,                    -- 'read', 'write', 'edit', 'search'
    metadata TEXT,                  -- JSON: extra info (search query, edit size, etc.)
    timestamp REAL NOT NULL,        -- time.time()
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_session ON session_log(session_id);
CREATE INDEX idx_tool ON session_log(tool);
CREATE INDEX idx_file ON session_log(file_path);
CREATE INDEX idx_timestamp ON session_log(timestamp);

-- Session metadata
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,            -- NULL nếu chưa kết thúc
    task_hint TEXT,                 -- user's first message (truncated 200 chars)
    files_read INTEGER DEFAULT 0,
    files_written INTEGER DEFAULT 0,
    theme_path TEXT                 -- detected theme path (nếu có)
);
```

### Hook implementation

```python
# File: agent/reasoning/session_hook.py
"""
Extend existing post_edit.py hook.
Ghi mỗi tool call vào SQLite. Append-only, lightweight.
"""

import sqlite3
import time
import uuid
import json
import os
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "memory" / "sessions.db"
_session_id = None

def get_session_id() -> str:
    """Lazy init session ID. Persists for lifetime of hook process."""
    global _session_id
    if _session_id is None:
        _session_id = str(uuid.uuid4())[:8]
        _init_session()
    return _session_id

def _init_session():
    """Register new session in DB."""
    conn = _get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO sessions (session_id, started_at) VALUES (?, ?)",
        (get_session_id(), time.time())
    )
    conn.commit()

def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")  # concurrent reads
    return conn

def log_tool_call(tool: str, file_path: str = None, metadata: dict = None):
    """
    Main entry point. Call from PostToolUse hook.
    ~0.5ms per call (SQLite WAL mode).
    """
    conn = _get_conn()
    conn.execute(
        "INSERT INTO session_log (session_id, tool, file_path, action, metadata, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            get_session_id(),
            tool,
            file_path,
            _infer_action(tool),
            json.dumps(metadata) if metadata else None,
            time.time(),
        )
    )
    
    # Update session counters
    if tool == 'Read':
        conn.execute(
            "UPDATE sessions SET files_read = files_read + 1 WHERE session_id = ?",
            (get_session_id(),)
        )
    elif tool in ('Write', 'Edit'):
        conn.execute(
            "UPDATE sessions SET files_written = files_written + 1 WHERE session_id = ?",
            (get_session_id(),)
        )
    
    conn.commit()
    conn.close()

def _infer_action(tool: str) -> str:
    return {
        'Read': 'read',
        'Write': 'write', 
        'Edit': 'edit',
        'Grep': 'search',
        'Glob': 'search',
        'Bash': 'shell',
    }.get(tool, 'other')
```

### Integration với existing hook

```python
# File: hooks/post_edit.py (EXTEND, không replace)
# Thêm ở đầu file:

from agent.reasoning.session_hook import log_tool_call

def post_tool_use(tool: str, file_path: str, **kwargs):
    # EXISTING: scan for violations
    if tool in ('Write', 'Edit') and is_theme_file(file_path):
        violations = kiwi_scan(file_path)
        # ... existing logic ...
    
    # NEW: log tool call (always, mọi tool)
    log_tool_call(tool, file_path, metadata=kwargs.get('metadata'))
```

### Query helpers (cho R2, R3, R4 dùng)

```python
# File: agent/reasoning/session_query.py

def get_session_reads(session_id: str) -> list[dict]:
    """Get all Read calls in a session, ordered by timestamp."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT file_path, timestamp FROM session_log "
        "WHERE session_id = ? AND tool = 'Read' ORDER BY timestamp",
        (session_id,)
    ).fetchall()
    return [{'file': r[0], 'timestamp': r[1]} for r in rows]

def get_session_writes(session_id: str) -> list[dict]:
    """Get all Write/Edit calls in a session."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT file_path, tool, timestamp FROM session_log "
        "WHERE session_id = ? AND tool IN ('Write', 'Edit') ORDER BY timestamp",
        (session_id,)
    ).fetchall()
    return [{'file': r[0], 'tool': r[1], 'timestamp': r[2]} for r in rows]

def get_read_order_before_write(session_id: str, write_path: str) -> list[str]:
    """Files Claude read BEFORE writing to a specific file."""
    conn = _get_conn()
    write_time = conn.execute(
        "SELECT MIN(timestamp) FROM session_log "
        "WHERE session_id = ? AND file_path = ? AND tool IN ('Write', 'Edit')",
        (session_id, write_path)
    ).fetchone()[0]
    
    if not write_time:
        return []
    
    rows = conn.execute(
        "SELECT file_path FROM session_log "
        "WHERE session_id = ? AND tool = 'Read' AND timestamp < ? "
        "ORDER BY timestamp",
        (session_id, write_time)
    ).fetchall()
    return [r[0] for r in rows]

def get_recent_sessions(days: int = 7) -> list[dict]:
    """Get sessions from last N days."""
    cutoff = time.time() - (days * 86400)
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM sessions WHERE started_at > ? ORDER BY started_at DESC",
        (cutoff,)
    ).fetchall()
    return rows
```

## Deliverable

- SQLite DB tại `.claude/kiwi/memory/sessions.db`
- Hook ghi mọi tool call (~0.5ms overhead, không ảnh hưởng UX)
- Query helpers cho downstream phases
- Session ID auto-generated, no user intervention

## Verification

```python
# Test: hook ghi đúng
log_tool_call('Read', 'themes/sfvn/templates/cart.php')
log_tool_call('Read', 'themes/sfvn/templates/checkout.php')
log_tool_call('Write', 'themes/sfvn/templates/checkout.php')

reads = get_session_reads(get_session_id())
assert len(reads) == 2
assert reads[0]['file'].endswith('cart.php')  # order preserved

order = get_read_order_before_write(get_session_id(), 'themes/sfvn/templates/checkout.php')
assert 'cart.php' in order[0]  # Claude đọc cart trước khi code checkout
```

## Constraints

- KHÔNG log file content (quá lớn, privacy concern)
- KHÔNG log user messages (chỉ tool calls)
- WAL mode cho concurrent access (hook + learner có thể chạy song song)
- Auto-cleanup: sessions > 90 ngày → archive/delete