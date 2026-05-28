# A4 — Usage Tracking + Savings Dashboard (3 days)

## Mục tiêu

Track mọi Kiwi operation (MCP tool calls, scans, fixes), estimate "cost nếu không có Kiwi" (baseline), hiện savings real-time qua CLI + MCP tool.

## Audit Notes (từ A4 plan review)

**Existing infrastructure to reuse:**
- `agent/cost.py`: `CostTracker`, `PRICING` dict, `TokenUsage`, `CostSummary` — đã có pricing model
- `agent/reasoning/session_logger.py`: SQLite session logging → `memory/reasoning.db`
- `agent/reasoning/metrics.py`: `record_output_quality()` — token estimation per session
- `memory/kiwi.db`: existing DB for scan history, false positives

**Issues with original plan:**
1. Title said "A3" — fixed to A4
2. Output path `core/` wrong — core/ is language-agnostic engine only
3. Schema too simplistic — 'local'|'claude' misses operation granularity
4. Missing session_id link to reasoning.db
5. Baseline estimator had no concrete formulas
6. No MCP tool exposure for Claude Code users
7. No integration hooks showing how tools emit events
8. Duplicates `agent/cost.py` pricing logic

---

## Tasks

1. **SQLite schema** in `memory/kiwi.db` (new table, reuse existing DB)
2. **UsageTracker class** — singleton, records every MCP tool invocation
3. **Integration hooks** — instrument `mcp_server.py` tool handlers to emit events
4. **Baseline estimator** — concrete formulas per operation type
5. **Savings calculator** — actual vs baseline, cumulative + per-day
6. **MCP tool `kiwi_dashboard`** — formatted savings for Claude Code users
7. **CLI command `kiwi dashboard`** — terminal-friendly output
8. **Tests** — 30+ assertions covering tracking, estimation, calculation

## Output

```
tracking/
├── __init__.py
├── usage_tracker.py      # singleton tracker, records operations
├── baseline_estimator.py # "without Kiwi" cost formulas
├── savings.py            # calculator: actual vs baseline
└── dashboard.py          # CLI + MCP formatted output
```

Integration points (modified files):
- `mcp_server.py` — add `tracker.record()` calls in each tool handler
- `mcp_server.py` — add `kiwi_dashboard` tool definition
- `agent/cost.py` — import PRICING from there (single source of truth)

---

## Schema

```sql
-- New table in memory/kiwi.db
CREATE TABLE IF NOT EXISTS usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,              -- time.time()
    session_id TEXT,                      -- link to reasoning.db sessions
    operation TEXT NOT NULL,              -- 'context'|'check'|'scan'|'fix'|'query'|'lesson'|'template'|'agent'|'deploy'
    sub_operation TEXT,                   -- e.g. 'scan_critical'|'scan_all'|'fix_preview'|'fix_apply'
    target_path TEXT,                     -- file or project path
    
    -- Actual cost (what Kiwi used)
    tokens_local INTEGER DEFAULT 0,      -- tokens processed locally (0 cost)
    tokens_claude INTEGER DEFAULT 0,     -- tokens sent to Claude API (if escalated)
    cost_actual_usd REAL DEFAULT 0.0,    -- actual $ spent (usually 0 for local ops)
    latency_ms INTEGER DEFAULT 0,        -- wall clock time
    
    -- Baseline estimate (what it WOULD cost without Kiwi)
    tokens_baseline INTEGER NOT NULL,    -- estimated tokens if user asked Claude directly
    cost_baseline_usd REAL NOT NULL,     -- estimated $ without Kiwi
    latency_baseline_ms INTEGER,         -- estimated time without Kiwi
    
    -- Result metadata
    violations_found INTEGER DEFAULT 0,
    files_processed INTEGER DEFAULT 0,
    success INTEGER DEFAULT 1            -- 1=ok, 0=error
);

CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_usage_operation ON usage_events(operation);

-- Aggregation view
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

-- Cumulative view
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
```

