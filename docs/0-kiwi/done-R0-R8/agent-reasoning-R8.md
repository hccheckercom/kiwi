# Phase R8 — Selective Thinking [1 tuần]

## Mục đích

Thêm LLM reasoning cho **5% edge cases** mà deterministic logic không đủ.
95% calls vẫn 0 token (~50ms). 5% calls tốn ~200 tokens Haiku (~100ms).

**Nguyên tắc:** Think only when confused. Compute when confident.

## Dependencies

- **R6 (Graduated Autonomy)** — cần code generation output
- **R3 (Trust Calibration)** — cần trust scores + signals
- **R5 (Cross-Theme)** — cần multi-pattern data
- **Haiku API** — model rẻ nhất cho reasoning

## Khi nào cần Think?

| Trigger | Deterministic fails vì... | Think giải quyết bằng... |
|---------|--------------------------|--------------------------|
| Pattern conflict | 2+ cross-theme patterns cùng task, success_rate gần nhau | Chọn pattern phù hợp nhất dựa trên context |
| Quality fix | `check_code_quality()` fail → fallback brief_only | Sửa code thay vì bỏ cuộc |
| Borderline trust | Trust 0.55-0.65 → skeleton hay brief_only? | Đánh giá task complexity thực tế |
| Novel validation | Novel pattern detected 3+ lần → promote? | Kiểm tra pattern có đúng best practice không |
| Style ambiguity | Target theme chưa có style_knowledge | Infer style từ industry DNA + existing code |

## Files tạo mới

```
agent/reasoning/
├── thinker.py             # LLM reasoning orchestrator
├── think_prompts.py       # Prompt templates cho từng trigger
├── think_cache.py         # Cache kết quả thinking (avoid re-think)
└── test_r8.py             # Tests
```

---

## Architecture

```
kiwi_reason()
  ├── [deterministic path — 95%]
  │   └── assemble → score → brief → generate → output
  │
  └── [thinking path — 5%]
      └── detect_confusion() → think() → apply_insight() → output
```

**Gate:** `should_think()` quyết định có cần LLM không. Chỉ True khi:
1. Confidence gap < 0.15 giữa 2 options (ambiguous)
2. Quality check failed nhưng code gần đúng (fixable)
3. Trust borderline ± 0.05 quanh threshold
4. Novel pattern cần semantic validation

---

## Module 1: thinker.py

