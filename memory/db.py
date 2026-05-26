"""SQLite operations for Kiwi memory."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "kiwi.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS scan_history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    path                TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    platform            TEXT,
    severity            TEXT,
    mode                TEXT,
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

CREATE INDEX IF NOT EXISTS idx_scan_path ON scan_history(path);
CREATE INDEX IF NOT EXISTS idx_scan_time ON scan_history(timestamp);

CREATE TABLE IF NOT EXISTS false_positives (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id       TEXT NOT NULL,
    file            TEXT NOT NULL,
    line            INTEGER DEFAULT 0,
    match_text      TEXT,
    reason          TEXT,
    dismissed_at    TEXT NOT NULL,
    scope           TEXT DEFAULT 'file',
    active          BOOLEAN DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_fp_lesson ON false_positives(lesson_id);
CREATE INDEX IF NOT EXISTS idx_fp_file ON false_positives(file);

CREATE TABLE IF NOT EXISTS lesson_confidence (
    lesson_id           TEXT PRIMARY KEY,
    total_hits          INTEGER DEFAULT 0,
    true_positive_count INTEGER DEFAULT 0,
    false_positive_count INTEGER DEFAULT 0,
    fix_success_count   INTEGER DEFAULT 0,
    fix_failure_count   INTEGER DEFAULT 0,
    confidence          REAL DEFAULT 1.0,
    effective_severity  TEXT,
    disabled            INTEGER DEFAULT 0,
    disabled_reason     TEXT,
    disabled_at         TEXT,
    last_hit            TEXT,
    last_updated        TEXT
);

CREATE TABLE IF NOT EXISTS fix_outcomes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id       TEXT NOT NULL,
    file            TEXT NOT NULL,
    fix_type        TEXT NOT NULL,
    applied_at      TEXT NOT NULL,
    scan_id         INTEGER,
    verified        BOOLEAN DEFAULT 0,
    rolled_back     BOOLEAN DEFAULT 0,
    new_violations  INTEGER DEFAULT 0,
    diff_preview    TEXT,
    FOREIGN KEY (scan_id) REFERENCES scan_history(id)
);

CREATE INDEX IF NOT EXISTS idx_fix_lesson ON fix_outcomes(lesson_id);

CREATE TABLE IF NOT EXISTS suggested_lessons (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern         TEXT NOT NULL,
    scope           TEXT NOT NULL,
    category        TEXT,
    severity        TEXT,
    example_file    TEXT,
    example_line    INTEGER,
    example_code    TEXT,
    suggested_at    TEXT NOT NULL,
    status          TEXT DEFAULT 'pending',
    lesson_id       TEXT
);

CREATE TABLE IF NOT EXISTS impact_analysis (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    fixed_file          TEXT NOT NULL,
    fixed_at            TEXT NOT NULL,
    symbols_changed     TEXT,
    affected_files      TEXT,
    risk_level          TEXT,
    regressions_found   INTEGER DEFAULT 0,
    scan_id             INTEGER,
    FOREIGN KEY (scan_id) REFERENCES scan_history(id)
);

CREATE TABLE IF NOT EXISTS approvals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    checkpoint_id   TEXT NOT NULL UNIQUE,
    decision        TEXT NOT NULL,
    comment         TEXT,
    user            TEXT NOT NULL,
    timestamp       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL UNIQUE,
    status          TEXT NOT NULL,
    project_path    TEXT NOT NULL,
    severity        TEXT NOT NULL,
    violations_found INTEGER DEFAULT 0,
    fixes_applied   INTEGER DEFAULT 0,
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    error           TEXT
);

CREATE INDEX IF NOT EXISTS idx_approvals_checkpoint ON approvals(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status);
CREATE INDEX IF NOT EXISTS idx_agent_runs_path ON agent_runs(project_path);

CREATE INDEX IF NOT EXISTS idx_impact_file ON impact_analysis(fixed_file);
CREATE INDEX IF NOT EXISTS idx_impact_time ON impact_analysis(fixed_at);

CREATE TABLE IF NOT EXISTS violations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         INTEGER NOT NULL,
    lesson_id       TEXT NOT NULL,
    file            TEXT NOT NULL,
    line            INTEGER DEFAULT 0,
    match_text      TEXT,
    severity        TEXT,
    category        TEXT,
    detected_at     TEXT NOT NULL,
    FOREIGN KEY (scan_id) REFERENCES scan_history(id)
);

CREATE INDEX IF NOT EXISTS idx_violations_scan ON violations(scan_id);
CREATE INDEX IF NOT EXISTS idx_violations_lesson ON violations(lesson_id);
CREATE INDEX IF NOT EXISTS idx_violations_file ON violations(file);
CREATE INDEX IF NOT EXISTS idx_violations_time ON violations(detected_at);

CREATE TABLE IF NOT EXISTS pattern_refinements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id TEXT NOT NULL,
    old_pattern TEXT NOT NULL,
    new_pattern TEXT NOT NULL,
    reason TEXT,
    fp_rate_before REAL,
    fp_rate_after REAL,
    timestamp TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_refinements_lesson ON pattern_refinements(lesson_id);
CREATE INDEX IF NOT EXISTS idx_refinements_time ON pattern_refinements(timestamp);

CREATE TABLE IF NOT EXISTS contextual_lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    context_pattern TEXT NOT NULL,
    violation_pattern TEXT NOT NULL,
    fix_pattern TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    examples TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    last_used TEXT
);

CREATE INDEX IF NOT EXISTS idx_contextual_context ON contextual_lessons(context_pattern);
CREATE INDEX IF NOT EXISTS idx_contextual_confidence ON contextual_lessons(confidence);

CREATE TABLE IF NOT EXISTS deployment_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    path            TEXT NOT NULL,
    deploy_type     TEXT NOT NULL,
    target          TEXT NOT NULL,
    user            TEXT,
    timestamp       TEXT NOT NULL,
    success         BOOLEAN DEFAULT 1,
    rollback        BOOLEAN DEFAULT 0,
    scan_passed     BOOLEAN DEFAULT 0,
    violations_critical INTEGER DEFAULT 0,
    violations_high INTEGER DEFAULT 0,
    health_check_passed BOOLEAN DEFAULT 0,
    error_message   TEXT,
    duration_ms     INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_deploy_path ON deployment_history(path);
CREATE INDEX IF NOT EXISTS idx_deploy_time ON deployment_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_deploy_target ON deployment_history(target);

CREATE TABLE IF NOT EXISTS embeddings (
    lesson_id TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scoring_feedback (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tool            TEXT NOT NULL,
    score_given     INTEGER NOT NULL,
    action_label    TEXT NOT NULL,
    outcome         TEXT,
    outcome_detail  TEXT,
    scored_at       TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sf_tool ON scoring_feedback(tool);
CREATE INDEX IF NOT EXISTS idx_sf_outcome ON scoring_feedback(outcome);

CREATE TABLE IF NOT EXISTS auto_tune_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id       TEXT NOT NULL,
    action          TEXT NOT NULL,
    old_severity    TEXT,
    new_severity    TEXT,
    reason          TEXT NOT NULL,
    timestamp       TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tune_lesson ON auto_tune_history(lesson_id);
CREATE INDEX IF NOT EXISTS idx_tune_time ON auto_tune_history(timestamp);

CREATE TABLE IF NOT EXISTS decay_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id       TEXT NOT NULL,
    old_confidence  REAL NOT NULL,
    new_confidence  REAL NOT NULL,
    days_since_hit  INTEGER NOT NULL,
    decay_amount    REAL NOT NULL,
    timestamp       TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_decay_lesson ON decay_history(lesson_id);
CREATE INDEX IF NOT EXISTS idx_decay_time ON decay_history(timestamp);

CREATE TABLE IF NOT EXISTS lesson_relations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_a        TEXT NOT NULL,
    lesson_b        TEXT NOT NULL,
    relation_type   TEXT NOT NULL,
    reason          TEXT,
    timestamp       TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_relations_a ON lesson_relations(lesson_a);
CREATE INDEX IF NOT EXISTS idx_relations_b ON lesson_relations(lesson_b);
CREATE INDEX IF NOT EXISTS idx_relations_type ON lesson_relations(relation_type);

CREATE TABLE IF NOT EXISTS feedback_adjustments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id       TEXT NOT NULL,
    old_confidence  REAL NOT NULL,
    new_confidence  REAL NOT NULL,
    dismissals      INTEGER NOT NULL,
    approvals       INTEGER NOT NULL,
    adjustment      REAL NOT NULL,
    timestamp       TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_feedback_lesson ON feedback_adjustments(lesson_id);
CREATE INDEX IF NOT EXISTS idx_feedback_time ON feedback_adjustments(timestamp);

CREATE TABLE IF NOT EXISTS ab_tests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id       TEXT NOT NULL,
    baseline_pattern TEXT NOT NULL,
    variant_pattern TEXT NOT NULL,
    description     TEXT,
    target_scans    INTEGER DEFAULT 100,
    status          TEXT DEFAULT 'active',
    winner          TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    completed_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_ab_lesson ON ab_tests(lesson_id);
CREATE INDEX IF NOT EXISTS idx_ab_status ON ab_tests(status);

CREATE TABLE IF NOT EXISTS ab_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id         INTEGER NOT NULL,
    version         TEXT NOT NULL,
    scan_id         INTEGER NOT NULL,
    true_positives  INTEGER DEFAULT 0,
    false_positives INTEGER DEFAULT 0,
    false_negatives INTEGER DEFAULT 0,
    fix_success     INTEGER DEFAULT 0,
    fix_failure     INTEGER DEFAULT 0,
    recorded_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (test_id) REFERENCES ab_tests(id),
    FOREIGN KEY (scan_id) REFERENCES scan_history(id)
);

CREATE INDEX IF NOT EXISTS idx_ab_results_test ON ab_results(test_id);
CREATE INDEX IF NOT EXISTS idx_ab_results_version ON ab_results(version);
"""


