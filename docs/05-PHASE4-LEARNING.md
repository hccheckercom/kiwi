# Phase 4: Learning & Memory

## Mục tiêu

Kiwi càng dùng càng thông minh: ít false positives, tự adjust severity, phát hiện regression, đề xuất lesson mới.

## SQLite Database

**File:** `.claude/kiwi/kiwi.db`

### Schema

```sql
-- Lịch sử scan
CREATE TABLE scan_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    path        TEXT NOT NULL,           -- project path
    timestamp   TEXT NOT NULL,           -- ISO 8601
    platform    TEXT,                    -- wp | nextjs
    severity    TEXT,                    -- filter used
    mode        TEXT,                    -- review | interactive | auto
    violations_total    INTEGER DEFAULT 0,
    violations_critical INTEGER DEFAULT 0,
    violations_high     INTEGER DEFAULT 0,
    violations_suggest  INTEGER DEFAULT 0,
    violations_fixed    INTEGER DEFAULT 0,
    patterns_checked    INTEGER DEFAULT 0,
    files_scanned       INTEGER DEFAULT 0,
    duration_ms         INTEGER DEFAULT 0,
    agent_iterations    INTEGER DEFAULT 0
);

CREATE INDEX idx_scan_path ON scan_history(path);
CREATE INDEX idx_scan_time ON scan_history(timestamp);

-- False positives — user dismissed violations
CREATE TABLE false_positives (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id   TEXT NOT NULL,           -- LES-016
    file        TEXT NOT NULL,           -- relative path
    line        INTEGER DEFAULT 0,
    match_text  TEXT,                    -- matched content
    reason      TEXT,                    -- why dismissed
    dismissed_at TEXT NOT NULL,          -- ISO 8601
    scope       TEXT DEFAULT 'file',    -- file | project | global
    -- scope=file: suppress this violation in this file only
    -- scope=project: suppress this lesson in this project
    -- scope=global: suppress this lesson everywhere
    active      BOOLEAN DEFAULT 1
);

CREATE INDEX idx_fp_lesson ON false_positives(lesson_id);
CREATE INDEX idx_fp_file ON false_positives(file);

-- Per-lesson confidence tracking
CREATE TABLE lesson_confidence (
    lesson_id           TEXT PRIMARY KEY,
    total_hits          INTEGER DEFAULT 0,  -- total violations found
    true_positive_count INTEGER DEFAULT 0,  -- confirmed real bugs
    false_positive_count INTEGER DEFAULT 0, -- user dismissed
    fix_success_count   INTEGER DEFAULT 0,  -- fixes verified
    fix_failure_count   INTEGER DEFAULT 0,  -- fixes caused regression
    confidence          REAL DEFAULT 1.0,   -- 0.0 to 1.0
    effective_severity  TEXT,               -- may differ from lesson severity
    last_hit            TEXT,               -- last time violation found
    last_updated        TEXT                -- last confidence recalc
);

-- Fix outcomes — what happened after fix was applied
CREATE TABLE fix_outcomes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id       TEXT NOT NULL,
    file            TEXT NOT NULL,
    fix_type        TEXT NOT NULL,        -- replace | template | llm | manual
    applied_at      TEXT NOT NULL,        -- ISO 8601
    scan_id         INTEGER,             -- FK to scan_history
    verified        BOOLEAN DEFAULT 0,   -- re-scan confirmed fix
    rolled_back     BOOLEAN DEFAULT 0,   -- fix caused regression
    new_violations  INTEGER DEFAULT 0,   -- violations introduced by fix
    diff_preview    TEXT,                -- unified diff of the fix
    FOREIGN KEY (scan_id) REFERENCES scan_history(id)
);

CREATE INDEX idx_fix_lesson ON fix_outcomes(lesson_id);

-- Auto-suggested lessons — patterns agent found but not in Kiwi
CREATE TABLE suggested_lessons (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern         TEXT NOT NULL,        -- regex pattern
    scope           TEXT NOT NULL,        -- file glob
    category        TEXT,                -- suggested category
    severity        TEXT,                -- suggested severity
    example_file    TEXT,                -- where first found
    example_line    INTEGER,
    example_code    TEXT,                -- code snippet
    suggested_at    TEXT NOT NULL,
    status          TEXT DEFAULT 'pending',  -- pending | accepted | rejected
    lesson_id       TEXT                 -- if accepted, the created lesson ID
);
```

## Module Structure

```
.claude/kiwi/memory/
├── __init__.py
├── db.py               # SQLite operations (CRUD)
├── confidence.py        # Confidence scoring algorithm
└── trends.py            # Trend analysis & reporting
```

### `db.py` — Database Operations

