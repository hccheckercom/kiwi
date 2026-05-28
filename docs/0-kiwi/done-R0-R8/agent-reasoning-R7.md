# Phase R7 — Output Versioning + Metrics [3 ngày]

## Mục đích

Đo "Kiwi có thông minh dần không?" bằng số cụ thể.
Nếu curve flat → Kiwi không học → cần debug learning pipeline.

## Dependencies

- **R0 (Session Capture)** — cần session data
- **R3 (Trust Calibration)** — cần calibration events
- **R6 (Graduated Autonomy)** — cần draft outcomes

## Files tạo mới

```
agent/reasoning/
├── metrics.py             # output quality tracking
├── dashboard.py           # generate metrics report (CLI + JSON)
└── alerts.py              # alert khi metrics stagnate
```

---

## Output Quality Table

```sql
CREATE TABLE output_quality (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    week INTEGER NOT NULL,             -- ISO week number
    task_type TEXT NOT NULL,
    
    -- Brief metrics
    brief_version INTEGER DEFAULT 0,   -- lần thứ mấy Kiwi brief cho task type này
    brief_level INTEGER DEFAULT 0,     -- 0-3 (Progressive Intelligence level)
    trust_score FLOAT,
    
    -- Claude behavior metrics (lower = Kiwi smarter)
    tokens_claude_used INTEGER,        -- estimated tokens Claude consumed
    files_re_read INTEGER DEFAULT 0,   -- files Claude đọc lại (brief đã cover)
    edits_after_first INTEGER DEFAULT 0, -- lần Edit cùng file (trial-and-error)
    total_tool_calls INTEGER DEFAULT 0,  -- total tool calls in session
    
    -- Autonomy metrics
    autonomy_level TEXT,               -- "brief_only", "skeleton", "draft", "ready"
    draft_outcome TEXT,                -- "approved", "modified", "rejected", NULL
    
    -- Time metrics
    session_duration_sec FLOAT,        -- thời gian từ first read đến last write
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_oq_week ON output_quality(week);
CREATE INDEX idx_oq_task ON output_quality(task_type);
CREATE INDEX idx_oq_level ON output_quality(brief_level);
```

---

## Metrics Collector

