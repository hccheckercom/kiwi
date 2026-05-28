# Phase R2 — Passive Learning Engine [1 tuần]

## Mục đích

Sau mỗi session Claude code theme → Kiwi tự động học patterns.
Không cần user intervention. 0 LLM token.

## Dependencies

- **R0 (Session Capture)** — cần session_log data
- R1 (Context Assembly) — dùng chung memory module

## Files tạo mới

```
agent/reasoning/
├── learner.py             # parse session logs, extract patterns
├── memory.py              # SQLite storage cho patterns + accuracy history
└── task_classifier.py     # infer task type từ file paths
```

## SQLite Schema

```sql
-- File: agent/reasoning/memory.py → init_db()

CREATE TABLE context_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    files_read TEXT NOT NULL,       -- JSON array of file paths
    files_written TEXT NOT NULL,    -- JSON array of file paths
    read_order TEXT,                -- JSON array (preserved order)
    theme TEXT,
    session_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE accuracy_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    brief_used BOOLEAN,            -- Claude có dùng brief không
    re_reads INTEGER DEFAULT 0,    -- số files Claude đọc lại
    edits_after_first INTEGER DEFAULT 0,  -- số lần Edit cùng file
    trust_at_time FLOAT,           -- trust score lúc đó
    session_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE code_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    section_type TEXT,             -- "hero", "product_grid", "checkout_form"
    style_choices TEXT,            -- JSON: {"spacing": "py-8 md:py-12", ...}
    bindings_used TEXT,            -- JSON array: ["wz_cart()", ...]
    structure_hash TEXT,           -- hash of code structure (for dedup)
    theme TEXT,
    file_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE fix_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT,
    file_path TEXT NOT NULL,
    fix_type TEXT,                 -- "kiwi_violation", "logic_error", "style_mismatch"
    edit_count INTEGER,            -- số lần Edit cùng file trong session
    session_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cp_task ON context_patterns(task_type);
CREATE INDEX idx_ah_task ON accuracy_history(task_type);
CREATE INDEX idx_code_task ON code_patterns(task_type);
CREATE INDEX idx_fix_file ON fix_signals(file_path);
```

## Learner — Core Logic

