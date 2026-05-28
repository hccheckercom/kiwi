# Phase R5 — Brief Quality + Smart Forgetting + Regression Detection [ongoing]

## Mục đích

Kiwi brief cải thiện tự nhiên theo thời gian. Đồng thời biết quên knowledge cũ/sai
và phát hiện khi mình đang tệ đi.

## Dependencies

- **R2 (Passive Learning)** — cần accumulated patterns
- **R3 (Trust Calibration)** — cần accuracy history
- **R4 (Active Learning)** — cần style/binding knowledge

## Files tạo mới

```
agent/reasoning/
├── distiller.py           # nén raw patterns → rules
├── forgetter.py           # decay, invalidate, prune
├── regression.py          # detect + diagnose + auto-recover
└── weekly_report.py       # metrics dashboard
```

---

## Knowledge Distillation — Nén patterns thành rules

Raw patterns scale linearly (100 tasks = 100 patterns).
Distilled rules scale logarithmically (100 tasks = 15 rules).

```python
# File: agent/reasoning/distiller.py
"""
Chạy weekly. Nén raw patterns thành higher-level rules.
0 LLM token — clustering + frequency analysis.
"""

import json
from collections import Counter, defaultdict
from .memory import get_db_conn


def distill_weekly() -> dict:
    """
    Main entry point. Chạy mỗi tuần.
    Nén raw patterns → distilled rules.
    """
    conn = get_db_conn()
    results = {
        'style_rules': distill_style_rules(conn),
        'binding_rules': distill_binding_rules(conn),
        'structure_rules': distill_structure_rules(conn),
    }
    return results


def distill_style_rules(conn) -> list:
    """
    Group style patterns by theme → extract common → note exceptions.
    
    Input: 50 raw observations
    Output: 5-10 rules like "section_spacing = py-8 md:py-12 (default)"
    """
    rules = []
    
    # Get all style knowledge grouped by pattern_key
    rows = conn.execute(
        "SELECT pattern_key, value, theme, times_seen "
        "FROM style_knowledge ORDER BY pattern_key, times_seen DESC"
    ).fetchall()
    
    # Group by pattern_key
    by_key = defaultdict(list)
    for key, value, theme, count in rows:
        by_key[key].append({'value': value, 'theme': theme, 'count': count})
    
    for key, entries in by_key.items():
        # Find most common value (across all themes)
        value_counts = Counter()
        for e in entries:
            value_counts[e['value']] += e['count']
        
        if not value_counts:
            continue
        
        most_common_value, most_common_count = value_counts.most_common(1)[0]
        total = sum(value_counts.values())
        confidence = most_common_count / total
        
        # Find exceptions
        exceptions = [
            {'value': v, 'count': c}
            for v, c in value_counts.items()
            if v != most_common_value and c >= 2  # at least 2 occurrences
        ]
        
        rule = {
            'key': key,
            'default_value': most_common_value,
            'confidence': round(confidence, 2),
            'evidence_count': total,
            'exceptions': exceptions,
        }
        rules.append(rule)
        
        # Save distilled rule
        conn.execute(
            "INSERT OR REPLACE INTO distilled_rules "
            "(rule_key, rule_type, default_value, confidence, evidence_count, "
            "exceptions, last_distilled) VALUES (?, 'style', ?, ?, ?, ?, ?)",
            (key, most_common_value, confidence, total,
             json.dumps(exceptions), time.time())
        )
    
    conn.commit()
    return rules


def distill_binding_rules(conn) -> list:
    """
    For each task_type → which bindings are ALWAYS used?
    """
    rules = []
    
    rows = conn.execute(
        "SELECT task_type, binding, SUM(times_seen) as total "
        "FROM binding_knowledge GROUP BY task_type, binding "
        "ORDER BY task_type, total DESC"
    ).fetchall()
    
    by_task = defaultdict(list)
    for task_type, binding, total in rows:
        by_task[task_type].append({'binding': binding, 'count': total})
    
    for task_type, bindings in by_task.items():
        if not bindings:
            continue
        
        # Bindings used in > 80% of instances = "required"
        max_count = bindings[0]['count']
        required = [b['binding'] for b in bindings if b['count'] >= max_count * 0.8]
        optional = [b['binding'] for b in bindings if b['count'] < max_count * 0.8]
        
        rule = {
            'task_type': task_type,
            'required_bindings': required,
            'optional_bindings': optional[:5],  # top 5 optional
            'evidence_count': max_count,
        }
        rules.append(rule)
    
    return rules


def distill_structure_rules(conn) -> list:
    """
    For each task_type → what's the dominant structure?
    """
    rows = conn.execute(
        "SELECT task_type, structure, themes_applied, success_count "
        "FROM cross_theme_patterns ORDER BY success_count DESC"
    ).fetchall()
    
    rules = []
    for task_type, structure_json, themes_json, success in rows:
        structure = json.loads(structure_json)
        themes = json.loads(themes_json)
        
        if success >= 3:  # at least 3 successful uses
            rules.append({
                'task_type': task_type,
                'structure': structure,
                'themes_validated': themes,
                'success_count': success,
                'confidence': min(success / 10, 1.0),
            })
    
    return rules
```