```python
# File: agent/reasoning/metrics.py
"""
Collect output quality metrics sau mỗi session.
Chạy sau learner (R2) + calibrator (R3).
"""

import time
from datetime import datetime
from .session_query import get_session_reads, get_session_writes, get_session_log_entries
from .memory import get_db_conn


def record_output_quality(session_id: str, brief_output: dict = None) -> dict:
    """
    Record quality metrics cho session này.
    Chạy cuối pipeline: R0 → R2 → R3 → R7.
    """
    conn = get_db_conn()
    
    reads = get_session_reads(session_id)
    writes = get_session_writes(session_id)
    entries = get_session_log_entries(session_id)
    
    if not writes:
        return {'status': 'skipped', 'reason': 'no_writes'}
    
    # Compute metrics
    task_type = brief_output.get('task_type', 'generic') if brief_output else 'generic'
    
    # Files re-read (brief đã cover nhưng Claude đọc lại)
    briefed_files = brief_output.get('source_files', []) if brief_output else []
    re_reads = len([r for r in reads if r['file'] in briefed_files])
    
    # Edits after first write (trial-and-error signal)
    file_edit_counts = {}
    for w in writes:
        if w.get('tool') == 'Edit':
            file_edit_counts[w['file']] = file_edit_counts.get(w['file'], 0) + 1
    max_edits = max(file_edit_counts.values()) if file_edit_counts else 0
    
    # Session duration
    if entries:
        timestamps = [e.get('timestamp', 0) for e in entries if e.get('timestamp')]
        duration = max(timestamps) - min(timestamps) if len(timestamps) >= 2 else 0
    else:
        duration = 0
    
    # Estimated tokens (heuristic: ~50 tokens per tool call)
    total_calls = len(entries)
    estimated_tokens = total_calls * 50 + len(reads) * 200 + len(writes) * 500
    
    # Brief version (how many times we've briefed this task type)
    brief_count = conn.execute(
        "SELECT COUNT(*) FROM output_quality WHERE task_type = ?",
        (task_type,)
    ).fetchone()[0]
    
    # Current week
    week = datetime.now().isocalendar()[1]
    
    # Record
    metrics = {
        'session_id': session_id,
        'week': week,
        'task_type': task_type,
        'brief_version': brief_count + 1,
        'brief_level': brief_output.get('level', 0) if brief_output else 0,
        'trust_score': brief_output.get('trust_score', 0) if brief_output else 0,
        'tokens_claude_used': estimated_tokens,
        'files_re_read': re_reads,
        'edits_after_first': max_edits,
        'total_tool_calls': total_calls,
        'autonomy_level': brief_output.get('autonomy_level', 'none') if brief_output else 'none',
        'draft_outcome': None,  # filled later by approval_tracker
        'session_duration_sec': duration,
    }
    
    conn.execute(
        "INSERT INTO output_quality "
        "(session_id, week, task_type, brief_version, brief_level, trust_score, "
        "tokens_claude_used, files_re_read, edits_after_first, total_tool_calls, "
        "autonomy_level, session_duration_sec) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            metrics['session_id'], metrics['week'], metrics['task_type'],
            metrics['brief_version'], metrics['brief_level'], metrics['trust_score'],
            metrics['tokens_claude_used'], metrics['files_re_read'],
            metrics['edits_after_first'], metrics['total_tool_calls'],
            metrics['autonomy_level'], metrics['session_duration_sec'],
        )
    )
    conn.commit()
    
    return metrics
```

---

## Dashboard — Metrics Report

