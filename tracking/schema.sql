CREATE TABLE IF NOT EXISTS usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    session_id TEXT,
    operation TEXT NOT NULL,
    sub_operation TEXT,
    target_path TEXT,
    tokens_local INTEGER DEFAULT 0,
    tokens_claude INTEGER DEFAULT 0,
    cost_actual_usd REAL DEFAULT 0.0,
    latency_ms INTEGER DEFAULT 0,
    tokens_baseline INTEGER NOT NULL,
    cost_baseline_usd REAL NOT NULL,
    latency_baseline_ms INTEGER,
    violations_found INTEGER DEFAULT 0,
    files_processed INTEGER DEFAULT 0,
    success INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_usage_operation ON usage_events(operation);

CREATE VIEW IF NOT EXISTS savings_daily AS
SELECT
    date(timestamp, 'unixepoch', 'localtime') as day,
    COUNT(*) as total_ops,
    SUM(CASE WHEN tokens_claude = 0 THEN 1 ELSE 0 END) as local_ops,
    ROUND(SUM(cost_actual_usd), 4) as actual_usd,
    ROUND(SUM(cost_baseline_usd), 4) as baseline_usd,
    ROUND(SUM(cost_baseline_usd) - SUM(cost_actual_usd), 4) as saved_usd,
    SUM(tokens_local) as tokens_local_total,
    SUM(tokens_baseline) as tokens_baseline_total
FROM usage_events
GROUP BY day
ORDER BY day DESC;

CREATE VIEW IF NOT EXISTS savings_cumulative AS
SELECT
    COUNT(*) as total_ops,
    SUM(CASE WHEN tokens_claude = 0 THEN 1 ELSE 0 END) as local_ops,
    ROUND(CAST(SUM(CASE WHEN tokens_claude = 0 THEN 1 ELSE 0 END) AS REAL) / COUNT(*) * 100, 1) as local_rate_pct,
    ROUND(SUM(cost_actual_usd), 4) as total_actual_usd,
    ROUND(SUM(cost_baseline_usd), 4) as total_baseline_usd,
    ROUND(SUM(cost_baseline_usd) - SUM(cost_actual_usd), 4) as total_saved_usd,
    ROUND((SUM(cost_baseline_usd) - SUM(cost_actual_usd)) / NULLIF(SUM(cost_baseline_usd), 0) * 100, 1) as savings_pct
FROM usage_events;