-- Kiwi Confidence Scoring System Schema
-- Tracks false positives, true positives, and auto-demotes noisy lessons

CREATE TABLE IF NOT EXISTS lessons (
    lesson_id TEXT PRIMARY KEY,
    true_positive_count INTEGER DEFAULT 0,
    false_positive_count INTEGER DEFAULT 0,
    confidence_score REAL DEFAULT 1.0,
    original_severity TEXT,
    current_severity TEXT,
    auto_demoted INTEGER DEFAULT 0,
    last_updated TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    path TEXT NOT NULL,
    platform TEXT,
    violations_count INTEGER DEFAULT 0,
    duration_ms INTEGER
);

CREATE TABLE IF NOT EXISTS dismissals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id TEXT NOT NULL,
    file TEXT NOT NULL,
    line INTEGER,
    reason TEXT NOT NULL,
    scope TEXT DEFAULT 'file',
    dismissed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lesson_id) REFERENCES lessons(lesson_id)
);

CREATE INDEX IF NOT EXISTS idx_dismissals_lesson ON dismissals(lesson_id);
CREATE INDEX IF NOT EXISTS idx_dismissals_file ON dismissals(file);
CREATE INDEX IF NOT EXISTS idx_scans_timestamp ON scans(timestamp);