```python
# File: agent/reasoning/dashboard.py
"""
Generate metrics dashboard. CLI output + JSON export.
Answers: "Is Kiwi getting smarter?"
"""

from .memory import get_db_conn
from datetime import datetime


def generate_dashboard(weeks: int = 8) -> dict:
    """
    Generate dashboard showing Kiwi's intelligence trend.
    """
    conn = get_db_conn()
    current_week = datetime.now().isocalendar()[1]
    
    dashboard = {
        'generated_at': datetime.now().isoformat(),
        'period_weeks': weeks,
        'weekly_trends': [],
        'task_type_breakdown': {},
        'autonomy_progression': {},
        'intelligence_score': 0.0,
    }
    
    # Weekly trends
    for w in range(current_week - weeks, current_week + 1):
        row = conn.execute(
            "SELECT "
            "  AVG(tokens_claude_used) as avg_tokens, "
            "  AVG(files_re_read) as avg_re_reads, "
            "  AVG(edits_after_first) as avg_edits, "
            "  AVG(trust_score) as avg_trust, "
            "  AVG(brief_level) as avg_level, "
            "  COUNT(*) as sessions "
            "FROM output_quality WHERE week = ?",
            (w,)
        ).fetchone()
        
        if row and row[5] > 0:  # has data
            dashboard['weekly_trends'].append({
                'week': w,
                'avg_tokens': round(row[0] or 0),
                'avg_re_reads': round(row[1] or 0, 1),
                'avg_edits': round(row[2] or 0, 1),
                'avg_trust': round(row[3] or 0, 3),
                'avg_level': round(row[4] or 0, 1),
                'sessions': row[5],
            })
    
    # Task type breakdown
    task_rows = conn.execute(
        "SELECT task_type, "
        "  AVG(tokens_claude_used) as avg_tokens, "
        "  AVG(trust_score) as avg_trust, "
        "  COUNT(*) as count "
        "FROM output_quality "
        "WHERE week >= ? "
        "GROUP BY task_type ORDER BY count DESC",
        (current_week - weeks,)
    ).fetchall()
    
    for task_type, avg_tokens, avg_trust, count in task_rows:
        dashboard['task_type_breakdown'][task_type] = {
            'avg_tokens': round(avg_tokens or 0),
            'avg_trust': round(avg_trust or 0, 3),
            'sessions': count,
        }
    
    # Autonomy progression
    level_rows = conn.execute(
        "SELECT autonomy_level, COUNT(*) as count "
        "FROM output_quality WHERE week >= ? "
        "GROUP BY autonomy_level",
        (current_week - 4,)  # last 4 weeks
    ).fetchall()
    
    total_sessions = sum(r[1] for r in level_rows) if level_rows else 1
    for level, count in level_rows:
        dashboard['autonomy_progression'][level or 'none'] = {
            'count': count,
            'percentage': round(count / total_sessions * 100, 1),
        }
    
    # Intelligence score (composite: 0-100)
    dashboard['intelligence_score'] = compute_intelligence_score(dashboard)
    
    return dashboard


def compute_intelligence_score(dashboard: dict) -> float:
    """
    Composite score 0-100. Higher = Kiwi smarter.
    Based on: token reduction, trust level, autonomy level, re-read reduction.
    """
    trends = dashboard.get('weekly_trends', [])
    if len(trends) < 2:
        return 0.0
    
    latest = trends[-1]
    first = trends[0]
    
    scores = []
    
    # Token reduction (0-30 points)
    if first['avg_tokens'] > 0:
        token_reduction = 1 - (latest['avg_tokens'] / first['avg_tokens'])
        scores.append(min(max(token_reduction * 100, 0), 30))
    
    # Trust level (0-30 points)
    scores.append(latest['avg_trust'] * 30)
    
    # Brief level (0-20 points)
    scores.append(latest['avg_level'] / 3 * 20)
    
    # Re-read reduction (0-20 points)
    if first['avg_re_reads'] > 0:
        reread_reduction = 1 - (latest['avg_re_reads'] / first['avg_re_reads'])
        scores.append(min(max(reread_reduction * 20, 0), 20))
    else:
        scores.append(20)  # no re-reads = perfect
    
    return round(sum(scores), 1)


def print_dashboard(dashboard: dict):
    """Pretty-print dashboard for CLI."""
    
    print("\n" + "=" * 60)
    print(f"  KIWI INTELLIGENCE DASHBOARD")
    print(f"  Score: {dashboard['intelligence_score']}/100")
    print("=" * 60)
    
    print("\n  Weekly Token Trend (lower = smarter):")
    print("  " + "-" * 50)
    
    for week in dashboard['weekly_trends']:
        bar_len = min(int(week['avg_tokens'] / 500), 40)
        bar = "#" * bar_len
        print(f"  W{week['week']:02d}: {bar} {week['avg_tokens']:,} tok "
              f"(trust:{week['avg_trust']:.2f}, L{week['avg_level']:.0f})")
    
    print("\n  Autonomy Distribution (last 4 weeks):")
    for level, data in dashboard['autonomy_progression'].items():
        print(f"    {level:12s}: {data['percentage']:5.1f}% ({data['count']} sessions)")
    
    print("\n  Task Type Performance:")
    for task, data in list(dashboard['task_type_breakdown'].items())[:5]:
        print(f"    {task:20s}: {data['avg_tokens']:,} tok, "
              f"trust {data['avg_trust']:.2f} ({data['sessions']} sessions)")
    
    print("\n" + "=" * 60)
```

---

## Stagnation Alerts

