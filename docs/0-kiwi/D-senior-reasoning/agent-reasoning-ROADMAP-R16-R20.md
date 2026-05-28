# Phase R16-R20 — From Junior to Senior: Closing the Reasoning Gap

## Vấn đề hiện tại

Kiwi R0-R15 là **pattern matcher** — chỉ output code khi đã thấy pattern tương tự trước đó. Khi gặp:
- Requirements mới chưa từng thấy → fallback brief_only (bó tay)
- Edge cases không có trong lessons → bỏ sót
- Creative decisions (layout mới, UX mới) → không có opinion

Đây là ceiling của "junior dev". Để lên "mid-level dev", Kiwi cần:
1. **Decompose** novel tasks thành sub-tasks đã biết
2. **Reason** về edge cases từ first principles
3. **Propose** creative alternatives dựa trên constraints

---

## R16 — Task Decomposition Engine [1 tuần]

**Mục đích:** Novel task → break thành sub-tasks đã biết. Nếu 80% sub-tasks có pattern → Kiwi handle được.

**Core idea:**
- "Tạo trang loyalty points" = novel (chưa có pattern)
- Decompose: header (known) + form (known) + points table (known) + API call (known) + business logic (novel)
- Kiwi generate 4/5 parts, Claude chỉ cần handle business logic

**Modules:**
```
agent/reasoning/
├── decomposer.py          # break task → sub-tasks
├── task_graph.py           # dependency graph giữa sub-tasks
├── coverage_scorer.py     # % sub-tasks Kiwi có thể handle
└── test_r16.py
```

**Decomposition strategy (deterministic + LLM hybrid):**
```python
def decompose(task: str, theme_path: str) -> list[SubTask]:
    # Step 1: Deterministic — match known components
    known_parts = match_known_components(task)  # header, footer, form, grid, etc.
    
    # Step 2: LLM (Haiku) — identify remaining novel parts
    if coverage(known_parts) < 0.8:
        novel_parts = think('decompose', {
            'task': task,
            'known_parts': known_parts,
            'available_components': get_component_registry(),
        })
    
    # Step 3: Build dependency graph
    return build_task_graph(known_parts + novel_parts)
```

**Output cho Claude:**
```
Task: "Tạo trang loyalty points"
Kiwi handles (4/5):
  ✓ Page skeleton (trust 0.9)
  ✓ Header section (trust 0.85)
  ✓ Data table component (trust 0.8)
  ✓ Form component (trust 0.75)
Claude handles (1/5):
  ✗ Points calculation logic (novel — no pattern)
```

**Value:** Claude chỉ code 20% thay vì 100%. Token savings ngay cả cho novel tasks.

---

## R17 — Edge Case Reasoning [1 tuần]

**Mục đích:** Phát hiện edge cases từ first principles, không cần lesson có sẵn.

**Core idea:**
- Hiện tại: Kiwi chỉ warn về edge cases đã ghi trong lessons
- R17: Kiwi suy luận edge cases từ data types + business rules
- Ví dụ: thấy `$product['price']` → tự suy ra: "price có thể = 0? có thể null? có thể negative?"

**Modules:**
```
agent/reasoning/
├── edge_reasoner.py       # infer edge cases from code structure
├── invariant_db.py        # known invariants per data type
├── test_r17.py
```

**Invariant database (deterministic, 0 token):**
```python
INVARIANTS = {
    'price': ['>= 0', 'not null', 'numeric', 'max 999999999'],
    'quantity': ['>= 0', 'integer', 'max 9999'],
    'email': ['valid format', 'not empty', 'max 254 chars'],
    'phone': ['digits only', '10-11 chars for VN'],
    'slug': ['lowercase', 'no spaces', 'unique'],
    'image_url': ['valid URL or empty', 'https preferred'],
}

# Khi thấy code dùng $product['price'] mà không check null:
# → auto-inject warning: "Missing null check for price"
```

**LLM escalation:** Chỉ khi invariant DB không cover → Haiku suy luận:
```
"Function nhận user_input nhưng không sanitize. 
Possible edge cases: XSS injection, SQL injection, empty string, unicode overflow."
```

**Integration:** Inject edge case warnings vào brief output. Claude thấy warnings → handle trong code.

---

## R18 — Creative Alternatives Engine [1 tuần]

**Mục đích:** Khi task có nhiều valid approaches, Kiwi propose 2-3 alternatives thay vì chỉ 1.