```python
# File: agent/reasoning/learner.py

import json
import re
from pathlib import Path
from .session_query import (
    get_session_reads, get_session_writes, 
    get_read_order_before_write, get_recent_sessions
)
from .memory import (
    save_context_pattern, save_code_pattern, 
    save_fix_signal, update_accuracy_history
)
from .task_classifier import infer_task_type

def learn_from_session(session_id: str) -> dict:
    """
    Main entry point. Chạy SAU mỗi session.
    Parse session log → extract patterns → update memory.
    Returns: summary of what was learned.
    """
    
    reads = get_session_reads(session_id)
    writes = get_session_writes(session_id)
    
    if not writes:
        return {'status': 'skipped', 'reason': 'no writes in session'}
    
    # Filter: chỉ học từ theme files
    theme_writes = [w for w in writes if is_theme_file(w['file'])]
    if not theme_writes:
        return {'status': 'skipped', 'reason': 'no theme files written'}
    
    learned = {
        'context_patterns': 0,
        'code_patterns': 0,
        'fix_signals': 0,
    }
    
    # 1. Extract context patterns
    task_type = infer_task_type([w['file'] for w in theme_writes])
    theme = detect_theme_from_paths([w['file'] for w in theme_writes])
    
    save_context_pattern(
        task_type=task_type,
        files_read=[r['file'] for r in reads],
        files_written=[w['file'] for w in theme_writes],
        read_order=[r['file'] for r in reads],
        theme=theme,
        session_id=session_id,
    )
    learned['context_patterns'] += 1
    
    # 2. Extract code patterns từ written files
    for write in theme_writes:
        file_path = write['file']
        if Path(file_path).exists():
            content = Path(file_path).read_text(encoding='utf-8', errors='ignore')
            pattern = extract_code_pattern(content, file_path, task_type, theme)
            if pattern:
                save_code_pattern(**pattern)
                learned['code_patterns'] += 1
    
    # 3. Detect fix signals (multiple edits to same file = trial-and-error)
    file_edit_counts = {}
    for w in writes:
        if w['tool'] == 'Edit':
            file_edit_counts[w['file']] = file_edit_counts.get(w['file'], 0) + 1
    
    for file_path, count in file_edit_counts.items():
        if count >= 3:  # 3+ edits = likely fixing mistakes
            save_fix_signal(
                task_type=task_type,
                file_path=file_path,
                fix_type='multiple_edits',
                edit_count=count,
                session_id=session_id,
            )
            learned['fix_signals'] += 1
    
    return {'status': 'learned', **learned}


def extract_code_pattern(content: str, file_path: str, task_type: str, theme: str) -> dict | None:
    """Extract style choices + bindings từ PHP/CSS code."""
    
    if not content.strip():
        return None
    
    # Extract Tailwind style choices
    style_choices = {}
    
    # Spacing
    spacing_matches = re.findall(r'py-(\d+)\s+(?:md:py-(\d+))?', content)
    if spacing_matches:
        style_choices['spacing'] = f"py-{spacing_matches[0][0]}"
        if spacing_matches[0][1]:
            style_choices['spacing'] += f" md:py-{spacing_matches[0][1]}"
    
    # Radius
    radius_matches = re.findall(r'rounded-(\w+)', content)
    if radius_matches:
        from collections import Counter
        most_common = Counter(radius_matches).most_common(1)[0][0]
        style_choices['radius'] = f"rounded-{most_common}"
    
    # Container
    container_matches = re.findall(r'max-w-(\w+)', content)
    if container_matches:
        style_choices['container'] = f"max-w-{container_matches[0]}"
    
    # Extract data bindings (wz_* function calls)
    bindings = re.findall(r'wz_\w+\([^)]*\)', content)
    bindings = list(set(bindings))  # dedup
    
    # Section type from file name
    section_type = infer_section_type(file_path)
    
    if not style_choices and not bindings:
        return None
    
    return {
        'task_type': task_type,
        'section_type': section_type,
        'style_choices': json.dumps(style_choices),
        'bindings_used': json.dumps(bindings),
        'structure_hash': hash_structure(content),
        'theme': theme,
        'file_path': file_path,
    }


def is_theme_file(path: str) -> bool:
    """Check if file is in themes/ directory."""
    return 'themes/' in path.replace('\\', '/') or 'themes\\' in path


def detect_theme_from_paths(paths: list[str]) -> str:
    """Extract theme name from file paths."""
    for p in paths:
        normalized = p.replace('\\', '/')
        if 'themes/' in normalized:
            parts = normalized.split('themes/')[1].split('/')
            if parts:
                return parts[0]
    return 'unknown'


def infer_section_type(file_path: str) -> str:
    """Infer section type from file name."""
    name = Path(file_path).stem.lower()
    
    section_map = {
        'hero': 'hero',
        'header': 'header',
        'footer': 'footer',
        'cart': 'cart',
        'checkout': 'checkout_form',
        'product': 'product_card',
        'archive': 'product_grid',
        'search': 'search',
        'sidebar': 'sidebar',
        'nav': 'navigation',
    }
    
    for keyword, section in section_map.items():
        if keyword in name:
            return section
    
    return 'generic'


def hash_structure(content: str) -> str:
    """Hash code structure (ignore whitespace, comments, specific values)."""
    import hashlib
    # Remove comments, whitespace, string literals
    stripped = re.sub(r'//.*|/\*.*?\*/', '', content, flags=re.DOTALL)
    stripped = re.sub(r"'[^']*'|\"[^\"]*\"", '""', stripped)
    stripped = re.sub(r'\s+', ' ', stripped).strip()
    return hashlib.md5(stripped.encode()).hexdigest()[:12]
```

## Task Classifier

```python
# File: agent/reasoning/task_classifier.py

from pathlib import Path

def infer_task_type(written_files: list[str]) -> str:
    """
    Infer task type từ list of files written.
    Rule-based, deterministic.
    """
    
    # Normalize paths
    files = [Path(f).name.lower() for f in written_files]
    dirs = [str(Path(f).parent).lower().replace('\\', '/') for f in written_files]
    
    # Page types (from file names)
    page_keywords = {
        'checkout': 'checkout_page',
        'cart': 'cart_page',
        'product': 'product_page',
        'home': 'home_page',
        'index': 'home_page',
        'archive': 'archive_page',
        'search': 'search_page',
        'account': 'account_page',
        'login': 'login_page',
        'register': 'register_page',
        'thank': 'thankyou_page',
        'order': 'order_page',
        'wishlist': 'wishlist_page',
        'dashboard': 'dashboard_page',
        'single': 'single_page',
    }
    
    for f in files:
        for keyword, task_type in page_keywords.items():
            if keyword in f:
                return task_type
    
    # Component types (from directory)
    for d in dirs:
        if 'template-parts' in d or 'partials' in d or 'components' in d:
            return 'add_component'
        if 'inc' in d:
            return 'add_utility'
    
    # File extension types
    css_files = [f for f in files if f.endswith('.css')]
    if css_files and not any(f.endswith('.php') for f in files):
        return 'fix_css'
    
    js_files = [f for f in files if f.endswith('.js')]
    if js_files and not any(f.endswith('.php') for f in files):
        return 'fix_js'
    
    # Layout files
    layout_keywords = ['header', 'footer', 'sidebar', 'nav']
    for f in files:
        for keyword in layout_keywords:
            if keyword in f:
                return 'layout_component'
    
    return 'generic'
```