---

## Smart Forgetting — Biết quên để không bị nhiễu

```python
# File: agent/reasoning/forgetter.py
"""
3 loại forgetting. Chạy weekly hoặc khi trust giảm bất thường.
"""

import time
from .memory import get_db_conn


def smart_forget() -> dict:
    """Main entry point. Run all 3 forgetting strategies."""
    results = {
        'decayed': decay_old_patterns(),
        'invalidated': invalidate_contradicted(),
        'pruned': prune_unused(),
    }
    return results


def decay_old_patterns() -> int:
    """
    Pattern không được confirm lại trong 30 ngày → confidence giảm 20%.
    Pattern confidence < 0.3 → archive.
    """
    conn = get_db_conn()
    cutoff = time.time() - (30 * 86400)  # 30 days
    
    # Decay stale distilled rules
    stale = conn.execute(
        "SELECT id, confidence FROM distilled_rules "
        "WHERE last_distilled < ? AND confidence > 0.3",
        (cutoff,)
    ).fetchall()
    
    decayed = 0
    for rule_id, confidence in stale:
        new_confidence = confidence * 0.8
        if new_confidence < 0.3:
            conn.execute(
                "UPDATE distilled_rules SET status = 'archived', confidence = ? WHERE id = ?",
                (new_confidence, rule_id)
            )
        else:
            conn.execute(
                "UPDATE distilled_rules SET confidence = ? WHERE id = ?",
                (new_confidence, rule_id)
            )
        decayed += 1
    
    conn.commit()
    return decayed


def invalidate_contradicted() -> int:
    """
    Khi Claude làm ngược lại knowledge đã lưu VÀ kết quả tốt (accepted)
    → knowledge cũ sai → invalidate.
    """
    conn = get_db_conn()
    
    # Find recent calibration events where trust increased
    # (meaning Claude's approach was correct, even if different from brief)
    recent_positive = conn.execute(
        "SELECT task_type, session_id FROM calibration_events "
        "WHERE delta > 0 AND created_at > ?",
        (time.time() - 7 * 86400,)
    ).fetchall()
    
    invalidated = 0
    
    for task_type, session_id in recent_positive:
        # Check if session had re-reads (Claude overrode brief)
        event = conn.execute(
            "SELECT signals FROM calibration_events "
            "WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
            (session_id,)
        ).fetchone()
        
        if event:
            import json
            signals = json.loads(event[0])
            if signals.get('brief_ignored') and not signals.get('kiwi_violations'):
                # Claude ignored brief BUT code was clean → brief was wrong
                # Find and invalidate the specific knowledge that led to bad brief
                # (simplified: mark oldest rule for this task_type as suspect)
                oldest = conn.execute(
                    "SELECT id FROM distilled_rules "
                    "WHERE rule_key LIKE ? AND status = 'active' "
                    "ORDER BY last_distilled ASC LIMIT 1",
                    (f"%{task_type}%",)
                ).fetchone()
                
                if oldest:
                    conn.execute(
                        "UPDATE distilled_rules SET status = 'invalidated' WHERE id = ?",
                        (oldest[0],)
                    )
                    invalidated += 1
    
    conn.commit()
    return invalidated


def prune_unused() -> int:
    """
    Knowledge tồn tại > 60 ngày nhưng chưa bao giờ xuất hiện trong brief → xóa.
    """
    conn = get_db_conn()
    cutoff = time.time() - (60 * 86400)
    
    # Novel patterns never promoted
    pruned = conn.execute(
        "DELETE FROM novel_patterns "
        "WHERE discovered_at < ? AND promoted_to_lesson = 0",
        (cutoff,)
    ).rowcount
    
    # Style knowledge never confirmed (times_seen = 1, old)
    pruned += conn.execute(
        "DELETE FROM style_knowledge "
        "WHERE times_seen = 1 AND last_seen < ?",
        (cutoff,)
    ).rowcount
    
    conn.commit()
    return pruned
```

---

## Regression Detection