---

## Baseline Estimation Formulas

Conservative estimates (under-promise, over-deliver):

| Operation | Without Kiwi (baseline) | Formula |
|-----------|------------------------|---------|
| `kiwi_context` | User reads 5-10 files manually, Claude processes context | `files_count × 200 tokens/file + 500 output` |
| `kiwi_check` (1 file) | Claude reads file + reasons about patterns | `file_lines × 4 tokens/line + 800 reasoning` |
| `kiwi_scan` (project) | Claude reads all files + full analysis | `files_scanned × 150 tokens/file + 2000 summary` |
| `kiwi_fix` (preview) | Claude reads file + proposes fix | `file_lines × 4 + 1500 reasoning + 500 output` |
| `kiwi_fix` (apply) | Same as preview + verification | `baseline_preview × 1.5` |
| `kiwi_query` | Claude searches codebase + answers | `3000 context + 500 output` |
| `kiwi_lesson` | Claude reads docs + explains | `1500 context + 300 output` |
| `kiwi_template` | Claude searches templates + formats | `2000 context + 800 output` |
| `kiwi_agent` (per iteration) | Full Claude conversation turn | `5000 context + 2000 output` |
| `kiwi_deploy` | Claude reads configs + executes | `3000 context + 1000 output` |

**Cost formula:** `tokens_baseline × $3.00/1M (input) + output_tokens × $15.00/1M (output)`
(Uses Sonnet pricing as baseline — most users would use Sonnet for these tasks)

**Latency formula:** `tokens_baseline / 100 × 1000ms` (conservative: 100 tok/s)

---

## Integration Design

```python
# In mcp_server.py — each tool handler wraps with:
from tracking import usage_tracker

async def handle_kiwi_check(params):
    start = time.time()
    result = _do_check(params)  # existing logic
    
    usage_tracker.record(
        operation="check",
        target_path=params.get("file"),
        tokens_local=0,  # all local
        files_processed=1,
        violations_found=len(result.get("violations", [])),
        latency_ms=int((time.time() - start) * 1000),
    )
    return result
```

Tracker auto-computes baseline from operation type + files_processed.

---

## MCP Tool: `kiwi_dashboard`

```json
{
    "name": "kiwi_dashboard",
    "description": "View usage stats and cost savings. Shows how much Kiwi saved vs direct Claude usage.",
    "parameters": {
        "period": { "enum": ["today", "week", "month", "all"], "default": "week" },
        "detail": { "type": "boolean", "default": false }
    }
}
```

**Output format (compact):**
```
Kiwi Savings (this week)
━━━━━━━━━━━━━━━━━━━━━━━
Operations: 47 (93.6% local)
Saved: $2.14 / $2.29 baseline (93.4% savings)
Local tokens: 0 | Baseline tokens: 152,300

Top operations:
  scan: 12 ops, saved $0.89
  context: 18 ops, saved $0.72
  check: 11 ops, saved $0.38
```

**Output format (detail=true):** adds per-day breakdown + per-operation table.

---

## CLI Command

```bash
# Quick summary
python -m tracking.dashboard

# Detailed
python -m tracking.dashboard --period month --detail

# JSON output (for integrations)
python -m tracking.dashboard --json
```

---

## Dependencies

- A1 (core structure) — ✅ done
- `agent/cost.py` — reuse PRICING dict (import, don't duplicate)
- `memory/kiwi.db` — existing DB, add new table

## Done khi

- [ ] Mỗi MCP tool call → ghi vào `usage_events` (verified by test)
- [ ] `kiwi_dashboard` MCP tool returns formatted savings
- [ ] `python -m tracking.dashboard` works standalone
- [ ] Baseline estimation conservative (formula-based, no LLM)
- [ ] 30+ test assertions pass
- [ ] Zero regression on existing 45 A3 tests
- [ ] Savings formula transparent: user can see "47 ops × avg 3200 tokens = $X baseline"