```python
"""R8 — Selective Thinking: LLM reasoning for edge cases only."""

import json
import time
import hashlib
from dataclasses import dataclass
from pathlib import Path

from .session_logger import _get_conn
from .output import KiwiOutput
from .think_prompts import get_prompt
from .think_cache import get_cached, save_cached


@dataclass
class ThinkResult:
    trigger: str
    decision: str
    reasoning: str
    confidence: float
    tokens_used: int
    cached: bool = False


# Triggers that activate thinking
THINK_TRIGGERS = {
    'pattern_conflict',
    'quality_fix',
    'borderline_trust',
    'novel_validation',
    'style_ambiguity',
}

# Budget: max tokens per think call
MAX_THINK_TOKENS = 300
# Budget: max think calls per session
MAX_THINKS_PER_SESSION = 3
# Cooldown between thinks
THINK_COOLDOWN_SEC = 10.0

_last_think_ts: float = 0.0
_session_think_count: int = 0


def should_think(trigger: str, context: dict) -> bool:
    """Gate: decide if LLM reasoning is needed. Conservative by default."""
    global _session_think_count

    if trigger not in THINK_TRIGGERS:
        return False

    if _session_think_count >= MAX_THINKS_PER_SESSION:
        return False

    if (time.time() - _last_think_ts) < THINK_COOLDOWN_SEC:
        return False

    # Check cache first — if we've thought about this before, skip
    cache_key = _make_cache_key(trigger, context)
    if get_cached(cache_key):
        return False

    # Trigger-specific gates
    if trigger == 'pattern_conflict':
        patterns = context.get('patterns', [])
        if len(patterns) < 2:
            return False
        # Only think if top 2 patterns have similar success rates
        rates = sorted([p.get('confidence', 0) for p in patterns], reverse=True)
        return len(rates) >= 2 and (rates[0] - rates[1]) < 0.15

    elif trigger == 'quality_fix':
        code = context.get('code', '')
        violations = context.get('violations', [])
        # Only think if code is mostly good (1-2 violations, not 5+)
        return 0 < len(violations) <= 2

    elif trigger == 'borderline_trust':
        trust = context.get('trust_score', 0)
        threshold = context.get('threshold', 0.6)
        return abs(trust - threshold) < 0.05

    elif trigger == 'novel_validation':
        times_seen = context.get('times_seen', 0)
        return times_seen >= 3

    elif trigger == 'style_ambiguity':
        style_count = context.get('style_knowledge_count', 0)
        return style_count == 0

    return False


def think(trigger: str, context: dict) -> ThinkResult | None:
    """Invoke LLM for reasoning. Returns decision + reasoning."""
    global _last_think_ts, _session_think_count

    if not should_think(trigger, context):
        return None

    cache_key = _make_cache_key(trigger, context)
    cached = get_cached(cache_key)
    if cached:
        return ThinkResult(
            trigger=trigger,
            decision=cached['decision'],
            reasoning=cached['reasoning'],
            confidence=cached['confidence'],
            tokens_used=0,
            cached=True,
        )

    prompt = get_prompt(trigger, context)
    if not prompt:
        return None

    # Call LLM (Haiku — cheapest)
    try:
        response = _call_haiku(prompt)
    except Exception:
        return None

    _last_think_ts = time.time()
    _session_think_count += 1

    result = _parse_response(trigger, response)
    if result:
        save_cached(cache_key, {
            'decision': result.decision,
            'reasoning': result.reasoning,
            'confidence': result.confidence,
        })
        _log_think_event(trigger, context, result)

    return result


def _call_haiku(prompt: str) -> str:
    """Call Haiku model. Minimal wrapper."""
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=MAX_THINK_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def _parse_response(trigger: str, response: str) -> ThinkResult | None:
    """Parse LLM response into structured ThinkResult."""
    try:
        # Expect JSON response from prompt template
        data = json.loads(response)
        return ThinkResult(
            trigger=trigger,
            decision=data.get('decision', ''),
            reasoning=data.get('reasoning', ''),
            confidence=data.get('confidence', 0.5),
            tokens_used=len(response.split()) * 2,  # rough estimate
        )
    except json.JSONDecodeError:
        # Fallback: treat entire response as reasoning
        return ThinkResult(
            trigger=trigger,
            decision=response.split('\n')[0][:100],
            reasoning=response[:300],
            confidence=0.5,
            tokens_used=len(response.split()) * 2,
        )


def _make_cache_key(trigger: str, context: dict) -> str:
    """Deterministic cache key from trigger + context."""
    relevant = {
        'trigger': trigger,
        'task_type': context.get('task_type', ''),
        'theme': context.get('theme', ''),
    }
    raw = json.dumps(relevant, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _log_think_event(trigger: str, context: dict, result: ThinkResult):
    """Log thinking event for metrics."""
    conn = _get_conn()
    if not conn:
        return
    try:
        conn.execute(
            "INSERT INTO think_events "
            "(trigger, task_type, theme, decision, confidence, tokens_used, cached, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                trigger,
                context.get('task_type', ''),
                context.get('theme', ''),
                result.decision,
                result.confidence,
                result.tokens_used,
                1 if result.cached else 0,
                time.time(),
            ),
        )
        conn.commit()
    except Exception:
        pass
```

---

## Module 2: think_prompts.py

```python
"""R8 — Prompt templates for selective thinking."""


PROMPTS = {
    'pattern_conflict': """You are choosing between {n} layout patterns for a {task_type} page.

Patterns:
{patterns_desc}

Target theme: {theme} (industry: {industry})
Style: {style_summary}

Which pattern fits best? Reply JSON:
{{"decision": "pattern_index (0-based)", "reasoning": "one sentence why", "confidence": 0.0-1.0}}""",

    'quality_fix': """This generated PHP code has {n} issues:
{violations}

Code (relevant section):
```php
{code_snippet}
```

Fix the issues. Reply JSON:
{{"decision": "fixed_code_snippet", "reasoning": "what was wrong", "confidence": 0.0-1.0}}""",

    'borderline_trust': """Task: {task_type} for theme {theme}.
Trust score: {trust_score} (threshold: {threshold}).
Signals: {signals}

Should Kiwi attempt code generation (skeleton level) or stay brief-only?
Consider: task complexity, available data, risk of bad output.

Reply JSON:
{{"decision": "generate" or "brief_only", "reasoning": "one sentence", "confidence": 0.0-1.0}}""",

    'novel_validation': """Pattern detected {times_seen} times across sessions:
Pattern: {pattern}
Type: {pattern_type}
Context: used in {task_type} for theme {theme}

Is this a good practice worth promoting to a Kiwi lesson?
Consider: security, performance, maintainability, Wezone conventions.

Reply JSON:
{{"decision": "promote" or "skip", "reasoning": "one sentence", "confidence": 0.0-1.0}}""",

    'style_ambiguity': """New theme "{theme}" has no style data yet.
Industry: {industry}
Available industry DNA: {dna_summary}

Suggest Tailwind style tokens for this theme.
Reply JSON:
{{"decision": "style_tokens", "reasoning": "based on industry", "confidence": 0.0-1.0,
  "tokens": {{"radius": "...", "spacing_base": "...", "container": "...", "shadow": "..."}}
}}""",
}


def get_prompt(trigger: str, context: dict) -> str | None:
    """Build prompt from template + context."""
    template = PROMPTS.get(trigger)
    if not template:
        return None

    try:
        return template.format(**context)
    except KeyError:
        return None
```