## Trigger: Khi nào chạy learner?

```python
# Option A: Hook-based (chạy khi session kết thúc)
# Trong hooks/post_edit.py — detect "session end" heuristic:
# Nếu không có tool call trong 5 phút → coi như session kết thúc → run learner

# Option B: Scheduled (chạy mỗi giờ)
# Cron job check sessions chưa được learn → learn

# Option C: Manual trigger (MCP tool)
@tool("kiwi_learn")
def handle_kiwi_learn(session_id: str = None) -> dict:
    """Trigger learning from recent session(s)."""
    if session_id:
        return learn_from_session(session_id)
    
    # Learn from all unprocessed sessions
    unprocessed = get_unprocessed_sessions()
    results = []
    for session in unprocessed:
        result = learn_from_session(session['session_id'])
        results.append(result)
        mark_session_processed(session['session_id'])
    
    return {'sessions_processed': len(results), 'results': results}
```

**Recommend: Option C (MCP tool) + Option B (hourly cron) as fallback.**

## Verification

```python
# Simulate a session
from .session_hook import log_tool_call, get_session_id

# Claude reads cart.php, then codes checkout.php
log_tool_call('Read', 'themes/sfvn/templates/cart.php')
log_tool_call('Read', '.claude/blueprint/pages/02-cap1-shop/08-checkout.md')
log_tool_call('Write', 'themes/sfvn/templates/checkout.php')
log_tool_call('Edit', 'themes/sfvn/templates/checkout.php')

# Run learner
result = learn_from_session(get_session_id())
assert result['status'] == 'learned'
assert result['context_patterns'] == 1
assert result['code_patterns'] >= 1

# Verify stored data
from .memory import query_context_patterns
patterns = query_context_patterns('checkout_page')
assert len(patterns) >= 1
assert 'cart.php' in patterns[0]['files_read']  # learned: checkout needs cart context
```

## Constraints

- KHÔNG đọc file content từ session log (chỉ đọc file hiện tại trên disk)
- KHÔNG dùng LLM cho classification (pure regex + rules)
- Dedup: không lưu pattern giống hệt (check structure_hash)
- Max 1000 patterns/task_type (FIFO eviction khi vượt)

---

## AUDIT (2026-05-28) — Trạng thái thực tế vs Plan

### Đã implement (KHÔNG cần làm lại)

| Component | File thực tế | Ghi chú |
|-----------|-------------|---------|
| `learn_from_session()` | `agent/reasoning/learner.py:18` | Đúng plan, hoạt động |
| `learn_all_unprocessed()` | `agent/reasoning/learner.py:71` | Đúng plan |
| Style extraction (spacing, radius, container, shadow, grid) | `learner.py:86-113` | Mở rộng hơn plan (thêm shadow, grid) |
| Binding extraction (wz_*, $product, hooks, wz_component) | `learner.py:116-131` | Mở rộng hơn plan |
| Task classifier (rule-based) | `learner.py:137-171` | Inline thay vì file riêng — OK |
| DB: `context_patterns` | `schema.sql:24` | Đúng plan |
| DB: `style_knowledge` (UPSERT times_seen) | `schema.sql:35` + `learner.py:214-244` | Tốt hơn plan (merge logic) |
| DB: `binding_knowledge` (ON CONFLICT) | `schema.sql:43` + `learner.py:247-257` | Tốt hơn plan |
| DB: `trust_baselines`, `output_quality` | `schema.sql:55,62` | Tables tồn tại, CHƯA có code populate |
| Session logger + ID management | `session_logger.py` | Robust (env var → file → uuid fallback) |
| MCP tool `kiwi_learn_session` | `mcp_server.py:1895-1924` | Hoạt động, gọi manual |

### Schema thực tế vs Plan