```python
"""SQLite operations for Kiwi memory."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "kiwi.db"

def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    """Create tables if not exist."""
    conn = get_connection()
    conn.executescript(SCHEMA_SQL)
    conn.close()

def log_scan(path, platform, severity, report, duration_ms, mode="cli"):
    """Record a scan in history."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO scan_history 
        (path, timestamp, platform, severity, mode,
         violations_total, violations_critical, violations_high, violations_suggest,
         patterns_checked, files_scanned, duration_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        path, _now(), platform, severity, mode,
        len(report.violations), report.critical_count,
        report.high_count, report.suggest_count,
        report.patterns_checked, report.files_scanned, duration_ms
    ))
    conn.commit()
    scan_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return scan_id

def dismiss_violation(lesson_id, file, line, match_text, reason, scope="file"):
    """Record a false positive dismissal."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO false_positives 
        (lesson_id, file, line, match_text, reason, dismissed_at, scope)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (lesson_id, file, line, match_text, reason, _now(), scope))
    conn.commit()
    conn.close()

def is_dismissed(lesson_id, file, line=None):
    """Check if a violation is dismissed (false positive)."""
    conn = get_connection()
    # Check global dismissals
    row = conn.execute(
        "SELECT 1 FROM false_positives WHERE lesson_id=? AND scope='global' AND active=1",
        (lesson_id,)
    ).fetchone()
    if row:
        conn.close()
        return True
    # Check file-level
    row = conn.execute(
        "SELECT 1 FROM false_positives WHERE lesson_id=? AND file=? AND active=1",
        (lesson_id, file)
    ).fetchone()
    if row:
        conn.close()
        return True
    conn.close()
    return False

def log_fix(lesson_id, file, fix_type, scan_id=None, verified=False, diff=""):
    """Record a fix outcome."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO fix_outcomes 
        (lesson_id, file, fix_type, applied_at, scan_id, verified, diff_preview)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (lesson_id, file, fix_type, _now(), scan_id, verified, diff))
    conn.commit()
    conn.close()

def _now():
    return datetime.now(timezone.utc).isoformat()
```

### `confidence.py` — Scoring Algorithm

```python
"""Confidence scoring for Kiwi lessons."""

from .db import get_connection

def recalculate_confidence(lesson_id: str) -> float:
    """Recalculate confidence for a lesson based on outcomes.
    
    Formula:
    confidence = 1.0 - (false_positive_count / max(total_hits, 1))
    
    Adjusted by fix success rate:
    if fix_success > 0:
        fix_rate = fix_success / (fix_success + fix_failure)
        confidence = confidence * 0.7 + fix_rate * 0.3
    
    Returns: float 0.0 to 1.0
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM lesson_confidence WHERE lesson_id=?", (lesson_id,)
    ).fetchone()
    
    if not row:
        conn.close()
        return 1.0
    
    total = max(row["total_hits"], 1)
    fp_rate = row["false_positive_count"] / total
    base_confidence = 1.0 - fp_rate
    
    fix_success = row["fix_success_count"]
    fix_failure = row["fix_failure_count"]
    if fix_success + fix_failure > 0:
        fix_rate = fix_success / (fix_success + fix_failure)
        confidence = base_confidence * 0.7 + fix_rate * 0.3
    else:
        confidence = base_confidence
    
    # Determine effective severity
    original_severity = _get_lesson_severity(lesson_id)
    if confidence < 0.3:
        effective = "SUGGEST"  # demote noisy lessons
    elif confidence < 0.5 and original_severity == "HIGH":
        effective = "SUGGEST"
    else:
        effective = original_severity
    
    conn.execute("""
        UPDATE lesson_confidence 
        SET confidence=?, effective_severity=?, last_updated=?
        WHERE lesson_id=?
    """, (round(confidence, 3), effective, _now(), lesson_id))
    conn.commit()
    conn.close()
    
    return confidence

def update_hit(lesson_id: str, is_true_positive: bool = True):
    """Record a new hit for a lesson."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO lesson_confidence (lesson_id, total_hits, true_positive_count, last_hit)
        VALUES (?, 1, ?, ?)
        ON CONFLICT(lesson_id) DO UPDATE SET
            total_hits = total_hits + 1,
            true_positive_count = true_positive_count + ?,
            last_hit = ?
    """, (lesson_id, int(is_true_positive), _now(), int(is_true_positive), _now()))
    conn.commit()
    conn.close()
```

### `trends.py` — Trend Analysis