---

## Module 3: think_cache.py

```python
"""R8 — Think Cache: avoid re-thinking the same question."""

import time
from .session_logger import _get_conn

CACHE_TTL_SEC = 3600  # 1 hour
MAX_CACHE_SIZE = 200


def get_cached(cache_key: str) -> dict | None:
    """Get cached think result. Returns None if miss or expired."""
    conn = _get_conn()
    if not conn:
        return None

    try:
        row = conn.execute(
            "SELECT decision, reasoning, confidence, created_at "
            "FROM think_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()

        if not row:
            return None

        if (time.time() - row[3]) > CACHE_TTL_SEC:
            conn.execute("DELETE FROM think_cache WHERE cache_key = ?", (cache_key,))
            conn.commit()
            return None

        return {
            'decision': row[0],
            'reasoning': row[1],
            'confidence': row[2],
        }
    except Exception:
        return None


def save_cached(cache_key: str, result: dict):
    """Save think result to cache."""
    conn = _get_conn()
    if not conn:
        return

    try:
        conn.execute(
            "INSERT OR REPLACE INTO think_cache "
            "(cache_key, decision, reasoning, confidence, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (cache_key, result['decision'], result['reasoning'],
             result['confidence'], time.time()),
        )

        # FIFO eviction
        count = conn.execute("SELECT COUNT(*) FROM think_cache").fetchone()[0]
        if count > MAX_CACHE_SIZE:
            conn.execute(
                "DELETE FROM think_cache WHERE rowid IN ("
                "  SELECT rowid FROM think_cache ORDER BY created_at ASC LIMIT ?"
                ")",
                (count - MAX_CACHE_SIZE,),
            )
        conn.commit()
    except Exception:
        pass


def invalidate_cache(task_type: str = None, theme: str = None):
    """Invalidate cache entries matching criteria."""
    conn = _get_conn()
    if not conn:
        return

    try:
        if task_type and theme:
            conn.execute(
                "DELETE FROM think_cache WHERE cache_key LIKE ?",
                (f"%{task_type}%{theme}%",),
            )
        conn.commit()
    except Exception:
        pass
```

---

## Schema Addition

```sql
-- R8: Thinking events log
CREATE TABLE IF NOT EXISTS think_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger TEXT NOT NULL,
    task_type TEXT,
    theme TEXT,
    decision TEXT,
    confidence REAL,
    tokens_used INTEGER DEFAULT 0,
    cached INTEGER DEFAULT 0,
    created_at REAL
);

-- R8: Think cache (avoid re-thinking)
CREATE TABLE IF NOT EXISTS think_cache (
    cache_key TEXT PRIMARY KEY,
    decision TEXT NOT NULL,
    reasoning TEXT,
    confidence REAL DEFAULT 0.5,
    created_at REAL
);

CREATE INDEX IF NOT EXISTS idx_te_trigger ON think_events(trigger);
CREATE INDEX IF NOT EXISTS idx_tc_key ON think_cache(cache_key);
```

---

## Integration Points

### 1. Pattern Conflict → trong `autonomy.py`

```python
# Khi generate_graduated_output() gặp 2+ patterns
from .thinker import should_think, think

if len(candidate_patterns) >= 2:
    ctx = {'patterns': candidate_patterns, 'task_type': task_type, 'theme': theme_name}
    if should_think('pattern_conflict', ctx):
        result = think('pattern_conflict', ctx)
        if result and result.decision.isdigit():
            chosen_pattern = candidate_patterns[int(result.decision)]
```

### 2. Quality Fix → trong `autonomy.py`

```python
# Khi check_code_quality() fails
if output.code and not check_code_quality(output.code):
    violations = get_violations(output.code)
    ctx = {'code_snippet': output.code[:500], 'violations': violations, 'n': len(violations)}
    if should_think('quality_fix', ctx):
        result = think('quality_fix', ctx)
        if result and result.confidence >= 0.7:
            output.code = result.decision  # fixed code
        else:
            output.level = "brief_only"
            output.code = None
```

### 3. Borderline Trust → trong `autonomy.py`

```python
# Khi trust gần threshold
if 0.55 <= trust_score <= 0.65:
    ctx = {'trust_score': trust_score, 'threshold': 0.6, 'task_type': task_type, ...}
    if should_think('borderline_trust', ctx):
        result = think('borderline_trust', ctx)
        if result and result.decision == 'generate':
            level = 'skeleton'  # override brief_only
```

### 4. Novel Validation → trong `auto_promoter.py`