**Core idea:**
- Hiện tại: Kiwi chọn 1 pattern (highest success_rate) → output
- R18: Kiwi present 2-3 options với tradeoffs → Claude/user chọn
- Ví dụ: "Hero section" → Option A (full-width image), Option B (split text+image), Option C (video background)

**Modules:**
```
agent/reasoning/
├── alternatives.py        # generate 2-3 options per task
├── tradeoff_analyzer.py   # analyze pros/cons per option
├── preference_learner.py  # learn user's aesthetic preferences over time
└── test_r18.py
```

**Sources of alternatives:**
1. Cross-theme patterns (different themes solved same task differently)
2. Industry DNA variations (beauty vs tech vs luxury → different aesthetics)
3. Component variants (`.claude/blueprint/variations/components/`)
4. Historical user choices (preference_learner tracks which options user picks)

**Output format:**
```
Task: Hero section for beauty theme

Option A: Full-width image + overlay text
  - Confidence: 0.85 (used in 3 beauty themes)
  - Tradeoff: high visual impact, slow load (large image)
  
Option B: Split layout (image left, text right)  
  - Confidence: 0.75 (used in 2 beauty themes)
  - Tradeoff: balanced, good for mobile, less dramatic

Option C: Slider with multiple products
  - Confidence: 0.70 (used in 1 beauty theme)
  - Tradeoff: shows more products, complex JS, slower

Kiwi recommendation: Option A (matches beauty DNA: visual-first)
```

**Preference learning:** Track user's choices → next time auto-recommend preferred style.

---

## R19 — Requirement Inference [3 ngày]

**Mục đích:** Khi user gives vague requirement, Kiwi infer missing details từ context.

**Core idea:**
- User: "Thêm trang checkout"
- Hiện tại: Kiwi output generic checkout skeleton
- R19: Kiwi infer: "Theme này là beauty → checkout cần: gift wrapping option, sample request, loyalty points display" (từ industry DNA + similar themes)

**Modules:**
```
agent/reasoning/
├── requirement_inferrer.py  # infer missing requirements from context
├── domain_knowledge.py      # industry-specific requirements
└── test_r19.py
```

**Inference sources:**
1. Industry DNA → standard features per industry
2. Similar themes → what they included for same page
3. Store config → enabled features (shipping, payment methods, etc.)
4. Existing pages → consistency (if cart has gift wrap, checkout should too)

**Output:** Enriched brief with inferred requirements:
```
Task: "Thêm trang checkout"
Inferred requirements (from beauty industry + similar themes):
  - Gift wrapping option (3/4 beauty themes have this)
  - Sample request checkbox (2/4 beauty themes)
  - Loyalty points display (store config has loyalty enabled)
  - Express checkout (Momo + ZaloPay — from payment config)
  
Confidence: 0.7 (ask user to confirm before coding)
```

**Safety:** Inferred requirements marked as "suggested" — Claude confirms with user before implementing.

---

## R20 — Autonomous Learning from Failures [1 tuần]

**Mục đích:** Khi Claude rejects Kiwi's output, Kiwi tự phân tích TẠI SAO bị reject và học để không lặp lại.

**Core idea:**
- Hiện tại: rejection → trust giảm (R6 approval_tracker). Nhưng Kiwi không biết TẠI SAO.
- R20: Kiwi diff rejected code vs Claude's final code → extract "what was wrong"
- Tự tạo lesson từ failure → prevent same mistake next time

**Modules:**
```
agent/reasoning/
├── failure_analyzer.py    # diff rejected vs accepted → extract lesson
├── self_lesson_writer.py  # auto-create Kiwi lesson from failure
├── regression_guard.py    # prevent generating same mistake twice
└── test_r20.py
```

**Flow:**
```
1. Kiwi generates draft code
2. Claude rejects/modifies heavily
3. failure_analyzer diffs: what did Claude change?
4. Categorize: style issue? logic bug? missing feature? wrong pattern?
5. If pattern (3+ similar failures) → auto-create lesson
6. regression_guard blocks same mistake in future generations
```

**Example:**
```
Failure: Kiwi generated checkout with 1-col layout
Claude changed to: 2-col (main + order summary sidebar)
Analysis: checkout_page for themes with > 5 products should use 2-col
Auto-lesson: "checkout_page + product_count > 5 → 2-col layout"
```

**This closes the loop:** Kiwi fails → learns why → doesn't fail same way again. Over time, failure rate drops toward 0 for known task types.

---

## Evolution Summary