```python
"""Trend analysis for Kiwi scan history."""

from .db import get_connection

def violation_trend(path: str, days: int = 30) -> list[dict]:
    """Get violation count over time for a project.
    
    Returns: [{"date": "2026-05-23", "critical": 5, "high": 12, "total": 20}, ...]
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT date(timestamp) as date,
               SUM(violations_critical) as critical,
               SUM(violations_high) as high,
               SUM(violations_total) as total,
               SUM(violations_fixed) as fixed
        FROM scan_history
        WHERE path=? AND timestamp >= datetime('now', ?)
        GROUP BY date(timestamp)
        ORDER BY date
    """, (path, f"-{days} days")).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def regression_check(path: str) -> list[dict]:
    """Compare last 2 scans — detect new violations.
    
    Returns: list of new violation categories since last scan
    """
    conn = get_connection()
    last_two = conn.execute("""
        SELECT * FROM scan_history 
        WHERE path=? ORDER BY timestamp DESC LIMIT 2
    """, (path,)).fetchall()
    conn.close()
    
    if len(last_two) < 2:
        return []
    
    current, previous = last_two[0], last_two[1]
    regressions = []
    
    if current["violations_critical"] > previous["violations_critical"]:
        regressions.append({
            "severity": "CRITICAL",
            "delta": current["violations_critical"] - previous["violations_critical"],
            "message": f"CRITICAL violations increased: {previous['violations_critical']} → {current['violations_critical']}"
        })
    
    if current["violations_high"] > previous["violations_high"]:
        regressions.append({
            "severity": "HIGH",
            "delta": current["violations_high"] - previous["violations_high"],
            "message": f"HIGH violations increased: {previous['violations_high']} → {current['violations_high']}"
        })
    
    return regressions

def top_noisy_lessons(min_fps: int = 3) -> list[dict]:
    """Find lessons with highest false positive rate.
    
    Returns lessons that should be reviewed/tuned.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT lesson_id, total_hits, false_positive_count, confidence
        FROM lesson_confidence
        WHERE false_positive_count >= ?
        ORDER BY confidence ASC
        LIMIT 20
    """, (min_fps,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

## Integration with Scanner

### Modified scan flow (Phase 4):

```python
# In scanner/cli.py or mcp_server.py
import time
from memory.db import log_scan, is_dismissed
from memory.confidence import update_hit

def scan_with_memory(theme_path, **kwargs):
    start = time.time()
    report = scan_theme(theme_path, **kwargs)
    duration = int((time.time() - start) * 1000)
    
    # Filter out dismissed false positives
    filtered = []
    for v in report.violations:
        if is_dismissed(v.lesson_id, v.file, v.line):
            continue
        filtered.append(v)
        update_hit(v.lesson_id, is_true_positive=True)
    
    report.violations = filtered
    
    # Log scan history
    log_scan(theme_path, kwargs.get("platform"), 
             kwargs.get("severity_filter", "ALL"),
             report, duration)
    
    return report
```

## MCP Tools (Phase 4)

### `kiwi_dismiss`
```json
{
  "name": "kiwi_dismiss",
  "description": "Mark a violation as false positive. Sẽ không hiện lại trong scan tương lai.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "lesson_id": {"type": "string"},
      "file": {"type": "string"},
      "reason": {"type": "string", "description": "Tại sao đây là false positive"},
      "scope": {"type": "string", "enum": ["file", "project", "global"], "default": "file"}
    },
    "required": ["lesson_id", "file", "reason"]
  }
}
```

### `kiwi_trends`
```json
{
  "name": "kiwi_trends",
  "description": "Xem trend violations theo thời gian. Phát hiện regression.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {"type": "string"},
      "days": {"type": "integer", "default": 30}
    },
    "required": ["path"]
  }
}
```

### `kiwi_confidence`
```json
{
  "name": "kiwi_confidence",
  "description": "Xem confidence score các lessons. Lessons noisy sẽ bị tự động demote.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "lesson_id": {"type": "string", "description": "Specific lesson, hoặc bỏ trống để xem top noisy"},
      "min_fps": {"type": "integer", "default": 3}
    }
  }
}
```

## Verification

1. **Init DB:**
   ```python
   from memory.db import init_db
   init_db()
   # Verify kiwi.db created with correct tables
   ```

2. **Scan logging:**
   ```python
   # Run 3 scans → check scan_history has 3 rows
   from memory.db import get_connection
   conn = get_connection()
   count = conn.execute("SELECT COUNT(*) FROM scan_history").fetchone()[0]
   assert count == 3
   ```

3. **False positive flow:**
   ```python
   dismiss_violation("LES-006", "src/test.css", 42, "#ff0000", "This is a token definition file")
   assert is_dismissed("LES-006", "src/test.css") == True
   assert is_dismissed("LES-006", "src/other.css") == False  # different file
   ```

4. **Confidence scoring:**
   ```python
   # Lesson with 10 hits, 3 false positives → confidence = 0.7
   update_hit("LES-006", True)  # x7
   update_hit("LES-006", False) # x3 (false positive)
   conf = recalculate_confidence("LES-006")
   assert 0.65 < conf < 0.75
   ```

5. **Trend analysis:**
   ```python
   trend = violation_trend("wezone-plugins", days=7)
   # Returns daily violation counts
   ```