Plan đề xuất 4 tables: `context_patterns`, `accuracy_history`, `code_patterns`, `fix_signals`.
Thực tế có 7 tables: `session_log`, `sessions`, `context_patterns`, `style_knowledge`, `binding_knowledge`, `trust_baselines`, `output_quality`.

**Khác biệt quan trọng:**
- Plan's `accuracy_history` → thực tế là `output_quality` (schema rộng hơn: week, brief_version, tokens_estimated, total_tool_calls)
- Plan's `code_patterns` → thực tế KHÔNG tồn tại. Thay bằng `style_knowledge` + `binding_knowledge` (normalized hơn)
- Plan's `fix_signals` → CHƯA implement (không có table, không có code)

### GAP NGHIÊM TRỌNG — Closed Loop CHƯA tồn tại

```
HIỆN TẠI (broken):
  session_log → learner → style_knowledge + binding_knowledge
                                    ↓
                              [DEAD END — không ai đọc]

  context_assembler.py → hardcoded BINDINGS_MAP → brief
  trust_scorer.py → 5 static heuristics → score
  output.py → format static data → KiwiOutput

CẦN (closed loop):
  session_log → learner → style_knowledge + binding_knowledge
                                    ↓
  context_assembler.py → query DB (fallback hardcoded) → brief
  trust_scorer.py → query output_quality + trust_baselines → calibrated score
  output.py → merge learned + static → KiwiOutput
```

### 5 Tasks cần implement (ưu tiên giảm dần)

#### Task 1: Wire DB → context_assembler (HIGH — biến dead data thành useful)

**File:** `agent/reasoning/context_assembler.py`

**Thay đổi:**
- `assemble_context()` → thêm call `_query_learned_styles(theme)` và `_query_learned_bindings(task_type, theme)`
- Merge learned data với hardcoded maps (learned override nếu times_seen >= 3)
- `detect_style_patterns()` → fallback sang DB nếu theme path không tồn tại hoặc empty

**Logic merge:**
```python
def _query_learned_styles(theme: str) -> dict:
    """Query style_knowledge DB. Return dict {pattern_key: value} where times_seen >= 3."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT pattern_key, value FROM style_knowledge WHERE theme = ? AND times_seen >= 3",
        (theme,)
    ).fetchall()
    return {r[0]: r[1] for r in rows}

def _query_learned_bindings(task_type: str, theme: str) -> list:
    """Query binding_knowledge DB. Return bindings seen >= 2 times."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT binding FROM binding_knowledge WHERE task_type = ? AND theme = ? AND times_seen >= 2",
        (task_type, theme)
    ).fetchall()
    return [r[0] for r in rows]
```

#### Task 2: Wire DB → trust_scorer (MEDIUM — trust cải thiện theo thời gian)

**File:** `agent/reasoning/trust_scorer.py`

**Thay đổi:**
- Thêm dimension `learned_data` vào trust score (weight 0.10, lấy từ style+binding)
- Query `trust_baselines` cho task_type → nếu có calibrated score, blend với computed
- Rebalance weights: spec 0.25, maturity 0.20, bindings 0.20, references 0.15, lessons 0.10, learned 0.10

**Logic:**
```python
def _check_learned_data(task_type: str, theme: str) -> float:
    """Score based on how much learned data exists for this task+theme."""
    conn = _get_conn()
    style_count = conn.execute(
        "SELECT COUNT(*) FROM style_knowledge WHERE theme = ? AND times_seen >= 3", (theme,)
    ).fetchone()[0]
    binding_count = conn.execute(
        "SELECT COUNT(*) FROM binding_knowledge WHERE task_type = ? AND theme = ? AND times_seen >= 2",
        (task_type, theme)
    ).fetchone()[0]
    
    if style_count >= 5 and binding_count >= 5:
        return 1.0
    elif style_count >= 3 or binding_count >= 3:
        return 0.7
    elif style_count >= 1 or binding_count >= 1:
        return 0.4
    return 0.0
```

#### Task 3: Accuracy detector (MEDIUM — populate output_quality)

**File:** `agent/reasoning/learner.py` (thêm function)

**Logic:** Sau khi `learn_from_session()` xong, analyze session để detect quality signals:
- `files_re_read`: count files Read > 1 lần (Claude đọc lại = brief thiếu info)
- `edits_after_first`: count files Edit > 1 lần (trial-and-error = brief sai)
- `total_tool_calls`: tổng tool calls trong session
- Populate `output_quality` table