| Phase | Kiwi's role | Claude's role | Token split |
|-------|------------|---------------|-------------|
| R0-R6 | Pattern matcher | Code everything | 30/70 |
| R7-R8 | Self-aware matcher | Code + review | 40/60 |
| R9-R15 | Predictive coder | Review + novel cases | 60/40 |
| R16-R18 | Creative proposer | Choose + refine | 70/30 |
| R19-R20 | Self-learning coder | Approve + edge cases only | 80/20 |

**After R20:** Kiwi handles 80% of work autonomously. Claude's role narrows to:
- Approving Kiwi's output (5 seconds vs 5 minutes coding)
- Handling truly novel requirements (first-time features)
- Making creative decisions when Kiwi presents options
- Edge cases that require human judgment (business logic, UX decisions)

---

## True Ceiling

Kiwi sẽ KHÔNG BAO GIỜ:
- Hiểu business context mới (tại sao client muốn feature X)
- Đưa ra UX decisions không có precedent
- Negotiate requirements với stakeholders
- Hiểu implicit constraints chưa được nói ra

Đây là boundary giữa "code generation" và "software engineering". Kiwi optimize phần code generation. Claude + human handle phần engineering.

**Asymptote sau R20:** ~500 tokens/session cho 80% tasks, ~3000 tokens cho 20% novel tasks. Average: ~1000 tokens/session. Giảm 90% so với baseline 10,000.

---

## Priority & Timeline

| Phase | Value | Effort | When |
|-------|-------|--------|------|
| R16 Task Decomposition | Very High | 1 week | After R8 |
| R17 Edge Case Reasoning | High | 1 week | After R16 |
| R18 Creative Alternatives | Medium-High | 1 week | After R17 |
| R19 Requirement Inference | Medium | 3 days | After R18 |
| R20 Autonomous Failure Learning | Very High | 1 week | After R19 |

**Total R16-R20:** ~5 weeks. Biến Kiwi từ "junior dev" thành "mid-level dev tự học".

---

## R21 — Learning from the Senior [1 tuần]

**Mục đích:** Kiwi observe Claude's reasoning process → extract decision patterns → dần handle những thứ "chỉ senior mới biết".

**Core idea:**
R0-R20 Kiwi học từ **code output** (files written, styles used, bindings called). R21 Kiwi học từ **reasoning process** — câu hỏi Claude hỏi, decisions Claude đưa ra, constraints Claude phát hiện giữa session.

**4 learning channels:**

### Channel 1: Question Patterns
- Track: Claude hỏi user gì trước khi code? (clarifying questions)
- Learn: task_type X thường cần confirm Y, Z trước khi bắt đầu
- Apply: Kiwi inject "Cần confirm: Y, Z" vào brief → Claude/user thấy ngay

```python
# Ví dụ learned questions:
# checkout_page → ["Có gift wrapping không?", "Payment methods nào?", "Shipping zones?"]
# product_page → ["Có variants không?", "Gallery hay single image?", "Reviews enabled?"]
```

### Channel 2: Decision Trees
- Track: Khi Claude chọn giữa 2+ options (layout, pattern, approach)
- Learn: context signals nào dẫn đến decision nào
- Apply: Kiwi tự chọn đúng option khi gặp context tương tự

```python
# Ví dụ learned decisions:
# IF product_count > 10 AND industry == "fashion" → grid 4-col (not 3-col)
# IF checkout has shipping → 2-col layout (not 1-col)
# IF mobile_first AND hero → slider (not static image)
```

### Channel 3: Constraint Discovery
- Track: Claude phát hiện constraint giữa session (không phải từ spec)
- Learn: constraint nào hay xuất hiện cho task_type + theme_type nào
- Apply: Kiwi warn sớm → Claude không phải discover lại

```python
# Ví dụ learned constraints:
# beauty themes → image aspect ratio must be consistent (discovered in 3 sessions)
# checkout → shipping validation must run before payment (discovered in 2 sessions)
# mobile → touch targets minimum 44px (discovered in 4 sessions)
```

### Channel 4: Recovery Patterns
- Track: Khi Claude gặp lỗi → cách Claude recover (approach change, different strategy)
- Learn: error type X → recovery strategy Y works
- Apply: Kiwi suggest recovery strategy ngay khi detect error pattern

```python
# Ví dụ learned recoveries:
# "Router conflict" → check rewrite rules, not template file
# "Blank page" → check wezone_is_active guard, not PHP syntax
# "Style not applying" → check Tailwind purge config, not CSS specificity
```