```python
# File: agent/reasoning/alerts.py
"""
Alert khi Kiwi không cải thiện (metrics flat hoặc worsening).
"""

from .memory import get_db_conn
from datetime import datetime


def check_stagnation() -> dict | None:
    """
    Check if Kiwi is stagnating (not improving).
    Returns alert dict or None if OK.
    """
    conn = get_db_conn()
    current_week = datetime.now().isocalendar()[1]
    
    # Compare last 2 weeks vs 2 weeks before that
    recent = _get_period_metrics(conn, current_week - 1, current_week)
    baseline = _get_period_metrics(conn, current_week - 3, current_week - 2)
    
    if not recent or not baseline:
        return None  # not enough data
    
    # Check: tokens NOT decreasing
    token_improvement = (baseline['avg_tokens'] - recent['avg_tokens']) / max(baseline['avg_tokens'], 1)
    
    # Check: trust NOT increasing
    trust_improvement = recent['avg_trust'] - baseline['avg_trust']
    
    # Check: level NOT increasing
    level_improvement = recent['avg_level'] - baseline['avg_level']
    
    # Stagnation = no improvement on ANY metric
    if token_improvement < 0.05 and trust_improvement < 0.02 and level_improvement < 0.1:
        return {
            'type': 'stagnation',
            'message': (
                f"Kiwi not improving: tokens {token_improvement:+.1%}, "
                f"trust {trust_improvement:+.3f}, level {level_improvement:+.1f}. "
                f"Check learning pipeline."
            ),
            'metrics': {
                'token_improvement': token_improvement,
                'trust_improvement': trust_improvement,
                'level_improvement': level_improvement,
            },
            'suggestions': _suggest_fixes(token_improvement, trust_improvement, level_improvement),
        }
    
    return None


def _get_period_metrics(conn, week_start: int, week_end: int) -> dict | None:
    row = conn.execute(
        "SELECT AVG(tokens_claude_used), AVG(trust_score), AVG(brief_level), COUNT(*) "
        "FROM output_quality WHERE week BETWEEN ? AND ?",
        (week_start, week_end)
    ).fetchone()
    
    if not row or row[3] < 3:  # need at least 3 sessions
        return None
    
    return {
        'avg_tokens': row[0] or 0,
        'avg_trust': row[1] or 0,
        'avg_level': row[2] or 0,
        'sessions': row[3],
    }


def _suggest_fixes(token_imp: float, trust_imp: float, level_imp: float) -> list:
    suggestions = []
    
    if token_imp < 0:  # tokens INCREASING (worse)
        suggestions.append("Tokens increasing — check if briefs are causing confusion (Claude re-reading more)")
    
    if trust_imp < 0:  # trust DECREASING
        suggestions.append("Trust decreasing — run smart_forget() to clear stale knowledge")
    
    if level_imp == 0 and trust_imp >= 0:
        suggestions.append("Level stuck but trust OK — may need more data for level-up threshold")
    
    if not suggestions:
        suggestions.append("All metrics flat — check if learning pipeline is running (sessions being processed?)")
    
    return suggestions
```

---

## MCP Tool: kiwi_metrics

```python
# Trong mcp_server.py — thêm tool

@tool("kiwi_metrics")
def handle_kiwi_metrics(weeks: int = 8, format: str = "summary") -> dict:
    """
    Get Kiwi intelligence metrics.
    format: "summary" (key numbers), "full" (complete dashboard), "alert" (only if issues)
    """
    from agent.reasoning.dashboard import generate_dashboard
    from agent.reasoning.alerts import check_stagnation
    
    if format == "alert":
        alert = check_stagnation()
        return alert or {'status': 'ok', 'message': 'Kiwi is improving normally'}
    
    dashboard = generate_dashboard(weeks)
    
    if format == "summary":
        return {
            'intelligence_score': dashboard['intelligence_score'],
            'latest_week': dashboard['weekly_trends'][-1] if dashboard['weekly_trends'] else None,
            'autonomy': dashboard['autonomy_progression'],
            'stagnation': check_stagnation(),
        }
    
    return dashboard  # full
```

---

## CLI Command