```python
def _compute_session_quality(session_id: str, task_type: str) -> dict:
    conn = _get_conn()
    
    # Count re-reads
    re_reads = conn.execute(
        "SELECT COUNT(*) FROM ("
        "  SELECT file_path, COUNT(*) as cnt FROM session_log"
        "  WHERE session_id = ? AND tool = 'Read' GROUP BY file_path HAVING cnt > 1"
        ")", (session_id,)
    ).fetchone()[0]
    
    # Count multi-edits
    multi_edits = conn.execute(
        "SELECT COUNT(*) FROM ("
        "  SELECT file_path, COUNT(*) as cnt FROM session_log"
        "  WHERE session_id = ? AND tool IN ('Edit','Write') GROUP BY file_path HAVING cnt > 2"
        ")", (session_id,)
    ).fetchone()[0]
    
    # Total tool calls
    total = conn.execute(
        "SELECT COUNT(*) FROM session_log WHERE session_id = ?", (session_id,)
    ).fetchone()[0]
    
    import math
    week = int(time.time() / 604800)
    
    conn.execute(
        "INSERT INTO output_quality (session_id, week, task_type, trust_score, "
        "files_re_read, edits_after_first, total_tool_calls, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (session_id, week, task_type, None, re_reads, multi_edits, total, time.time())
    )
    conn.commit()
    
    return {"re_reads": re_reads, "multi_edits": multi_edits, "total": total}
```

#### Task 4: Auto-trigger (LOW — convenience, manual trigger đã hoạt động)

**Options:**
- A) Hook trong `hooks/post_edit.py` — detect session idle > 5 min → auto learn
- B) Thêm logic vào `kiwi_reason` — mỗi lần gọi, check unprocessed sessions → learn
- C) Giữ manual `kiwi_learn_session` — user/Claude gọi cuối session

**Recommend: Option B** — piggyback vào `kiwi_reason()` call. Mỗi lần Claude gọi `kiwi_reason` cho task mới, nó tự learn sessions cũ trước. Zero extra overhead cho user.

```python
# Trong __init__.py → kiwi_reason()
def kiwi_reason(task: str, theme_path: str) -> KiwiOutput:
    # Auto-learn unprocessed sessions (max 3 per call, ~5ms each)
    _auto_learn_recent(max_sessions=3)
    
    context = assemble_context(task, theme_path)
    trust_score, breakdown = compute_trust_score(context, theme_path)
    return format_output(context, trust_score, breakdown)
```

#### Task 5: Pattern mining (LOW — nice-to-have, cần data trước)

**Chưa cần implement.** Cần ít nhất 20+ sessions trong DB trước khi mining có ý nghĩa. Revisit sau 2 tuần sử dụng.

**Concept:** Aggregate `context_patterns` → tìm "task_type X luôn đọc file Y trước khi write Z" → auto-add Y vào `files_needed` cho task_type X.

### Thứ tự implement khuyến nghị

```
Task 1 (wire assembler)  → 30 min  → immediate value
Task 3 (accuracy)        → 20 min  → feeds Task 2
Task 2 (wire trust)      → 20 min  → needs Task 3 data
Task 4 (auto-trigger)    → 10 min  → convenience
Task 5 (mining)          → defer   → needs 2 weeks of data
```

**Tổng effort: ~80 min cho Task 1-4. Task 5 defer.**

### Test plan

```python
# Sau khi implement Task 1-4:

# 1. Seed test data
from agent.reasoning.session_logger import _get_conn
conn = _get_conn()
conn.execute("INSERT INTO style_knowledge VALUES (NULL, 'sfvn', 'spacing_base', '4', 5, ?)", (time.time(),))
conn.execute("INSERT INTO binding_knowledge VALUES (NULL, 'checkout_page', 'wz_cart()', 'sfvn', 4, ?)", (time.time(),))
conn.commit()

# 2. Verify assembler reads DB
from agent.reasoning.context_assembler import assemble_context
ctx = assemble_context("tạo checkout page", "themes/sfvn")
assert 'wz_cart()' in str(ctx.bindings)  # learned binding appears

# 3. Verify trust scorer uses learned dimension
from agent.reasoning.trust_scorer import compute_trust_score
score, breakdown = compute_trust_score(ctx, "themes/sfvn")
assert 'learned_data' in breakdown

# 4. Verify accuracy tracking
from agent.reasoning.learner import learn_from_session
# (simulate session with re-reads)
result = learn_from_session("test-session")
quality = conn.execute("SELECT * FROM output_quality WHERE session_id = 'test-session'").fetchone()
assert quality is not None
```