**Modules:**
```
agent/reasoning/
├── senior_observer.py     # observe Claude's reasoning signals
├── question_learner.py    # learn clarifying question patterns
├── decision_learner.py    # learn decision trees from choices
├── constraint_learner.py  # learn implicit constraints
├── recovery_learner.py    # learn error recovery strategies
└── test_r21.py
```

**Schema:**
```sql
CREATE TABLE learned_questions (
    id INTEGER PRIMARY KEY,
    task_type TEXT NOT NULL,
    question TEXT NOT NULL,
    times_asked INTEGER DEFAULT 1,
    answers_seen TEXT,  -- JSON: common answers
    impact TEXT,        -- "high" if answer changes approach significantly
    UNIQUE(task_type, question)
);

CREATE TABLE learned_decisions (
    id INTEGER PRIMARY KEY,
    task_type TEXT NOT NULL,
    context_signals TEXT NOT NULL,  -- JSON: what was true when decision was made
    decision TEXT NOT NULL,
    alternative TEXT,               -- what was NOT chosen
    times_seen INTEGER DEFAULT 1,
    success_rate REAL DEFAULT 0.5
);

CREATE TABLE learned_constraints (
    id INTEGER PRIMARY KEY,
    task_type TEXT NOT NULL,
    constraint_text TEXT NOT NULL,
    discovery_context TEXT,  -- how it was discovered
    times_confirmed INTEGER DEFAULT 1,
    severity TEXT DEFAULT 'medium'  -- "critical", "medium", "low"
);

CREATE TABLE learned_recoveries (
    id INTEGER PRIMARY KEY,
    error_pattern TEXT NOT NULL,
    recovery_strategy TEXT NOT NULL,
    times_used INTEGER DEFAULT 1,
    success_rate REAL DEFAULT 0.5
);
```

**Observation signals (from session_log):**
- Claude reads file → writes different file → reads first file again = **constraint discovered**
- Claude asks user question (detected via conversation pattern) = **clarifying question**
- Claude changes approach mid-session (different files than brief suggested) = **decision made**
- Claude encounters error → tries different approach → succeeds = **recovery pattern**

**Maturity thresholds:**
- Question: seen 3+ times → inject into brief
- Decision: seen 5+ times with > 70% success → auto-apply
- Constraint: confirmed 3+ times → inject as warning
- Recovery: used 3+ times with > 80% success → suggest immediately on error

**Token cost:** 0 (pure observation + pattern extraction from session logs). LLM chỉ cần cho semantic clustering (group similar questions/decisions).

**Value:** Sau 50+ sessions, Kiwi biết:
- Hỏi gì trước khi code (thay vì Claude phải hỏi mỗi lần)
- Chọn gì khi có nhiều options (thay vì Claude phải suy nghĩ)
- Cảnh báo constraint gì (thay vì Claude phải discover)
- Recover thế nào khi lỗi (thay vì Claude phải trial-and-error)

**Đây là cách Kiwi thu hẹp gap "chỉ senior mới biết" → "Kiwi cũng biết vì đã thấy senior làm đủ lần".**

---

## Updated Evolution Summary

| Phase | Kiwi's role | Claude's role | Token split |
|-------|------------|---------------|-------------|
| R0-R6 | Pattern matcher | Code everything | 30/70 |
| R7-R8 | Self-aware matcher | Code + review | 40/60 |
| R9-R15 | Predictive coder | Review + novel cases | 60/40 |
| R16-R18 | Creative proposer | Choose + refine | 70/30 |
| R19-R20 | Self-learning coder | Approve + edge cases | 80/20 |
| R21 | Senior-level reasoner | Novel-only + final approve | 85/15 |

**After R21:** Kiwi handles 85% of work. Remaining 15% = truly first-time situations with zero precedent.

---

## Updated Priority & Timeline

| Phase | Value | Effort | When |
|-------|-------|--------|------|
| R16 Task Decomposition | Very High | 1 week | After R8 |
| R17 Edge Case Reasoning | High | 1 week | After R16 |
| R18 Creative Alternatives | Medium-High | 1 week | After R17 |
| R19 Requirement Inference | Medium | 3 days | After R18 |
| R20 Autonomous Failure Learning | Very High | 1 week | After R19 |
| R21 Learning from the Senior | Very High | 1 week | After R20 |

**Total R16-R21:** ~6 weeks. Biến Kiwi từ "junior dev" thành "near-senior dev tự học từ senior".