def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA_SQL)

    # Migration: Add disabled columns to existing lesson_confidence table
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(lesson_confidence)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'disabled' not in columns:
            cursor.execute("ALTER TABLE lesson_confidence ADD COLUMN disabled INTEGER DEFAULT 0")
        if 'disabled_reason' not in columns:
            cursor.execute("ALTER TABLE lesson_confidence ADD COLUMN disabled_reason TEXT")
        if 'disabled_at' not in columns:
            cursor.execute("ALTER TABLE lesson_confidence ADD COLUMN disabled_at TEXT")

        conn.commit()
    except Exception as e:
        print(f"Migration warning: {e}")

    conn.close()

    try:
        from . import coordination
        coordination.init_coordination_db()
    except ImportError:
        pass


def _now():
    return datetime.now(timezone.utc).isoformat()


def log_scan(path, platform=None, severity=None, mode="cli",
             violations_total=0, violations_critical=0,
             violations_high=0, violations_suggest=0,
             violations_fixed=0, patterns_checked=0,
             files_scanned=0, duration_ms=0, agent_iterations=0):
    conn = get_connection()
    conn.execute("""
        INSERT INTO scan_history
        (path, timestamp, platform, severity, mode,
         violations_total, violations_critical, violations_high, violations_suggest,
         violations_fixed, patterns_checked, files_scanned, duration_ms, agent_iterations)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        path, _now(), platform, severity, mode,
        violations_total, violations_critical, violations_high, violations_suggest,
        violations_fixed, patterns_checked, files_scanned, duration_ms, agent_iterations,
    ))
    conn.commit()
    scan_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return scan_id


def log_scan_from_report(path, report, duration_ms, platform=None, severity=None, mode="cli"):
    scan_id = log_scan(
        path=path, platform=platform, severity=severity, mode=mode,
        violations_total=len(report.violations),
        violations_critical=report.critical_count,
        violations_high=report.high_count,
        violations_suggest=report.suggest_count,
        patterns_checked=report.patterns_checked,
        files_scanned=report.files_scanned,
        duration_ms=duration_ms,
    )

    # Track violations in database for learning loop
    if report.violations:
        track_violations(scan_id, report.violations)

    return scan_id


def track_violations(scan_id, violations):
    """Track violations in database for pattern mining."""
    conn = get_connection()

    for v in violations:
        conn.execute("""
            INSERT INTO violations
            (scan_id, lesson_id, file, line, match_text, severity, category, detected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            scan_id,
            v.lesson_id,
            v.file,
            v.line,
            getattr(v, 'match_text', ''),
            v.severity,
            v.category,
            _now()
        ))

    conn.commit()
    conn.close()