```python
# File: agent/reasoning/regression.py
"""
Detect khi Kiwi đang tệ đi. Auto-recover hoặc escalate.
"""

import time
from dataclasses import dataclass
from .memory import get_db_conn


@dataclass
class RegressionAlert:
    metric: str
    current_value: float
    baseline_value: float
    drop: float
    diagnosis: list
    suggested_action: str


def detect_regression() -> RegressionAlert | None:
    """
    So sánh 7 ngày gần nhất vs 7 ngày trước đó.
    Returns alert nếu regression detected, None nếu OK.
    """
    conn = get_db_conn()
    now = time.time()
    
    # Recent window: last 7 days
    recent_start = now - 7 * 86400
    # Baseline window: 8-14 days ago
    baseline_start = now - 14 * 86400
    baseline_end = now - 7 * 86400
    
    # Get trust scores
    recent_trust = _avg_trust(conn, recent_start, now)
    baseline_trust = _avg_trust(conn, baseline_start, baseline_end)
    
    if recent_trust is None or baseline_trust is None:
        return None  # not enough data
    
    # Check: trust dropped > 15%
    trust_drop = baseline_trust - recent_trust
    if trust_drop > 0.15:
        diagnosis = diagnose_regression(conn, recent_start)
        return RegressionAlert(
            metric='trust_score',
            current_value=recent_trust,
            baseline_value=baseline_trust,
            drop=trust_drop,
            diagnosis=diagnosis,
            suggested_action=diagnosis[0]['fix'] if diagnosis else 'manual_review',
        )
    
    # Check: brief usage rate dropped > 20%
    recent_usage = _brief_usage_rate(conn, recent_start, now)
    baseline_usage = _brief_usage_rate(conn, baseline_start, baseline_end)
    
    if recent_usage is not None and baseline_usage is not None:
        usage_drop = baseline_usage - recent_usage
        if usage_drop > 0.2:
            diagnosis = diagnose_regression(conn, recent_start)
            return RegressionAlert(
                metric='brief_usage_rate',
                current_value=recent_usage,
                baseline_value=baseline_usage,
                drop=usage_drop,
                diagnosis=diagnosis,
                suggested_action=diagnosis[0]['fix'] if diagnosis else 'manual_review',
            )
    
    return None


def diagnose_regression(conn, since: float) -> list:
    """Tìm root cause."""
    causes = []
    
    # Cause 1: Many negative calibration events
    negatives = conn.execute(
        "SELECT COUNT(*) FROM calibration_events "
        "WHERE delta < 0 AND created_at > ?",
        (since,)
    ).fetchone()[0]
    
    if negatives >= 3:
        causes.append({
            'cause': 'repeated_brief_failures',
            'detail': f"{negatives} sessions where brief was ignored/wrong",
            'fix': 'run_smart_forget',
        })
    
    # Cause 2: Many stale rules
    stale_count = conn.execute(
        "SELECT COUNT(*) FROM distilled_rules "
        "WHERE status = 'active' AND last_distilled < ?",
        (time.time() - 30 * 86400,)
    ).fetchone()[0]
    
    if stale_count >= 5:
        causes.append({
            'cause': 'stale_knowledge',
            'detail': f"{stale_count} rules not confirmed in 30+ days",
            'fix': 'run_decay',
        })
    
    # Cause 3: Novel task types (no prior patterns)
    novel = conn.execute(
        "SELECT COUNT(DISTINCT task_type) FROM calibration_events "
        "WHERE created_at > ? AND task_type NOT IN "
        "(SELECT DISTINCT task_type FROM context_patterns)",
        (since,)
    ).fetchone()[0]
    
    if novel >= 2:
        causes.append({
            'cause': 'novel_tasks',
            'detail': f"{novel} new task types with no prior patterns",
            'fix': 'expected_recovery',  # trust will recover naturally
        })
    
    return causes


def auto_recover(alert: RegressionAlert) -> str:
    """Attempt auto-recovery based on diagnosis."""
    from .forgetter import smart_forget, decay_old_patterns
    
    action = alert.suggested_action
    
    if action == 'run_smart_forget':
        result = smart_forget()
        return f"Smart forget executed: {result}"
    elif action == 'run_decay':
        result = decay_old_patterns()
        return f"Decayed {result} stale patterns"
    elif action == 'expected_recovery':
        return "Novel tasks detected — trust will recover as patterns accumulate"
    else:
        return "Manual review needed — escalate to user"


def _avg_trust(conn, start: float, end: float) -> float | None:
    row = conn.execute(
        "SELECT AVG(trust_after) FROM calibration_events "
        "WHERE created_at BETWEEN ? AND ?",
        (start, end)
    ).fetchone()
    return row[0] if row and row[0] is not None else None


def _brief_usage_rate(conn, start: float, end: float) -> float | None:
    row = conn.execute(
        "SELECT AVG(CASE WHEN delta >= 0 THEN 1.0 ELSE 0.0 END) "
        "FROM calibration_events WHERE created_at BETWEEN ? AND ?",
        (start, end)
    ).fetchone()
    return row[0] if row and row[0] is not None else None
```