```powershell
# Chạy dashboard từ terminal
$env:PYTHONUTF8=1; cd .claude/kiwi; python -m agent.reasoning.dashboard

# Output:
# ============================================================
#   KIWI INTELLIGENCE DASHBOARD
#   Score: 42/100
# ============================================================
#
#   Weekly Token Trend (lower = smarter):
#   --------------------------------------------------
#   W20: ################################## 17000 tok (trust:0.40, L0)
#   W21: ########################## 13000 tok (trust:0.55, L1)
#   W22: #################### 10000 tok (trust:0.62, L1)
#   W23: ################ 8000 tok (trust:0.70, L2)
#   W24: ############ 6000 tok (trust:0.75, L2)
#
#   Autonomy Distribution (last 4 weeks):
#     brief_only  :  40.0% (8 sessions)
#     skeleton    :  35.0% (7 sessions)
#     draft       :  20.0% (4 sessions)
#     ready       :   5.0% (1 sessions)
# ============================================================
```

---

## Integration: Full Post-Session Pipeline

```python
def full_post_session_pipeline(session_id: str, brief_output: dict = None):
    """
    Complete pipeline chạy sau mỗi session.
    R0 (capture) → R2 (learn) → R3 (calibrate) → R4 (active learn) → R7 (metrics)
    """
    from .learner import learn_from_session
    from .calibrator import calibrate_trust_from_session
    from .metrics import record_output_quality
    from .alerts import check_stagnation
    
    # Step 1: Learn patterns (R2)
    learn_result = learn_from_session(session_id)
    
    # Step 2: Calibrate trust (R3)
    calibrate_result = None
    if brief_output:
        calibrate_result = calibrate_trust_from_session(session_id, brief_output)
    
    # Step 3: Record metrics (R7)
    metrics = record_output_quality(session_id, brief_output)
    
    # Step 4: Check stagnation (R7)
    alert = check_stagnation()
    
    return {
        'learn': learn_result,
        'calibrate': calibrate_result,
        'metrics': metrics,
        'alert': alert,
    }
```

---

## Verification

```python
# Test: metrics recording
from .metrics import record_output_quality

metrics = record_output_quality(
    session_id='test-001',
    brief_output={
        'task_type': 'checkout_page',
        'trust_score': 0.75,
        'level': 2,
        'source_files': ['cart.php', 'spec.md'],
        'autonomy_level': 'skeleton',
    }
)
assert metrics['task_type'] == 'checkout_page'
assert metrics['trust_score'] == 0.75
assert metrics['brief_level'] == 2

# Test: dashboard generation
from .dashboard import generate_dashboard, compute_intelligence_score
dashboard = generate_dashboard(weeks=4)
assert 'weekly_trends' in dashboard
assert 'intelligence_score' in dashboard
assert 0 <= dashboard['intelligence_score'] <= 100

# Test: stagnation detection
from .alerts import check_stagnation
# (after inserting flat metrics for 4 weeks)
alert = check_stagnation()
# Should detect stagnation if metrics are flat
```

---

## Key Insight: Intelligence Score

**Intelligence Score (0-100)** là single number trả lời "Kiwi có thông minh dần không?"

| Score | Meaning |
|-------|---------|
| 0-20 | Kiwi mới, chưa học gì |
| 20-40 | Đang học, brief bắt đầu hữu ích |
| 40-60 | Brief tốt, Claude bắt đầu tin |
| 60-80 | Graduated autonomy working, token savings rõ |
| 80-100 | Near-autonomous cho common tasks |

**Target:** Score tăng ~5-10 points/tuần trong 2 tháng đầu, sau đó plateau ở 70-85.
Nếu score flat > 2 tuần → stagnation alert fires.

---

## AUDIT FINDINGS (2026-05-28)

### A1. Schema Mismatch — `output_quality` table đã tồn tại nhưng thiếu cột

**Hiện trạng** (`schema.sql:62-74`):
```sql
CREATE TABLE IF NOT EXISTS output_quality (
    id, session_id, week, task_type, brief_version, trust_score,
    tokens_estimated, files_re_read, edits_after_first, total_tool_calls, created_at
);
```