```python
# Trước khi promote pattern thành lesson
ctx = {'pattern': pattern['pattern'], 'times_seen': pattern['times_seen'], ...}
if should_think('novel_validation', ctx):
    result = think('novel_validation', ctx)
    if result and result.decision == 'skip':
        return None  # don't promote
```

### 5. Style Ambiguity → trong `cold_start.py`

```python
# Khi bootstrap không tìm được industry peers
ctx = {'theme': theme_name, 'industry': industry, 'dna_summary': dna}
if should_think('style_ambiguity', ctx):
    result = think('style_ambiguity', ctx)
    if result and 'tokens' in json.loads(result.decision):
        # Bootstrap style from LLM suggestion
```

---

## Cost Analysis

| Scenario | Calls/session | Tokens/call | Cost/session |
|----------|--------------|-------------|--------------|
| No thinking needed | 0 | 0 | $0 |
| 1 edge case | 1 | ~200 | ~$0.0002 |
| Max (3 thinks) | 3 | ~200 | ~$0.0006 |
| Cached hit | 0 | 0 | $0 |

**Worst case:** $0.0006/session. **Average:** $0.0001/session (most sessions don't trigger).

Compare: Claude Sonnet full session = $0.05-0.50. Thinking adds < 0.1% overhead.

---

## Safety Guards

1. **Budget cap:** Max 3 thinks per session, max 300 tokens each
2. **Cooldown:** 10s between thinks (prevent rapid-fire)
3. **Cache:** Same question → same answer (1h TTL)
4. **Fallback:** If Haiku fails/timeout → use deterministic path (no crash)
5. **Confidence gate:** Only apply think result if confidence >= 0.7
6. **No auto-apply:** Think results for code fixes still need Claude review
7. **Logging:** All think events logged for audit + cost tracking

---

## Metrics (feeds into R7)

```python
# Dashboard additions:
# - think_calls_per_week (should be low, 5-15% of sessions)
# - think_cache_hit_rate (should increase over time)
# - think_accuracy (decisions that led to positive calibration)
# - think_cost_per_week (should stay < $0.01)
```

---

## Verification

```python
# Level determination
assert should_think('pattern_conflict', {'patterns': [{'confidence': 0.8}, {'confidence': 0.75}]}) == True
assert should_think('pattern_conflict', {'patterns': [{'confidence': 0.9}, {'confidence': 0.5}]}) == False
assert should_think('pattern_conflict', {'patterns': [{'confidence': 0.8}]}) == False

# Borderline trust
assert should_think('borderline_trust', {'trust_score': 0.58, 'threshold': 0.6}) == True
assert should_think('borderline_trust', {'trust_score': 0.45, 'threshold': 0.6}) == False

# Quality fix
assert should_think('quality_fix', {'code': '...', 'violations': ['v1']}) == True
assert should_think('quality_fix', {'code': '...', 'violations': ['v1','v2','v3','v4','v5']}) == False

# Budget enforcement
# After 3 thinks, should_think returns False regardless
```

---

## So sánh R6 vs R8

| Aspect | R6 (Generate) | R8 (Think) |
|--------|--------------|------------|
| LLM cost | 0 | ~200 tokens Haiku (5% of sessions) |
| Latency | ~50ms | ~100-200ms (only when triggered) |
| Trigger | Always (trust-based) | Only when confused |
| Output | Code (skeleton/draft/ready) | Decision (which pattern, fix code, promote?) |
| Fallback | brief_only | Deterministic path (no degradation) |

**R8 không thay thế R6.** R8 cải thiện R6 decisions ở edge cases.

---

## Implementation Steps

| # | Task | Effort |
|---|------|--------|
| 1 | Schema: `think_events` + `think_cache` tables | 10 min |
| 2 | `think_cache.py`: get/save/invalidate | 20 min |
| 3 | `think_prompts.py`: 5 prompt templates | 20 min |
| 4 | `thinker.py`: should_think + think + parse | 40 min |
| 5 | Integration: hook vào autonomy.py (pattern_conflict + quality_fix + borderline) | 30 min |
| 6 | Integration: hook vào auto_promoter.py (novel_validation) | 15 min |
| 7 | Integration: hook vào cold_start.py (style_ambiguity) | 15 min |
| 8 | `test_r8.py`: mock LLM, test gates, test cache, test budget | 45 min |
| 9 | Fallback tests: verify no crash when Haiku unavailable | 15 min |

**Total:** ~3.5 giờ

---

## Roadmap Beyond R8

```
R8  — Selective Thinking (edge cases only, Haiku)
R9  — Reflective Learning (think results feed back into trust calibration)
R10 — Multi-Model Routing (Haiku for simple thinks, Sonnet for complex)
R11 — Predictive Prefetch (anticipate next task, pre-compute brief)
```