def dismiss_violation(lesson_id, file, line=0, match_text="", reason="", scope="file"):
    conn = get_connection()
    conn.execute("""
        INSERT INTO false_positives
        (lesson_id, file, line, match_text, reason, dismissed_at, scope)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (lesson_id, file, line, match_text, reason, _now(), scope))
    conn.commit()
    conn.close()


def is_dismissed(lesson_id, file, line=None):
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM false_positives WHERE lesson_id=? AND scope='global' AND active=1",
        (lesson_id,)
    ).fetchone()
    if row:
        conn.close()
        return True

    row = conn.execute(
        "SELECT 1 FROM false_positives WHERE lesson_id=? AND file=? AND active=1",
        (lesson_id, file)
    ).fetchone()
    if row:
        conn.close()
        return True

    conn.close()
    return False


def get_dismissed_list(lesson_id=None):
    conn = get_connection()
    if lesson_id:
        rows = conn.execute(
            "SELECT * FROM false_positives WHERE lesson_id=? AND active=1 ORDER BY dismissed_at DESC",
            (lesson_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM false_positives WHERE active=1 ORDER BY dismissed_at DESC LIMIT 50"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def log_fix(lesson_id, file, fix_type, scan_id=None, verified=False, diff_preview=""):
    conn = get_connection()
    conn.execute("""
        INSERT INTO fix_outcomes
        (lesson_id, file, fix_type, applied_at, scan_id, verified, diff_preview)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (lesson_id, file, fix_type, _now(), scan_id, verified, diff_preview))
    conn.commit()
    conn.close()


