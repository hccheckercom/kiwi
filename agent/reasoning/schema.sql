-- Kiwi Reasoning Layer — Session Learning Schema

CREATE TABLE IF NOT EXISTS session_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    tool TEXT NOT NULL,
    file_path TEXT,
    action TEXT,
    metadata TEXT,
    timestamp REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    started_at REAL,
    ended_at REAL,
    task_hint TEXT,
    files_read INTEGER DEFAULT 0,
    files_written INTEGER DEFAULT 0,
    theme_path TEXT,
    processed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS context_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    files_read TEXT NOT NULL,
    files_written TEXT NOT NULL,
    read_order TEXT,
    theme TEXT,
    session_id TEXT,
    created_at REAL
);

CREATE TABLE IF NOT EXISTS style_knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    theme TEXT NOT NULL,
    pattern_key TEXT NOT NULL,
    value TEXT NOT NULL,
    times_seen INTEGER DEFAULT 1,
    last_seen REAL,
    UNIQUE(theme, pattern_key)
);

CREATE TABLE IF NOT EXISTS binding_knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    binding TEXT NOT NULL,
    theme TEXT,
    times_seen INTEGER DEFAULT 1,
    last_seen REAL,
    UNIQUE(task_type, binding, theme)
);

CREATE TABLE IF NOT EXISTS trust_baselines (
    task_type TEXT PRIMARY KEY,
    trust_score REAL DEFAULT 0.5,
    last_calibrated REAL,
    calibration_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS output_quality (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    week INTEGER NOT NULL,
    task_type TEXT NOT NULL,
    brief_version INTEGER DEFAULT 0,
    trust_score REAL,
    tokens_estimated INTEGER,
    files_re_read INTEGER DEFAULT 0,
    edits_after_first INTEGER DEFAULT 0,
    total_tool_calls INTEGER DEFAULT 0,
    brief_level INTEGER DEFAULT 0,
    autonomy_level TEXT DEFAULT 'none',
    draft_outcome TEXT,
    session_duration_sec REAL DEFAULT 0,
    created_at REAL
);

CREATE INDEX IF NOT EXISTS idx_sl_session ON session_log(session_id);
CREATE INDEX IF NOT EXISTS idx_sl_tool ON session_log(tool);
CREATE INDEX IF NOT EXISTS idx_sl_file ON session_log(file_path);
CREATE INDEX IF NOT EXISTS idx_sl_ts ON session_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_cp_task ON context_patterns(task_type);
CREATE INDEX IF NOT EXISTS idx_sk_theme ON style_knowledge(theme);
CREATE INDEX IF NOT EXISTS idx_bk_task ON binding_knowledge(task_type);
CREATE INDEX IF NOT EXISTS idx_oq_week ON output_quality(week);

-- R3: Trust Calibration
CREATE TABLE IF NOT EXISTS calibration_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    signals TEXT,
    trust_before REAL,
    trust_after REAL,
    delta REAL,
    reason TEXT,
    created_at REAL
);

CREATE TABLE IF NOT EXISTS brief_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE,
    task_type TEXT NOT NULL,
    files_needed TEXT,
    trust_score REAL,
    recommendation TEXT,
    created_at REAL
);

CREATE INDEX IF NOT EXISTS idx_ce_session ON calibration_events(session_id);
CREATE INDEX IF NOT EXISTS idx_ce_task ON calibration_events(task_type);
CREATE INDEX IF NOT EXISTS idx_bl_session ON brief_log(session_id);

-- R4: Novel patterns Claude uses that Kiwi doesn't know
CREATE TABLE IF NOT EXISTS novel_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL,
    pattern_type TEXT NOT NULL,
    source_file TEXT,
    theme TEXT,
    task_type TEXT,
    times_seen INTEGER DEFAULT 1,
    first_seen REAL,
    last_seen REAL,
    promoted INTEGER DEFAULT 0,
    UNIQUE(pattern, pattern_type, theme)
);

-- R4/R5: Cross-theme pattern transfer (multi-pattern with layout clustering)
CREATE TABLE IF NOT EXISTS cross_theme_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    layout_hash TEXT NOT NULL DEFAULT '',
    structure TEXT,
    themes_applied TEXT,
    bindings TEXT,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    last_updated REAL,
    UNIQUE(task_type, layout_hash)
);

-- R4: Proactive warning history
CREATE TABLE IF NOT EXISTS warnings_issued (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    task_type TEXT NOT NULL,
    warning_type TEXT NOT NULL,
    message TEXT,
    was_useful INTEGER DEFAULT NULL,
    created_at REAL
);

CREATE INDEX IF NOT EXISTS idx_np_pattern ON novel_patterns(pattern, pattern_type);
CREATE INDEX IF NOT EXISTS idx_np_theme ON novel_patterns(theme);
CREATE INDEX IF NOT EXISTS idx_ctp_task ON cross_theme_patterns(task_type);
CREATE INDEX IF NOT EXISTS idx_wi_task ON warnings_issued(task_type);

-- R5: Auto-promote pipeline suggestions
CREATE TABLE IF NOT EXISTS promotion_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL,
    pattern_type TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'SUGGEST',
    theme TEXT,
    task_type TEXT,
    times_seen INTEGER DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at REAL
);

CREATE INDEX IF NOT EXISTS idx_ps_status ON promotion_suggestions(status);

-- R6: Draft outcome tracking for graduated autonomy
CREATE TABLE IF NOT EXISTS draft_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    task_type TEXT NOT NULL,
    level TEXT NOT NULL,
    outcome TEXT NOT NULL,
    changes_made INTEGER DEFAULT 0,
    created_at REAL
);

CREATE INDEX IF NOT EXISTS idx_do_task ON draft_outcomes(task_type, level);

-- R8: Selective Thinking — LLM reasoning for edge cases
CREATE TABLE IF NOT EXISTS think_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    trigger TEXT NOT NULL,
    task_type TEXT,
    theme TEXT,
    decision TEXT,
    confidence REAL,
    tokens_used INTEGER DEFAULT 0,
    cached INTEGER DEFAULT 0,
    success INTEGER DEFAULT NULL,
    created_at REAL
);

CREATE TABLE IF NOT EXISTS think_cache (
    cache_key TEXT PRIMARY KEY,
    trigger TEXT NOT NULL,
    task_type TEXT,
    theme TEXT,
    decision TEXT NOT NULL,
    reasoning TEXT,
    confidence REAL DEFAULT 0.5,
    extra TEXT,
    created_at REAL
);

CREATE INDEX IF NOT EXISTS idx_te_session ON think_events(session_id);
CREATE INDEX IF NOT EXISTS idx_te_trigger ON think_events(trigger);
CREATE INDEX IF NOT EXISTS idx_tc_trigger ON think_cache(trigger);