**R7 spec yêu cầu thêm:** `brief_level`, `autonomy_level`, `draft_outcome`, `session_duration_sec`
**R7 spec đổi tên:** `tokens_estimated` → `tokens_claude_used`

**Suggestion:** Giữ `tokens_estimated` (đã có data). Thêm 4 cột mới qua migration trong `session_logger._migrate()`. KHÔNG đổi tên cột.

---

### A2. Import sai module — `session_query` không tồn tại

Spec import:
```python
from .session_query import get_session_reads, get_session_writes, get_session_log_entries
from .memory import get_db_conn
```

**Thực tế:** Tất cả nằm trong `session_logger.py`:
- `get_session_reads()` → `session_logger.py:226`
- `get_session_writes()` → `session_logger.py:237`
- `get_session_log_entries()` → `session_logger.py:332`
- `_get_conn()` → `session_logger.py:18` (không phải `get_db_conn`)

**Fix:** Đổi import thành:
```python
from .session_logger import _get_conn, get_session_reads, get_session_writes, get_session_log_entries
```

---

### A3. `brief_output` dict không khớp `KiwiOutput` dataclass

Spec giả định `brief_output` có keys: `task_type`, `trust_score`, `level`, `source_files`, `autonomy_level`.

**Thực tế** (`output.py`): `KiwiOutput` có:
- `content.get('target')` → task_type ✓
- `trust_score` → ✓
- **KHÔNG CÓ** `level` (brief_level)
- **KHÔNG CÓ** `source_files` (chỉ có `content['files_needed']`)
- **KHÔNG CÓ** `autonomy_level` (chỉ có `graduated.level` nếu R6 chạy)

**Fix:** `record_output_quality()` phải nhận `KiwiOutput` trực tiếp, extract:
```python
task_type = brief.content.get('target', 'generic')
source_files = brief.content.get('files_needed', [])
autonomy_level = brief.graduated.level if brief.graduated else 'none'
brief_level = {'brief_only': 0, 'skeleton': 1, 'draft': 2, 'ready': 3}.get(autonomy_level, 0)
```

---

### A4. Duplicate pipeline — `_auto_learn_recent` vs `full_post_session_pipeline`

`__init__.py:67` đã có `_auto_learn_recent()` chạy learn + calibrate mỗi lần `kiwi_reason()` được gọi.

Spec thêm `full_post_session_pipeline()` làm gần y hệt.

**Suggestion:** KHÔNG tạo `full_post_session_pipeline()` riêng. Thay vào đó, thêm `record_output_quality()` vào cuối `_auto_learn_recent()` — sau learn + calibrate, ghi metrics. Giữ 1 pipeline duy nhất.

---

### A5. Dashboard week calculation — lỗi qua năm mới

```python
current_week = datetime.now().isocalendar()[1]
for w in range(current_week - weeks, current_week + 1):
```

Nếu current_week = 3 (đầu tháng 1), `range(3-8, 4)` = `range(-5, 4)` → query week -5 đến -1 → 0 results.

**Fix:** Dùng `(year, week)` tuple hoặc epoch-week (`int(timestamp / 604800)`). Epoch-week đơn giản hơn, không bị reset:
```python
week = int(time.time() / 604800)  # weeks since epoch
```

---

### A6. Intelligence score — `avg_level` là string, không phải int

DB lưu `autonomy_level` là TEXT (`"brief_only"`, `"skeleton"`, `"draft"`, `"ready"`).
Spec dùng `AVG(brief_level)` nhưng cột này chưa tồn tại.

**Fix:** Thêm cột `brief_level INTEGER` (0-3) vào `output_quality`. Compute khi insert:
```python
LEVEL_MAP = {'none': 0, 'brief_only': 0, 'skeleton': 1, 'draft': 2, 'ready': 3}
brief_level = LEVEL_MAP.get(autonomy_level, 0)
```