def get_scan_history(path=None, limit=20):
    conn = get_connection()
    if path:
        rows = conn.execute(
            "SELECT * FROM scan_history WHERE path=? ORDER BY timestamp DESC LIMIT ?",
            (path, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM scan_history ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_fix_history(lesson_id=None, limit=20):
    conn = get_connection()
    if lesson_id:
        rows = conn.execute(
            "SELECT * FROM fix_outcomes WHERE lesson_id=? ORDER BY applied_at DESC LIMIT ?",
            (lesson_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM fix_outcomes ORDER BY applied_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def log_impact(fixed_file, symbols_changed, affected_files, risk_level, regressions_found=0, scan_id=None):
    """Log impact analysis result."""
    import json
    conn = get_connection()
    conn.execute("""
        INSERT INTO impact_analysis
        (fixed_file, fixed_at, symbols_changed, affected_files, risk_level, regressions_found, scan_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        fixed_file,
        _now(),
        json.dumps(symbols_changed) if symbols_changed else None,
        json.dumps(affected_files) if affected_files else None,
        risk_level,
        regressions_found,
        scan_id
    ))
    conn.commit()
    conn.close()


def get_impact_history(fixed_file=None, limit=20):
    """Get impact analysis history."""
    conn = get_connection()
    if fixed_file:
        rows = conn.execute(
            "SELECT * FROM impact_analysis WHERE fixed_file=? ORDER BY fixed_at DESC LIMIT ?",
            (fixed_file, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM impact_analysis ORDER BY fixed_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def log_violation(scan_id, lesson_id, file, line, match_text, severity, category):
    """Log individual violation for pattern mining."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO violations
        (scan_id, lesson_id, file, line, match_text, severity, category, detected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (scan_id, lesson_id, file, line, match_text, severity, category, _now()))
    conn.commit()
    conn.close()


def get_recent_violations(lookback_days=30, path=None):
    """Query recent violations for pattern mining."""
    conn = get_connection()
    query = """
        SELECT v.*, s.path as scan_path
        FROM violations v
        JOIN scan_history s ON v.scan_id = s.id
        WHERE v.detected_at >= datetime('now', ?)
    """
    params = [f"-{lookback_days} days"]
    if path:
        query += " AND s.path LIKE ?"
        params.append(f"%{path}%")
    query += " ORDER BY v.detected_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_project_violation_counts(path: str, limit_days: int = 90) -> dict:
    """Return {lesson_id: hit_count} for violations in the given project path."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT v.lesson_id, COUNT(*) as hit_count
        FROM violations v
        JOIN scan_history s ON v.scan_id = s.id
        WHERE s.path LIKE ?
          AND v.detected_at >= datetime('now', ?)
        GROUP BY v.lesson_id
    """, (f"%{path}%", f"-{limit_days} days")).fetchall()
    conn.close()
    return {r["lesson_id"]: r["hit_count"] for r in rows}


def get_all_confidence_scores() -> dict:
    """Return {lesson_id: confidence_float} for all non-disabled lessons."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT lesson_id, confidence
        FROM lesson_confidence
        WHERE disabled = 0
    """).fetchall()
    conn.close()
    return {r["lesson_id"]: r["confidence"] for r in rows}


def get_suggested_lessons(status="pending"):
    """Get suggested lessons for review."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM suggested_lessons
        WHERE status = ?
        ORDER BY suggested_at DESC
    """, (status,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_suggested_lesson_status(suggestion_id, status, lesson_id=None):
    """Update status of suggested lesson."""
    conn = get_connection()
    if lesson_id:
        conn.execute("UPDATE suggested_lessons SET status = ?, lesson_id = ? WHERE id = ?",
                    (status, lesson_id, suggestion_id))
    else:
        conn.execute("UPDATE suggested_lessons SET status = ? WHERE id = ?", (status, suggestion_id))
    conn.commit()
    conn.close()


def get_learned_fix(lesson_id: str) -> dict:
    """Get the most recent successful fix for a lesson, if any.

    Returns dict with fix_type, diff_preview, applied_count, or None.
    """
    conn = get_connection()
    row = conn.execute("""
        SELECT fix_type, diff_preview,
               COUNT(*) as applied_count
        FROM fix_outcomes
        WHERE lesson_id = ? AND verified = 1 AND rolled_back = 0
              AND diff_preview IS NOT NULL AND diff_preview != ''
        GROUP BY fix_type
        ORDER BY applied_count DESC, MAX(applied_at) DESC
        LIMIT 1
    """, (lesson_id,)).fetchone()
    conn.close()

    if not row:
        return None
    return {
        "lesson_id": lesson_id,
        "fix_type": row["fix_type"],
        "diff_preview": row["diff_preview"],
        "applied_count": row["applied_count"],
    }


def log_deployment(path, deploy_type, target, user=None, success=True, rollback=False,
                   scan_passed=False, violations_critical=0, violations_high=0,
                   health_check_passed=False, error_message=None, duration_ms=0):
    """Log deployment to history."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO deployment_history
        (path, deploy_type, target, user, timestamp, success, rollback, scan_passed,
         violations_critical, violations_high, health_check_passed, error_message, duration_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (path, deploy_type, target, user, _now(), success, rollback, scan_passed,
          violations_critical, violations_high, health_check_passed, error_message, duration_ms))
    conn.commit()
    conn.close()


def get_deployment_history(path=None, target=None, limit=50):
    """Query deployment history."""
    conn = get_connection()
    query = "SELECT * FROM deployment_history WHERE 1=1"
    params = []

    if path:
        query += " AND path LIKE ?"
        params.append(f"%{path}%")
    if target:
        query += " AND target = ?"
        params.append(target)

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]