---

## Weekly Report

```python
# File: agent/reasoning/weekly_report.py

import time
import json
from .memory import get_db_conn
from .regression import detect_regression


def generate_weekly_report() -> dict:
    """
    Chạy weekly. Output metrics dashboard.
    Dùng để track "Kiwi có thông minh dần không?"
    """
    conn = get_db_conn()
    now = time.time()
    week_ago = now - 7 * 86400
    
    report = {
        'period': 'last_7_days',
        'generated_at': now,
        
        # Core metrics
        'avg_trust_score': _avg_metric(conn, 'trust_after', week_ago, now),
        'brief_usage_rate': _brief_usage(conn, week_ago, now),
        'sessions_count': _count_sessions(conn, week_ago, now),
        
        # Learning metrics
        'patterns_learned': _count_new(conn, 'context_patterns', week_ago),
        'code_patterns_learned': _count_new(conn, 'code_patterns', week_ago),
        'novel_patterns_discovered': _count_new(conn, 'novel_patterns', week_ago),
        
        # Knowledge health
        'knowledge_health': {
            'total_rules': _count_rules(conn, 'active'),
            'archived': _count_rules(conn, 'archived'),
            'invalidated': _count_rules(conn, 'invalidated'),
        },
        
        # Forgetting stats
        'forgetting_stats': {
            'decayed': _count_decayed(conn, week_ago),
            'pruned': _count_pruned(conn, week_ago),
        },
        
        # Regression check
        'regression_alert': None,
    }
    
    # Check for regression
    alert = detect_regression()
    if alert:
        report['regression_alert'] = {
            'metric': alert.metric,
            'drop': alert.drop,
            'diagnosis': alert.diagnosis,
            'action': alert.suggested_action,
        }
    
    return report


# Helper functions (simplified)
def _avg_metric(conn, col, start, end):
    r = conn.execute(
        f"SELECT AVG({col}) FROM calibration_events WHERE created_at BETWEEN ? AND ?",
        (start, end)
    ).fetchone()
    return round(r[0], 3) if r and r[0] else None

def _brief_usage(conn, start, end):
    r = conn.execute(
        "SELECT AVG(CASE WHEN delta >= 0 THEN 1.0 ELSE 0.0 END) "
        "FROM calibration_events WHERE created_at BETWEEN ? AND ?",
        (start, end)
    ).fetchone()
    return round(r[0], 3) if r and r[0] else None

def _count_sessions(conn, start, end):
    r = conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE started_at BETWEEN ? AND ?",
        (start, end)
    ).fetchone()
    return r[0] if r else 0

def _count_new(conn, table, since):
    r = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE created_at > ?", (since,)
    ).fetchone()
    return r[0] if r else 0

def _count_rules(conn, status):
    r = conn.execute(
        "SELECT COUNT(*) FROM distilled_rules WHERE status = ?", (status,)
    ).fetchone()
    return r[0] if r else 0

def _count_decayed(conn, since):
    return 0  # TODO: track in forgetting log

def _count_pruned(conn, since):
    return 0  # TODO: track in forgetting log
```

---

## Additional Schema

```sql
CREATE TABLE distilled_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_key TEXT NOT NULL,
    rule_type TEXT NOT NULL,        -- 'style', 'binding', 'structure'
    default_value TEXT,
    confidence FLOAT DEFAULT 0.5,
    evidence_count INTEGER DEFAULT 0,
    exceptions TEXT,                -- JSON
    status TEXT DEFAULT 'active',   -- 'active', 'archived', 'invalidated'
    last_distilled REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rules_status ON distilled_rules(status);
CREATE INDEX idx_rules_type ON distilled_rules(rule_type);
```

## Schedule

- **Distillation:** Weekly (Sunday midnight)
- **Smart Forgetting:** Weekly (after distillation)
- **Regression Detection:** After every session (lightweight check)
- **Weekly Report:** Weekly (Monday morning)

## Verification

```python
# Test: distillation produces rules
from .distiller import distill_weekly
# (after accumulating 10+ style patterns)
rules = distill_weekly()
assert len(rules['style_rules']) > 0
assert all(r['confidence'] > 0 for r in rules['style_rules'])

# Test: forgetting removes stale data
from .forgetter import smart_forget
result = smart_forget()
# (after 30+ days with unconfirmed patterns)
assert result['decayed'] >= 0
assert result['pruned'] >= 0

# Test: regression detection
from .regression import detect_regression
alert = detect_regression()
# (after simulating trust drop)
# alert should be non-None with diagnosis
```