---

### A7. Division by zero trong `compute_intelligence_score`

```python
if first['avg_tokens'] > 0:
    token_reduction = 1 - (latest['avg_tokens'] / first['avg_tokens'])
```

Nếu `first['avg_tokens']` = 0 (tuần đầu không có session) → skip. Nhưng nếu `first['avg_re_reads']` = 0 → else branch cho 20 points miễn phí. Inconsistent.

**Fix:** Cả 2 nên dùng cùng logic: nếu baseline = 0, cho max points (không có gì để cải thiện).

---

### A8. MCP tool registration pattern sai

Spec dùng `@tool("kiwi_metrics")` decorator. Thực tế `mcp_server.py` dùng dict dispatch:
```python
TOOLS = {"kiwi_scan": handle_scan, "kiwi_check": handle_check, ...}
```

**Fix:** Đăng ký theo pattern hiện tại — thêm entry vào `TOOLS` dict + handler function.

---

### A9. Thiếu test file

R0-R6 đều có test riêng (`test_integration_r0_r3.py`, `test_calibrator.py`, `test_r4.py`, `test_r5.py`, `test_r6.py`, `test_r6_qa.py`).

R7 chỉ có inline snippets, không có `test_r7.py`.

**Suggestion:** Tạo `test_r7.py` với:
- `TestMetricsRecording`: insert + verify output_quality rows
- `TestDashboard`: generate with mock data, verify score bounds
- `TestStagnation`: flat data → alert fires; improving data → None
- `TestWeekBoundary`: epoch-week không bị reset qua năm
- `TestIntegrationWithAutoLearn`: verify metrics ghi sau learn cycle

---

### A10. Stagnation detection — false positive risk

So sánh 2 tuần vs 2 tuần trước, min 3 sessions. Với volume thấp (1-2 sessions/ngày), 3 sessions trong 2 tuần là quá ít để kết luận stagnation.

**Suggestion:** Tăng `min_sessions` lên 5. Thêm `confidence` field vào alert:
```python
confidence = min(sessions / 10, 1.0)  # 10 sessions = full confidence
```
Chỉ fire alert khi confidence >= 0.5.

---

## IMPLEMENTATION PLAN (Đã audit, sẵn sàng code)

### Priority order:

| # | Task | Effort | Depends |
|---|------|--------|---------|
| 1 | Migration: thêm 4 cột vào `output_quality` | 15 min | — |
| 2 | `metrics.py`: collector (fix imports, fix brief_output interface) | 30 min | #1 |
| 3 | `dashboard.py`: epoch-week, fix score formula | 30 min | #2 |
| 4 | `alerts.py`: stagnation + confidence | 20 min | #2 |
| 5 | Hook vào `_auto_learn_recent()` (không tạo pipeline mới) | 10 min | #2 |
| 6 | MCP tool `kiwi_metrics` (dict registration) | 10 min | #3, #4 |
| 7 | `test_r7.py`: 15+ tests | 40 min | #2-#4 |
| 8 | CLI `__main__` trong dashboard.py | 10 min | #3 |

**Total:** ~2.5 giờ (vs spec estimate 3 ngày — spec overestimated vì đã có foundation)

### Schema migration (exact SQL):

```sql
-- Thêm vào session_logger._migrate()
ALTER TABLE output_quality ADD COLUMN brief_level INTEGER DEFAULT 0;
ALTER TABLE output_quality ADD COLUMN autonomy_level TEXT DEFAULT 'none';
ALTER TABLE output_quality ADD COLUMN draft_outcome TEXT;
ALTER TABLE output_quality ADD COLUMN session_duration_sec REAL DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_oq_task ON output_quality(task_type);
CREATE INDEX IF NOT EXISTS idx_oq_level ON output_quality(brief_level);
```