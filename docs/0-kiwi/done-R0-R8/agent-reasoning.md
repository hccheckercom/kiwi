# Kiwi Reasoning Layer — Pre-Digest Engine cho Claude

## Mục đích thực sự

Kiwi KHÔNG tự code (tốn LLM token = vô nghĩa).
Kiwi là **bộ não tiền xử lý** — đọc, phân tích, chuẩn bị context — để khi Claude nhận task, Claude chỉ cần execute thay vì explore + think + execute + fix.

**Hiện tại (không có Kiwi reasoning):**
```
User task → Claude đọc 10 files (5000 tokens) → Claude suy nghĩ (3000 tokens)
→ Claude thử sai (2000 tokens) → Claude code (5000 tokens) → Claude fix (2000 tokens)
= ~17000 tokens/task
```

**Với Kiwi reasoning:**
```
User task → Kiwi đọc files, phân tích, gói context (0 token, chạy local Python)
→ Kiwi output: structured brief + confidence score
→ Claude nhận brief (800 tokens) → Claude execute (3000 tokens)
= ~4000 tokens/task (giảm 75%)
```

**Kiwi thông minh dần nhờ Claude:**
```
Claude code → Kiwi quan sát output → Kiwi lưu patterns/decisions
→ Lần sau Kiwi brief tốt hơn → Claude cần ít token hơn
→ Vòng lặp: Claude dạy Kiwi → Kiwi giúp Claude → Claude dạy Kiwi tốt hơn
```

---

## Cơ chế Trust Score — Claude quyết định tin hay không

**Vấn đề**: Kiwi output có thể sai (context cũ, pattern không match, spec thay đổi). Claude cần biết KHI NÀO nên tin Kiwi, khi nào nên tự research lại.

**Giải pháp**: Mỗi output của Kiwi đi kèm `trust_score` — Kiwi tự đánh giá độ tin cậy của chính mình.

### Trust Score Structure

```python
@dataclass
class KiwiOutput:
    content: dict          # context/plan/brief đã chuẩn bị
    trust_score: float     # 0.0 - 1.0
    trust_breakdown: dict  # chi tiết từng dimension
    staleness: str         # "fresh" | "stale" | "unknown"
    evidence: list         # bằng chứng cho score
    recommendation: str    # "trust" | "verify_partial" | "re_research"
```

### 5 Trust Dimensions (tự động, 0 token)

```python
def compute_trust_score(output: KiwiOutput, task: str, theme_path: str) -> float:
    scores = {}
    
    # 1. Data freshness — files Kiwi đọc có bị thay đổi sau khi cache?
    scores['freshness'] = check_file_freshness(output.source_files, theme_path)
    # git diff --stat trên files đã đọc → nếu changed → score giảm
    
    # 2. Pattern confidence — Kiwi đã thấy task tương tự bao nhiêu lần?
    similar_tasks = query_memory(task_type=output.task_type)
    scores['experience'] = min(len(similar_tasks) / 10, 1.0)
    # 0 lần = 0.0, 10+ lần = 1.0
    
    # 3. Historical accuracy — lần trước Kiwi brief cho task tương tự, Claude có phải sửa không?
    past_results = query_accuracy_history(task_type=output.task_type)
    if past_results:
        scores['accuracy'] = sum(r.accepted for r in past_results) / len(past_results)
    else:
        scores['accuracy'] = 0.5  # unknown = neutral
    
    # 4. Spec coverage — Kiwi có tìm được spec/blueprint cho target không?
    scores['spec_found'] = 1.0 if output.content.get('spec') else 0.3
    
    # 5. Internal consistency — các phần trong output có mâu thuẫn không?
    scores['consistency'] = check_internal_consistency(output.content)
    
    # Weighted average
    weights = {'freshness': 0.25, 'experience': 0.2, 'accuracy': 0.3, 'spec_found': 0.15, 'consistency': 0.1}
    trust = sum(scores[k] * weights[k] for k in scores)
    
    return trust, scores
```

### Claude's Decision Logic

Kiwi output đi kèm recommendation. Claude dùng nó để quyết định:

| Trust Score | Recommendation | Claude hành động |
|-------------|---------------|-----------------|
| ≥ 0.85 | `trust` | Dùng Kiwi brief trực tiếp, code ngay |
| 0.6 - 0.85 | `verify_partial` | Dùng brief nhưng spot-check 1-2 files quan trọng |
| < 0.6 | `re_research` | Bỏ qua brief, tự đọc files từ đầu |

**Ví dụ output Kiwi gửi cho Claude:**
```json
{
  "brief": {
    "target": "checkout page",
    "spec_sections": ["shipping_form", "payment", "order_summary"],
    "data_bindings": {"cart": "wz_cart()", "methods": "wz_get_shipping_methods()"},
    "style_pattern": "rounded-xl, py-8 md:py-12, max-w-7xl",
    "lessons": ["LES-045: no hex in PHP", "LES-102: wz_config guard"],
    "reference_page": "themes/sfvn/templates/cart.php"
  },
  "trust_score": 0.82,
  "trust_breakdown": {
    "freshness": 0.9,
    "experience": 0.7,
    "accuracy": 0.85,
    "spec_found": 1.0,
    "consistency": 0.9
  },
  "recommendation": "verify_partial",
  "verify_hint": "cart.php đã bị sửa 2 ngày trước — check style có thay đổi không"
}
```

Claude đọc → thấy `verify_partial` + hint → chỉ cần Read `cart.php` (1 file) thay vì 10 files → tiết kiệm ~4000 tokens.

---

## Training Loop — Kiwi học từ Claude

### Nguyên tắc cốt lõi

**Kiwi KHÔNG tự generate knowledge. Kiwi CHỈ học từ những gì Claude thực sự code.**

Mỗi lần Claude code xong 1 task → Kiwi quan sát và lưu:
1. Task gì? (input)
2. Claude đọc files nào? (context pattern)
3. Claude quyết định gì? (decisions)
4. Claude code ra sao? (output pattern)
5. Code có bị fix lại không? (quality signal)

### Training Data Sources

```python
# Source 1: Claude's file reads — Kiwi học "task X cần đọc files nào"
@dataclass
class ContextPattern:
    task_type: str           # "checkout_page", "product_card", "fix_css"
    files_read: list[str]    # files Claude đọc trước khi code
    files_written: list[str] # files Claude tạo/sửa
    read_order: list[str]    # thứ tự đọc (quan trọng!)
    timestamp: datetime

# Source 2: Claude's decisions — Kiwi học "trong context X, Claude chọn approach Y"
@dataclass  
class DecisionPattern:
    task_type: str
    context_summary: str     # tóm tắt context lúc quyết định
    decision: str            # "dùng 2-col layout", "skip sidebar", "dùng wz_cart()"
    outcome: str             # "accepted" | "revised" | "reverted"
    
# Source 3: Claude's code output — Kiwi học "cho task X, code pattern là Z"
@dataclass
class CodePattern:
    task_type: str
    theme: str
    section_type: str        # "hero", "product_grid", "checkout_form"
    code_structure: str      # abstracted structure (không phải raw code)
    style_choices: dict      # {"spacing": "py-8", "container": "max-w-7xl", ...}
    data_bindings_used: list # ["wz_cart()", "$product['name']"]

# Source 4: Fix signal — Kiwi học "output X bị sửa thành Y → X là sai"
@dataclass
class FixSignal:
    original_code: str       # code Kiwi brief dẫn đến (hoặc Claude tự code)
    fixed_code: str          # code sau khi fix
    fix_type: str            # "kiwi_violation", "logic_error", "style_mismatch"
    lesson_extracted: str    # pattern rút ra
```

### Passive Learning (0 token, chạy sau mỗi Claude session)

```python
def learn_from_claude_session(session_log: list[ToolCall]) -> None:
    """
    Chạy SAU mỗi session Claude code theme.
    Parse tool calls → extract patterns → update Kiwi memory.
    0 LLM token — pure Python analysis.
    """
    
    # Extract context patterns
    reads = [call for call in session_log if call.tool == 'Read']
    writes = [call for call in session_log if call.tool in ('Write', 'Edit')]
    
    if not writes:
        return  # session không code → không học
    
    # Xác định task type từ files written
    task_type = infer_task_type(writes)
    
    # Lưu context pattern: "cho task X, Claude đọc files [A, B, C] theo thứ tự"
    save_context_pattern(ContextPattern(
        task_type=task_type,
        files_read=[r.file_path for r in reads],
        files_written=[w.file_path for w in writes],
        read_order=[r.file_path for r in reads],  # preserve order
        timestamp=now(),
    ))
    
    # Lưu code patterns: extract structure từ written code
    for write in writes:
        if is_theme_file(write.file_path):
            pattern = extract_code_pattern(write.content, task_type)
            save_code_pattern(pattern)
    
    # Detect fixes: nếu Claude Edit file mà Kiwi đã brief → so sánh
    for edit in [c for c in session_log if c.tool == 'Edit']:
        if was_kiwi_briefed(edit.file_path):
            fix = detect_fix_signal(edit)
            if fix:
                save_fix_signal(fix)
                update_accuracy_history(task_type, accepted=False)
            else:
                update_accuracy_history(task_type, accepted=True)
```

### Active Learning (khi Claude code xong → Kiwi tự cập nhật)

```python
def post_code_update(file_path: str, content: str, task: str) -> None:
    """
    Hook chạy SAU mỗi lần Claude Write/Edit file trong themes/.
    Kiwi quan sát và cập nhật knowledge.
    """
    
    # 1. Extract style patterns từ code mới
    new_patterns = extract_style_from_code(content)
    existing_patterns = load_style_patterns(get_theme_path(file_path))
    
    # 2. Nếu style mới khác existing → update (Claude đã quyết định style mới)
    if new_patterns != existing_patterns:
        merge_style_patterns(existing_patterns, new_patterns)
    
    # 3. Extract data bindings thực tế Claude dùng
    bindings_used = extract_bindings_from_code(content)
    update_binding_knowledge(task_type=infer_task_type_from_file(file_path), bindings=bindings_used)
    
    # 4. Nếu Claude dùng pattern mới chưa có trong Kiwi → ghi nhận
    known_patterns = load_known_patterns()
    novel = [p for p in bindings_used if p not in known_patterns]
    if novel:
        save_novel_patterns(novel, source=file_path, task=task)
```

---

## Trust Score Feedback Loop — Kiwi tự calibrate

**Vấn đề**: Trust score ban đầu có thể sai (quá tự tin hoặc quá thận trọng). Cần cơ chế tự điều chỉnh.

### Feedback signal: Claude có dùng Kiwi brief không?

```python
def track_brief_usage(brief: KiwiOutput, claude_actions: list[ToolCall]) -> None:
    """
    Sau mỗi session, check: Claude có dùng brief của Kiwi không?
    """
    
    # Signal 1: Claude đọc lại files mà Kiwi đã brief → Kiwi brief không đủ tin
    re_reads = [f for f in claude_reads if f in brief.source_files]
    
    # Signal 2: Claude code khác hẳn Kiwi suggest → Kiwi brief sai hướng
    divergence = compute_divergence(brief.content, claude_output)
    
    # Signal 3: Claude code giống Kiwi brief → Kiwi brief đúng
    alignment = compute_alignment(brief.content, claude_output)
    
    # Update trust calibration
    if re_reads and divergence > 0.5:
        # Claude không tin brief → Kiwi quá tự tin → giảm trust cho task type này
        adjust_trust_baseline(brief.task_type, delta=-0.1)
    elif alignment > 0.8 and not re_reads:
        # Claude tin brief hoàn toàn → Kiwi đúng → tăng trust
        adjust_trust_baseline(brief.task_type, delta=+0.05)
    
    # Asymmetric: giảm nhanh (sai = nguy hiểm), tăng chậm (đúng = cần chứng minh nhiều lần)
```

### Trust calibration over time

```
Tuần 1: Trust score trung bình 0.5 (Kiwi mới, chưa biết gì)
         → Claude tự research hầu hết tasks
         → Kiwi quan sát, học patterns

Tuần 2-3: Trust tăng lên 0.6-0.7 cho task types đã thấy nhiều lần
           → Claude bắt đầu dùng brief, chỉ verify 1-2 files
           → Kiwi tiếp tục học, accuracy history tích lũy

Tháng 2+: Trust ổn định 0.8-0.9 cho common tasks
           → Claude gần như chỉ execute từ brief
           → Token savings 70-80%

Khi spec thay đổi: Trust tự giảm (freshness dimension detect file changes)
                    → Claude tự research lại → Kiwi học pattern mới
```

---

## Kiến trúc tổng thể

```
┌─────────────────────────────────────────────────────────┐
│                    USER TASK                              │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│  KIWI REASONING (Python, 0 LLM token)                   │
│                                                          │
│  1. Context Assembly                                     │
│     - Đọc files cần thiết (từ learned patterns)          │
│     - Query Kiwi lessons                                 │
│     - Detect style patterns                              │
│     - Load data bindings                                 │
│                                                          │
│  2. Brief Generation                                     │
│     - Gói context thành structured JSON                  │
│     - Tính trust score (5 dimensions)                    │
│     - Đính kèm recommendation + verify hints            │
│                                                          │
│  3. Output: KiwiOutput (brief + trust_score)             │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│  CLAUDE (LLM, tốn token)                                │
│                                                          │
│  IF trust ≥ 0.85: Execute từ brief (3000 tokens)        │
│  IF trust 0.6-0.85: Verify partial + execute (5000 tk)  │
│  IF trust < 0.6: Ignore brief, self-research (15000 tk) │
│                                                          │
│  Output: Code files                                      │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│  KIWI LEARNING (Python, 0 LLM token, chạy sau session)  │
│                                                          │
│  1. Observe: Claude đọc gì? Code gì? Fix gì?            │
│  2. Extract: Context patterns, decisions, code patterns  │
│  3. Evaluate: Brief có được dùng không? Đúng không?      │
│  4. Update: Trust calibration, pattern memory, bindings  │
│                                                          │
│  → Kiwi thông minh hơn cho lần sau                      │
└─────────────────────────────────────────────────────────┘
```

---

## Phases thực hiện

### Phase R1 — Context Assembly + Trust Score [1 tuần]

**Files:**
- `agent/reasoning/context_assembler.py` — đọc files, query lessons, detect patterns
- `agent/reasoning/trust_scorer.py` — tính trust score 5 dimensions
- `agent/reasoning/output.py` — format KiwiOutput cho Claude

**Deliverable:** Kiwi có thể nhận task → output brief + trust score. Claude đọc và quyết định.

**Verification:**
```python
output = kiwi_reason("Tạo trang checkout", "themes/sfvn")
assert output.trust_score >= 0  # score hợp lệ
assert output.recommendation in ("trust", "verify_partial", "re_research")
assert 'spec' in output.content or output.trust_score < 0.5  # nếu không có spec → score thấp
```

---

### Phase R2 — Passive Learning Engine [1 tuần]

**Files:**
- `agent/reasoning/learner.py` — parse session logs, extract patterns
- `agent/reasoning/memory.py` — SQLite storage cho patterns + accuracy history
- `agent/reasoning/hooks.py` — PostToolUse hook để observe Claude

**Deliverable:** Sau mỗi session Claude code theme → Kiwi tự động học patterns. Không cần user intervention.

**Training data format (SQLite):**
```sql
CREATE TABLE context_patterns (
    id INTEGER PRIMARY KEY,
    task_type TEXT,
    files_read TEXT,      -- JSON array
    files_written TEXT,   -- JSON array  
    theme TEXT,
    created_at TIMESTAMP
);

CREATE TABLE accuracy_history (
    id INTEGER PRIMARY KEY,
    task_type TEXT,
    brief_used BOOLEAN,   -- Claude có dùng brief không
    divergence FLOAT,     -- 0 = giống hệt, 1 = khác hoàn toàn
    trust_at_time FLOAT,  -- trust score lúc đó
    created_at TIMESTAMP
);

CREATE TABLE code_patterns (
    id INTEGER PRIMARY KEY,
    task_type TEXT,
    section_type TEXT,
    style_choices TEXT,    -- JSON
    bindings_used TEXT,    -- JSON array
    theme TEXT,
    created_at TIMESTAMP
);

CREATE TABLE fix_signals (
    id INTEGER PRIMARY KEY,
    task_type TEXT,
    file_path TEXT,
    fix_type TEXT,
    pattern_before TEXT,
    pattern_after TEXT,
    created_at TIMESTAMP
);
```

---

### Phase R3 — Trust Calibration [3-5 ngày]

**Files:**
- `agent/reasoning/calibrator.py` — feedback loop, trust adjustment

**Deliverable:** Trust score tự điều chỉnh dựa trên Claude's actual behavior. Giảm nhanh khi sai, tăng chậm khi đúng.

**Verification:**
```python
# Simulate: Kiwi brief bị Claude ignore 3 lần liên tiếp
for _ in range(3):
    record_brief_ignored(task_type="checkout")

# Trust phải giảm
new_trust = get_trust_baseline("checkout")
assert new_trust < original_trust - 0.2
```

---

### Phase R4 — Active Learning Hooks [1 tuần]

**Files:**
- `agent/reasoning/post_code_hook.py` — hook chạy sau Write/Edit trong themes/
- `agent/reasoning/pattern_extractor.py` — extract style/binding/structure từ code

**Deliverable:** Mỗi lần Claude code → Kiwi tự động cập nhật knowledge base. Không cần explicit "kiwi learn" command.

**Integration với existing hooks:**
```python
# Trong .claude/kiwi/hooks/post_edit.py (đã có)
# Thêm: sau khi scan violations → gọi learning hook

def post_edit_hook(file_path: str, content: str):
    # Existing: scan for violations
    violations = kiwi_scan(file_path)
    
    # NEW: learn from Claude's code
    if is_theme_file(file_path):
        learn_from_code(file_path, content, task=get_current_task())
```

---

### Phase R5 — Brief Quality Improvement [ongoing]

**Không có deadline — chạy liên tục.**

Kiwi brief cải thiện tự nhiên qua:
1. Nhiều context patterns hơn → biết đọc đúng files hơn
2. Accuracy history dài hơn → trust score chính xác hơn
3. Code patterns phong phú hơn → brief chi tiết hơn
4. Fix signals tích lũy → tránh suggest sai

**Metric tracking:**
```python
# Chạy weekly
def weekly_report():
    return {
        'avg_trust_score': compute_avg_trust(last_7_days),
        'brief_usage_rate': briefs_used / briefs_generated,  # Claude tin bao nhiêu %
        'token_savings_estimate': estimate_savings(last_7_days),
        'patterns_learned': count_new_patterns(last_7_days),
        'accuracy_trend': compute_accuracy_trend(last_30_days),
    }
```

---

## Progressive Intelligence — Output thông minh dần theo thời gian

### Vấn đề với plan cũ

Plan cũ: Kiwi brief cùng format mọi lúc, chỉ "đúng hơn" (trust score tăng).
Thực tế cần: Kiwi brief **chi tiết hơn, sâu hơn, thông minh hơn** — không chỉ đúng files mà còn biết WHY, biết tradeoffs, biết edge cases.

### 4 Levels of Brief Intelligence

```
Level 0 (tuần 1): "Task checkout cần đọc files: cart.php, spec.md, bindings.py"
  → Chỉ liệt kê files. Claude vẫn phải tự suy nghĩ approach.

Level 1 (tuần 2-3): "Task checkout: dùng 2-col layout (vì theme này đã dùng ở cart.php),
  data từ wz_cart(), style py-8 md:py-12 (consistent với existing pages)"
  → Có decisions + reasoning. Claude chỉ cần verify rồi execute.

Level 2 (tháng 2+): "Task checkout: 2-col layout. Edge cases: empty cart → redirect,
  payment error → inline message (không modal — theme này không dùng modal ở đâu cả).
  Cảnh báo: spec nói dùng wz_get_shipping_methods() nhưng theme này override bằng
  custom function ở inc/shipping.php line 45. Dùng function đó thay vì spec."
  → Có warnings, contradictions detected, theme-specific overrides.

Level 3 (tháng 4+): "Task checkout: [full brief]. Tương tự lần code checkout cho
  theme-beauty (trust 0.92, Claude không sửa gì). Khác biệt: theme này dùng
  rounded-2xl thay rounded-xl, spacing lớn hơn (py-12 thay py-8).
  Suggest: copy structure từ theme-beauty checkout, chỉ đổi style tokens."
  → Cross-reference past successes, suggest reuse, minimize Claude's work.
```

### Cơ chế level-up (tự động, 0 token)

```python
def determine_brief_level(task_type: str, theme: str) -> int:
    """Kiwi tự biết mình đang ở level nào cho task type này."""
    
    history = query_accuracy_history(task_type)
    
    # Level 0: chưa có data
    if len(history) < 3:
        return 0
    
    # Level 1: có data, accuracy > 60%
    accuracy = sum(h.accepted for h in history) / len(history)
    if accuracy < 0.6 or len(history) < 5:
        return 1
    
    # Level 2: accuracy > 80% + có fix_signals để biết edge cases
    fix_signals = query_fix_signals(task_type)
    if accuracy < 0.8 or len(fix_signals) < 3:
        return 2
    
    # Level 3: accuracy > 90% + có cross-theme data
    cross_theme = query_cross_theme_patterns(task_type)
    if accuracy >= 0.9 and len(cross_theme) >= 2:
        return 3
    
    return 2
```

### Brief content tăng theo level

```python
def generate_brief(task: str, theme_path: str) -> KiwiOutput:
    context = assemble_context(task, theme_path)
    level = determine_brief_level(context['task_type'], context['theme']['name'])
    
    brief = {}
    
    # Level 0: chỉ files
    brief['files_needed'] = context['files_read']
    brief['spec'] = context.get('spec')
    
    if level >= 1:
        # Thêm decisions + reasoning
        brief['suggested_decisions'] = generate_decisions(context)
        brief['style_constraints'] = context['theme']['style_patterns']
        brief['data_bindings'] = context['bindings']
    
    if level >= 2:
        # Thêm edge cases + warnings + contradictions
        brief['edge_cases'] = extract_edge_cases(context)
        brief['warnings'] = detect_contradictions(context)
        brief['theme_overrides'] = find_theme_overrides(context)
    
    if level >= 3:
        # Thêm cross-theme references + reuse suggestions
        brief['similar_successes'] = find_similar_successes(context)
        brief['reuse_suggestion'] = suggest_reuse(context)
        brief['diff_from_reference'] = compute_style_diff(context)
    
    return KiwiOutput(
        content=brief,
        level=level,
        trust_score=compute_trust(context, level),
        recommendation=decide_recommendation(level, context),
    )
```

---

## Cross-Theme Learning — Fix ở theme A giúp theme B

### Vấn đề

Hiện tại mỗi theme là silo riêng. Claude fix checkout ở theme-beauty → Kiwi chỉ nhớ cho theme-beauty. Theme-fashion cũng cần checkout → Claude phải làm lại từ đầu.

### Giải pháp: Abstract patterns tách khỏi theme-specific details

```python
@dataclass
class CrossThemePattern:
    task_type: str              # "checkout_page"
    section_type: str           # "payment_form"
    
    # Universal (áp dụng mọi theme)
    structure: str              # "2-col: form left, summary right"
    data_bindings: list         # ["wz_cart()", "wz_get_shipping_methods()"]
    edge_cases: list            # ["empty_cart_redirect", "payment_error_inline"]
    kiwi_lessons: list          # ["LES-045", "LES-102"]
    
    # Theme-variable (thay đổi theo theme)
    style_tokens: dict          # {"spacing": "VARIES", "radius": "VARIES", "container": "VARIES"}
    
    # Evidence
    themes_applied: list        # ["beauty", "fashion", "tech"]
    success_rate: float         # 0.9 = 9/10 lần Claude không sửa structure
    last_updated: datetime
```

### Learning flow

```python
def learn_cross_theme(task_type: str, theme: str, code: str, was_accepted: bool):
    """Sau mỗi lần Claude code → extract universal vs theme-specific."""
    
    # 1. Extract structure (universal)
    structure = extract_code_structure(code)  # sections, layout, flow
    bindings = extract_data_bindings(code)    # wz_* calls
    
    # 2. Extract style (theme-specific)
    style = extract_style_tokens(code)        # spacing, colors, radius
    
    # 3. Check existing cross-theme pattern
    existing = get_cross_theme_pattern(task_type, section_type=infer_section(code))
    
    if existing:
        # Update: thêm theme vào list, update success rate
        if was_accepted:
            existing.themes_applied.append(theme)
            existing.success_rate = recalculate_success(existing)
        
        # Nếu structure khác → Claude đã chọn approach khác → ghi nhận variant
        if structure != existing.structure:
            save_structure_variant(existing, structure, theme, was_accepted)
    else:
        # Tạo mới
        save_cross_theme_pattern(CrossThemePattern(
            task_type=task_type,
            structure=structure,
            data_bindings=bindings,
            style_tokens={"spacing": "VARIES", "radius": "VARIES"},
            themes_applied=[theme],
            success_rate=1.0 if was_accepted else 0.0,
        ))
```

### Dùng cross-theme trong brief (Level 3)

```python
def suggest_reuse(context: dict) -> dict:
    """Tìm cross-theme pattern phù hợp nhất."""
    
    pattern = get_best_cross_theme_pattern(
        task_type=context['task_type'],
        min_success_rate=0.8,
        min_themes=2,
    )
    
    if not pattern:
        return None
    
    # Tìm theme gần nhất về style
    closest_theme = find_closest_style_theme(
        target_style=context['theme']['style_patterns'],
        candidate_themes=pattern.themes_applied,
    )
    
    return {
        'reference_pattern': pattern,
        'closest_theme': closest_theme,
        'style_diff': compute_style_diff(
            source=load_style(closest_theme),
            target=context['theme']['style_patterns'],
        ),
        'instruction': f"Dùng structure từ {closest_theme}, thay style tokens theo theme hiện tại",
    }
```

### Ví dụ thực tế

```
Kiwi brief cho theme-fashion (checkout page):

"Cross-theme match: checkout đã code thành công ở theme-beauty (trust 0.92)
 và theme-tech (trust 0.88). Structure giống nhau: 2-col, form left, summary right.

 Khác biệt style:
 - beauty: rounded-xl, py-8, shadow-sm, pink accent
 - tech: rounded-lg, py-6, shadow-none, blue accent
 - fashion (target): rounded-2xl, py-10, shadow-md, gold accent

 Suggest: copy structure từ beauty (closest style match),
 thay: rounded-xl→rounded-2xl, py-8→py-10, shadow-sm→shadow-md, pink→gold

 Edge cases đã học (universal):
 - Empty cart → redirect (không show form rỗng)
 - Payment error → inline message dưới button (không modal)
 - Shipping methods loading → skeleton placeholder"
```

Claude nhận brief này → chỉ cần execute style swap → ~2000 tokens thay vì 15000.

---

## Knowledge Distillation — Lưu WHY của Claude, không chỉ WHAT

### Vấn đề

Kiwi hiện chỉ lưu: "Claude đọc file X, code pattern Y, dùng binding Z."
Thiếu: **TẠI SAO** Claude chọn approach đó. WHY là thứ giúp Kiwi quyết định đúng trong tình huống mới.

### Ví dụ

```
WHAT (hiện tại lưu): Claude dùng 2-col layout cho checkout
WHY (cần lưu): Vì theme đã dùng 2-col ở cart page → consistency.
                Nếu theme dùng full-width ở cart → checkout cũng nên full-width.
```

WHAT chỉ giúp khi task giống hệt. WHY giúp khi task tương tự nhưng context khác.

### Cơ chế capture WHY (0 LLM token)

**Source 1: Claude's exploration pattern → infer reasoning**

```python
def infer_reasoning_from_reads(session_reads: list, session_writes: list) -> list[str]:
    """
    Claude đọc files theo thứ tự có ý nghĩa.
    Nếu Claude đọc cart.php TRƯỚC khi code checkout.php → Claude đang reference cart cho consistency.
    """
    reasonings = []
    
    for write in session_writes:
        # Files đọc ngay trước write = context cho decision
        preceding_reads = get_reads_before_write(session_reads, write)
        
        for read in preceding_reads:
            if is_same_theme(read, write):
                # Claude đọc file cùng theme → consistency reference
                reasonings.append({
                    'type': 'consistency_reference',
                    'source': read.file_path,
                    'target': write.file_path,
                    'inference': f"Code {write.file_path} consistent với {read.file_path}",
                })
            elif is_spec_file(read):
                # Claude đọc spec → following spec
                reasonings.append({
                    'type': 'spec_driven',
                    'spec': read.file_path,
                    'target': write.file_path,
                    'inference': f"Code {write.file_path} theo spec {read.file_path}",
                })
    
    return reasonings
```

**Source 2: Claude's fix patterns → infer constraints**

```python
def infer_constraints_from_fixes(fix_signals: list) -> list[str]:
    """
    Khi Claude fix code → có constraint mà code ban đầu vi phạm.
    Fix pattern reveals hidden rules.
    """
    constraints = []
    
    for fix in fix_signals:
        # Phân tích diff → loại constraint
        if 'modal' in fix.pattern_before and 'inline' in fix.pattern_after:
            constraints.append({
                'type': 'ui_preference',
                'rule': 'Không dùng modal cho error messages',
                'evidence': f"Claude đổi modal→inline ở {fix.file_path}",
                'scope': fix.theme or 'universal',
            })
        
        if 'hardcoded' in categorize_fix(fix):
            constraints.append({
                'type': 'code_quality',
                'rule': f"Không hardcode {extract_hardcoded_type(fix)}",
                'evidence': f"Claude fix hardcode ở {fix.file_path}",
                'scope': 'universal',
            })
    
    return constraints
```

**Source 3: Claude's decision reversals → infer tradeoffs**

```python
def infer_tradeoffs_from_reversals(session_log: list) -> list[str]:
    """
    Khi Claude code → xóa → code lại khác → có tradeoff mà approach đầu không đáp ứng.
    """
    tradeoffs = []
    
    # Detect: Write file → Edit same file (significant change) trong cùng session
    writes = [c for c in session_log if c.tool == 'Write']
    edits = [c for c in session_log if c.tool == 'Edit']
    
    for write in writes:
        major_edits = [e for e in edits 
                       if e.file_path == write.file_path 
                       and is_major_change(e)]
        
        if major_edits:
            tradeoffs.append({
                'type': 'approach_reversal',
                'file': write.file_path,
                'first_approach': summarize_structure(write.content),
                'final_approach': summarize_structure(get_final_content(write.file_path)),
                'inference': 'First approach had issues → final approach is preferred',
            })
    
    return tradeoffs
```

### Knowledge Store (SQLite)

```sql
CREATE TABLE knowledge_distilled (
    id INTEGER PRIMARY KEY,
    task_type TEXT,
    knowledge_type TEXT,    -- 'reasoning', 'constraint', 'tradeoff', 'preference'
    rule TEXT,              -- the WHY statement
    evidence TEXT,          -- how we know this
    scope TEXT,             -- 'universal', 'theme:{name}', 'industry:{name}'
    confidence FLOAT,       -- how sure (based on repetition)
    times_confirmed INT,    -- how many times this pattern repeated
    created_at TIMESTAMP,
    last_confirmed TIMESTAMP
);
```

### Dùng distilled knowledge trong brief

```python
def enrich_brief_with_knowledge(brief: dict, context: dict) -> dict:
    """Thêm WHY vào brief — giúp Claude hiểu reasoning đằng sau suggestions."""
    
    knowledge = query_knowledge(
        task_type=context['task_type'],
        scope=[f"theme:{context['theme']['name']}", 'universal'],
        min_confidence=0.7,
    )
    
    # Thêm reasoning cho mỗi decision
    for decision in brief.get('suggested_decisions', []):
        relevant = [k for k in knowledge if k.relates_to(decision)]
        if relevant:
            decision['why'] = relevant[0].rule
            decision['evidence'] = relevant[0].evidence
    
    # Thêm constraints (things to avoid)
    brief['constraints'] = [
        {'rule': k.rule, 'why': k.evidence}
        for k in knowledge
        if k.knowledge_type == 'constraint'
    ]
    
    # Thêm tradeoffs (past mistakes to not repeat)
    brief['avoid'] = [
        {'approach': k.rule, 'why': k.evidence}
        for k in knowledge
        if k.knowledge_type == 'tradeoff'
    ]
    
    return brief
```

### Ví dụ brief với knowledge distillation

```json
{
  "brief": {
    "target": "checkout",
    "suggested_decisions": [
      {
        "decision": "2-col layout",
        "why": "Theme dùng 2-col ở cart.php (line 12-45). Claude đã chọn consistent layout 3/3 lần cho theme này.",
        "evidence": "Inferred từ: Claude đọc cart.php trước khi code checkout ở 3 themes khác nhau"
      }
    ],
    "constraints": [
      {
        "rule": "Không dùng modal cho error messages trong checkout flow",
        "why": "Claude đã fix modal→inline 2 lần (theme-beauty, theme-tech). Lý do inferred: checkout flow cần user thấy error ngay, không bị block bởi modal"
      },
      {
        "rule": "Shipping methods phải dùng inc/shipping.php nếu theme có file đó",
        "why": "Claude đã override spec's wz_get_shipping_methods() bằng custom function 2/2 lần khi theme có custom shipping logic"
      }
    ],
    "avoid": [
      {
        "approach": "Full-width single column checkout",
        "why": "Claude thử approach này ở theme-beauty → xóa → chuyển sang 2-col. Inferred: form quá dài khi single column"
      }
    ]
  },
  "trust_score": 0.88,
  "level": 3
}
```

---

## Vòng lặp thông minh hóa hoàn chỉnh

```
┌─────────────────────────────────────────────────────────────────┐
│  CLAUDE CODES (tốn token, nhưng mỗi lần ít hơn)                │
│                                                                  │
│  Session 1: Claude code checkout (17000 tokens, từ đầu)          │
│  Session 5: Claude code checkout theme khác (8000 tokens,        │
│             Kiwi brief level 1 giúp skip research)               │
│  Session 15: Claude code checkout (4000 tokens,                  │
│              Kiwi brief level 3 + cross-theme reuse)             │
│  Session 30+: Claude chỉ verify brief + execute (2000 tokens)    │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓ (sau mỗi session)
┌─────────────────────────────────────────────────────────────────┐
│  KIWI LEARNS (0 token, Python thuần)                             │
│                                                                  │
│  1. Observe: Claude đọc gì, code gì, fix gì                     │
│  2. Extract WHAT: files, patterns, bindings, structure           │
│  3. Infer WHY: reasoning, constraints, tradeoffs                 │
│  4. Generalize: tách universal vs theme-specific                 │
│  5. Cross-pollinate: pattern từ theme A → áp dụng theme B       │
│  6. Level up: brief intelligence tăng khi data đủ               │
│  7. Calibrate: trust score điều chỉnh theo feedback             │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓ (session tiếp theo)
┌─────────────────────────────────────────────────────────────────┐
│  KIWI OUTPUTS SMARTER BRIEF                                     │
│                                                                  │
│  - Nhiều context hơn (biết đọc đúng files)                      │
│  - Decisions có reasoning (WHY, không chỉ WHAT)                  │
│  - Warnings về contradictions/overrides                          │
│  - Cross-theme suggestions (reuse proven patterns)               │
│  - Edge cases từ past fixes                                      │
│  - Constraints từ past mistakes                                  │
│                                                                  │
│  → Claude nhận brief tốt hơn → code nhanh hơn → ít fix hơn     │
│  → Kiwi có thêm positive signal → brief lần sau còn tốt hơn    │
└─────────────────────────────────────────────────────────────────┘
```

### Metric: Kiwi thông minh = Claude tốn ít token hơn theo thời gian

```
Tokens/task (cùng task type):
Session 1:  ████████████████████ 17000
Session 5:  ████████████         8000  (Kiwi level 1)
Session 10: ████████             5500  (Kiwi level 2)
Session 20: █████                3500  (Kiwi level 2-3)
Session 30: ███                  2000  (Kiwi level 3, cross-theme)
Session 50: ██                   1500  (Kiwi near-autonomous)

Asymptote: ~1000 tokens (Claude chỉ verify + approve)
```

**Kiwi thông minh = đường cong này giảm nhanh hơn.**
Nếu đường cong phẳng (không giảm) → Kiwi không học → cần debug learning pipeline.

---

## Smart Forgetting — Biết quên để không bị nhiễu

### Vấn đề

Kiwi chỉ tích lũy knowledge, không bao giờ quên. Nhưng:
- Blueprint spec thay đổi → pattern cũ trở thành sai
- Theme bị xóa/refactor → cross-theme reference trỏ vào void
- Claude thay đổi approach (vì user yêu cầu) → pattern cũ conflict với pattern mới
- Data bindings thay đổi (wz_* API update) → brief suggest function không còn tồn tại

Nếu không quên → brief chứa noise → trust score giảm → Claude ignore → Kiwi không học thêm → stagnation.

### 3 loại forgetting

```python
def smart_forget():
    """Chạy weekly hoặc khi trust score giảm bất thường."""
    
    # 1. DECAY — knowledge cũ mất dần relevance
    decay_old_patterns()
    
    # 2. INVALIDATE — knowledge bị contradict bởi evidence mới
    invalidate_contradicted()
    
    # 3. PRUNE — knowledge không bao giờ được dùng
    prune_unused()
```

**1. Decay (giảm dần)**

```python
def decay_old_patterns():
    """
    Pattern không được confirm lại trong 30 ngày → confidence giảm 20%.
    Pattern confidence < 0.3 → archive (không xóa, nhưng không dùng trong brief).
    """
    cutoff = now() - timedelta(days=30)
    
    stale = query("""
        SELECT * FROM knowledge_distilled 
        WHERE last_confirmed < ? AND confidence > 0.3
    """, cutoff)
    
    for k in stale:
        k.confidence *= 0.8  # decay 20%
        if k.confidence < 0.3:
            k.status = 'archived'
            log(f"Archived: {k.rule} (no confirmation in 30 days)")
```

**2. Invalidate (vô hiệu hóa)**

```python
def invalidate_contradicted():
    """
    Khi Claude làm ngược lại knowledge đã lưu VÀ kết quả tốt (accepted)
    → knowledge cũ sai → invalidate.
    """
    recent_sessions = get_sessions(last_7_days)
    
    for session in recent_sessions:
        for action in session.actions:
            contradicted = find_contradicting_knowledge(action)
            if contradicted and action.was_accepted:
                # Claude làm ngược lại VÀ user chấp nhận → knowledge cũ sai
                contradicted.status = 'invalidated'
                contradicted.invalidation_reason = f"Claude did opposite at {action.file}, accepted"
                log(f"Invalidated: {contradicted.rule}")
                
                # Tạo knowledge mới thay thế
                save_knowledge(
                    rule=infer_new_rule(action),
                    evidence=f"Replaces invalidated: {contradicted.id}",
                    confidence=0.6,  # start moderate, cần confirm thêm
                )
```

**3. Prune (cắt bỏ)**

```python
def prune_unused():
    """
    Knowledge tồn tại > 60 ngày nhưng chưa bao giờ xuất hiện trong brief
    (vì không match bất kỳ task nào) → xóa.
    """
    unused = query("""
        SELECT * FROM knowledge_distilled
        WHERE times_used_in_brief = 0
        AND created_at < ?
    """, now() - timedelta(days=60))
    
    for k in unused:
        delete_knowledge(k.id)
        log(f"Pruned (never used): {k.rule}")
```

### File freshness check (real-time, mỗi brief)

```python
def check_source_freshness(knowledge: Knowledge, theme_path: str) -> float:
    """
    Trước khi dùng knowledge trong brief → check source files còn tồn tại/unchanged không.
    """
    if knowledge.source_file:
        # File bị xóa → knowledge invalid
        if not exists(knowledge.source_file):
            knowledge.status = 'invalidated'
            return 0.0
        
        # File bị sửa sau khi knowledge được tạo → có thể outdated
        file_mtime = get_mtime(knowledge.source_file)
        if file_mtime > knowledge.last_confirmed:
            return 0.5  # uncertain — include nhưng flag
    
    return 1.0  # fresh
```

---

## Regression Detection — Kiwi biết khi mình đang tệ đi

### Vấn đề

Trust score có thể giảm dần mà Kiwi không nhận ra pattern. Ví dụ:
- Tuần 1-4: trust 0.8 (tốt)
- Tuần 5: trust 0.75 (hơi giảm — có thể noise)
- Tuần 6: trust 0.7 (giảm tiếp)
- Tuần 7: trust 0.6 (regression rõ ràng — nhưng Kiwi không biết TẠI SAO)

Nếu không detect regression sớm → Kiwi tiếp tục output brief kém → Claude ignore nhiều hơn → vòng xoáy đi xuống.

### Regression detector (chạy sau mỗi session)

```python
def detect_regression() -> Optional[RegressionAlert]:
    """
    So sánh performance gần đây vs baseline.
    Nếu giảm đáng kể → alert + diagnose.
    """
    
    # Window: 7 ngày gần nhất vs 7 ngày trước đó
    recent = get_metrics(last_7_days)
    baseline = get_metrics(days_8_to_14)
    
    if not baseline or not recent:
        return None
    
    # Detect: trust giảm > 15%
    trust_drop = baseline.avg_trust - recent.avg_trust
    if trust_drop > 0.15:
        # Diagnose: TẠI SAO giảm?
        diagnosis = diagnose_regression(recent, baseline)
        return RegressionAlert(
            metric='trust_score',
            drop=trust_drop,
            diagnosis=diagnosis,
            suggested_action=diagnosis.fix,
        )
    
    # Detect: brief usage rate giảm > 20%
    usage_drop = baseline.brief_usage_rate - recent.brief_usage_rate
    if usage_drop > 0.2:
        diagnosis = diagnose_usage_drop(recent, baseline)
        return RegressionAlert(
            metric='brief_usage_rate',
            drop=usage_drop,
            diagnosis=diagnosis,
            suggested_action=diagnosis.fix,
        )
    
    return None


def diagnose_regression(recent, baseline) -> Diagnosis:
    """Tìm root cause của regression."""
    
    causes = []
    
    # Cause 1: Spec files thay đổi nhưng knowledge chưa update
    changed_specs = find_changed_specs(last_7_days)
    if changed_specs:
        causes.append({
            'cause': 'spec_drift',
            'detail': f"{len(changed_specs)} spec files changed, knowledge may be stale",
            'fix': 'Run smart_forget() + re-learn from changed specs',
        })
    
    # Cause 2: New task types mà Kiwi chưa có experience
    novel_tasks = find_novel_tasks(recent)
    if novel_tasks:
        causes.append({
            'cause': 'novel_tasks',
            'detail': f"{len(novel_tasks)} new task types with no prior patterns",
            'fix': 'Expected — trust will recover as patterns accumulate',
        })
    
    # Cause 3: Knowledge contradictions (nhiều rules conflict nhau)
    conflicts = find_knowledge_conflicts()
    if conflicts:
        causes.append({
            'cause': 'knowledge_conflicts',
            'detail': f"{len(conflicts)} conflicting rules detected",
            'fix': 'Invalidate older rule in each conflict pair',
        })
    
    # Cause 4: Stale cross-theme patterns (theme bị xóa/refactor)
    stale_refs = find_stale_theme_references()
    if stale_refs:
        causes.append({
            'cause': 'stale_references',
            'detail': f"{len(stale_refs)} cross-theme refs point to deleted/changed files",
            'fix': 'Prune stale references',
        })
    
    return Diagnosis(causes=causes, fix=causes[0]['fix'] if causes else 'Manual investigation needed')
```

### Auto-recovery

```python
def auto_recover(alert: RegressionAlert):
    """
    Khi regression detected → tự động thử fix.
    Nếu fix không giúp sau 3 ngày → escalate to user.
    """
    
    if alert.diagnosis.causes[0]['cause'] == 'spec_drift':
        # Auto-fix: invalidate knowledge liên quan đến changed specs
        smart_forget()
        
    elif alert.diagnosis.causes[0]['cause'] == 'knowledge_conflicts':
        # Auto-fix: invalidate older rule in each pair
        for conflict in find_knowledge_conflicts():
            older = min(conflict, key=lambda k: k.last_confirmed)
            older.status = 'invalidated'
    
    elif alert.diagnosis.causes[0]['cause'] == 'stale_references':
        # Auto-fix: prune
        prune_stale_references()
    
    # Schedule re-check sau 3 ngày
    schedule_recheck(alert, days=3)


def recheck_after_recovery(alert: RegressionAlert):
    """3 ngày sau auto-recovery → check có cải thiện không."""
    current = get_metrics(last_3_days)
    
    if current.avg_trust > alert.pre_recovery_trust + 0.05:
        log("Recovery successful")
    else:
        # Escalate: báo user
        save_alert_for_user(
            f"Kiwi regression detected: {alert.metric} dropped {alert.drop:.0%}. "
            f"Auto-recovery attempted but trust still low. "
            f"Diagnosis: {alert.diagnosis.causes[0]['detail']}. "
            f"May need manual review of knowledge base."
        )
```

### Regression dashboard (trong weekly report)

```python
def weekly_report():
    return {
        # ... existing metrics ...
        
        # NEW: regression indicators
        'trust_trend': compute_trend(metric='trust', window=14),  # ↑ ↓ →
        'regression_alerts': get_active_alerts(),
        'knowledge_health': {
            'total': count_knowledge(),
            'active': count_knowledge(status='active'),
            'archived': count_knowledge(status='archived'),
            'invalidated': count_knowledge(status='invalidated'),
            'conflicts': len(find_knowledge_conflicts()),
        },
        'forgetting_stats': {
            'decayed_this_week': count_decayed(last_7_days),
            'invalidated_this_week': count_invalidated(last_7_days),
            'pruned_this_week': count_pruned(last_7_days),
        },
    }
```

---

## Composability — Hiểu pages liên quan nhau

### Vấn đề

Kiwi học từng page riêng lẻ. Nhưng pages KHÔNG độc lập:
- Checkout phụ thuộc Cart (cùng data: `wz_cart()`)
- Thank-you phụ thuộc Checkout (nhận order data từ checkout flow)
- Product page → Cart → Checkout → Thank-you = 1 flow
- Dashboard pages share sidebar + navigation pattern
- Account pages share auth guard + layout

Nếu Kiwi brief checkout mà không biết cart đã code thế nào → inconsistency.
Nếu Claude fix cart → checkout cũng cần update → Kiwi phải biết propagate.

### Page Dependency Graph

```python
# Static knowledge — từ blueprint specs
PAGE_DEPENDENCIES = {
    'checkout': {
        'depends_on': ['cart'],           # cần cart data
        'feeds_into': ['thank-you', 'order-failed'],  # output flows here
        'shares_layout': ['cart'],         # same 2-col layout expected
        'shares_data': ['cart'],           # wz_cart() used in both
    },
    'thank-you': {
        'depends_on': ['checkout'],
        'shares_data': ['checkout'],       # order data from checkout
    },
    'cart': {
        'depends_on': ['single-product'],  # add-to-cart from product page
        'feeds_into': ['checkout'],
        'shares_data': ['checkout'],
    },
    'dashboard': {
        'shares_layout': ['orders', 'wishlist', 'profile', 'addresses'],
        'shares_component': ['sidebar', 'account-nav'],
    },
    'orders': {
        'depends_on': ['dashboard'],
        'shares_layout': ['dashboard'],
        'shares_component': ['sidebar', 'account-nav'],
    },
    # ... 50 pages mapped
}
```

### Dùng dependency graph trong brief

```python
def enrich_brief_with_dependencies(brief: dict, context: dict) -> dict:
    """Thêm thông tin về related pages vào brief."""
    
    target = context['task_type']  # e.g., "checkout"
    deps = PAGE_DEPENDENCIES.get(target, {})
    
    if not deps:
        return brief
    
    # 1. Pages mà target phụ thuộc → Claude cần biết chúng code thế nào
    brief['dependencies'] = {}
    for dep_page in deps.get('depends_on', []):
        dep_file = find_page_file(dep_page, context['theme']['path'])
        if dep_file:
            brief['dependencies'][dep_page] = {
                'file': dep_file,
                'structure': extract_structure_summary(dep_file),
                'shared_data': deps.get('shares_data', []),
            }
    
    # 2. Pages share layout → phải consistent
    brief['layout_references'] = {}
    for shared_page in deps.get('shares_layout', []):
        shared_file = find_page_file(shared_page, context['theme']['path'])
        if shared_file:
            brief['layout_references'][shared_page] = {
                'file': shared_file,
                'layout_pattern': extract_layout_pattern(shared_file),
            }
    
    # 3. Shared components → phải dùng cùng component
    brief['shared_components'] = {}
    for component in deps.get('shares_component', []):
        comp_file = find_component_file(component, context['theme']['path'])
        if comp_file:
            brief['shared_components'][component] = {
                'file': comp_file,
                'usage_pattern': extract_usage_pattern(comp_file),
            }
    
    # 4. Downstream impact warning
    downstream = deps.get('feeds_into', [])
    if downstream:
        brief['downstream_warning'] = (
            f"Changes here may affect: {', '.join(downstream)}. "
            f"Check consistency after coding."
        )
    
    return brief
```

### Propagation — khi 1 page thay đổi, related pages cần check

```python
def detect_propagation_needed(changed_file: str, theme_path: str) -> list[str]:
    """
    Sau khi Claude sửa 1 page → check: pages nào liên quan cần review?
    Output: list of files cần Claude verify consistency.
    """
    
    changed_page = infer_page_type(changed_file)
    if not changed_page:
        return []
    
    affected = []
    
    # Pages phụ thuộc vào page vừa sửa
    for page, deps in PAGE_DEPENDENCIES.items():
        if changed_page in deps.get('depends_on', []):
            affected.append(page)
        if changed_page in deps.get('shares_layout', []):
            affected.append(page)
        if changed_page in deps.get('shares_data', []):
            affected.append(page)
    
    # Chỉ return pages đã tồn tại trong theme (chưa code thì không cần check)
    existing = [p for p in affected if find_page_file(p, theme_path)]
    
    return existing


def post_code_propagation_check(changed_file: str, theme_path: str):
    """
    Hook: sau khi Claude code xong 1 page → check propagation.
    Nếu có affected pages → thêm vào brief cho session tiếp theo.
    """
    affected = detect_propagation_needed(changed_file, theme_path)
    
    if affected:
        save_propagation_alert({
            'source': changed_file,
            'affected_pages': affected,
            'reason': f"Changes to {infer_page_type(changed_file)} may affect consistency",
            'priority': 'medium',
            'created_at': now(),
        })
```

### Ví dụ brief với composability

```json
{
  "brief": {
    "target": "checkout",
    "dependencies": {
      "cart": {
        "file": "themes/sfvn/templates/cart.php",
        "structure": "2-col: items left, summary right. Uses wz_cart() for data.",
        "shared_data": ["wz_cart()"]
      }
    },
    "layout_references": {
      "cart": {
        "file": "themes/sfvn/templates/cart.php",
        "layout_pattern": "2-col, max-w-7xl, py-8 md:py-12, rounded-xl cards"
      }
    },
    "downstream_warning": "Changes here may affect: thank-you, order-failed. Check consistency after coding.",
    "composability_note": "Checkout MUST use same wz_cart() data structure as cart.php. Order summary section should mirror cart summary (same component, different CTA)."
  }
}
```

### Flow-level learning (cross-page patterns)

```python
@dataclass
class FlowPattern:
    """Pattern cho cả 1 user flow, không chỉ 1 page."""
    flow_name: str              # "purchase_flow", "account_flow"
    pages: list[str]            # ["product", "cart", "checkout", "thank-you"]
    shared_data: dict           # data passed between pages
    shared_components: list     # components reused across flow
    layout_consistency: dict    # layout rules cho cả flow
    success_rate: float         # bao nhiêu lần flow consistent sau generate

def learn_flow_pattern(pages_coded: list[str], theme: str):
    """
    Khi Claude code nhiều pages trong cùng flow → extract flow-level pattern.
    """
    # Detect: pages thuộc cùng flow
    flow = detect_flow(pages_coded)
    if not flow:
        return
    
    # Extract shared patterns across pages in flow
    shared = extract_shared_patterns(pages_coded, theme)
    
    # Save flow pattern
    save_flow_pattern(FlowPattern(
        flow_name=flow,
        pages=pages_coded,
        shared_data=shared['data'],
        shared_components=shared['components'],
        layout_consistency=shared['layout'],
        success_rate=1.0,  # initial
    ))
```

---

## Tổng kết: 3 tầng intelligence

```
Tầng 1: WHAT (agent-code.md)
  - Templates, validators, data bindings
  - Deterministic, 0 token
  - Ceiling: generate code giống nhau mọi lần

Tầng 2: CONTEXT + TRUST (agent-reasoning.md — core)
  - Context assembly, trust scoring, brief generation
  - Passive learning từ Claude sessions
  - 0 token, Python thuần
  - Ceiling: brief đúng files + đúng patterns, nhưng không hiểu WHY

Tầng 3: INTELLIGENCE (agent-reasoning.md — upgrades)
  - Knowledge distillation (WHY, không chỉ WHAT)
  - Cross-theme learning (generalize patterns)
  - Smart forgetting (biết quên để không bị nhiễu)
  - Regression detection (biết khi mình tệ đi)
  - Composability (hiểu pages liên quan nhau)
  - Progressive output (brief thông minh dần theo level)
  
  → Kiwi không chỉ "đúng hơn" mà "khôn hơn" theo thời gian
```

**"Thông minh" vs "Khôn":**
- Thông minh = output đúng (trust score cao)
- Khôn = biết giới hạn mình (trust score thấp khi không chắc), biết quên (smart forgetting), biết mình đang tệ đi (regression detection), biết context rộng hơn (composability)

Kiwi target: KHÔN, không chỉ thông minh.

---

## Kiwi KHÔNG bao giờ làm

1. **KHÔNG gọi LLM API** — mọi reasoning đều Python thuần (regex, file I/O, SQLite queries)
2. **KHÔNG tự sửa code** — chỉ brief cho Claude, Claude quyết định
3. **KHÔNG override Claude** — nếu Claude ignore brief, Kiwi học từ đó (không insist)
4. **KHÔNG tự tạo lessons** — chỉ suggest candidates, user/Claude approve
5. **KHÔNG cache code output** — chỉ cache patterns/decisions (code cụ thể thay đổi theo theme)

---

## Relationship với agent-code.md

| agent-code.md | agent-reasoning.md |
|---------------|-------------------|
| Template engine (render .j2) | Context engine (assemble brief) |
| Validator (check violations) | Trust scorer (check reliability) |
| Data bindings (static mapping) | Learned bindings (from Claude's code) |
| Learning loop (lesson from diffs) | Training loop (patterns from sessions) |
| Generate code | Prepare context cho Claude generate |

**Không conflict. Complementary:**
- `agent-code.md` templates = fallback khi trust cao + task đơn giản
- `agent-reasoning.md` brief = primary path cho mọi task
- Validator từ agent-code.md dùng trong trust scoring (dimension 1)
- Data bindings từ agent-code.md là seed, reasoning layer bổ sung từ Claude's actual usage

---

## Token Savings Projection

| Tuần | Avg Trust | Claude tokens/task | Savings vs baseline |
|------|-----------|-------------------|-------------------|
| 1 | 0.4 | 14000 | 18% (Kiwi mới, Claude tự research) |
| 2 | 0.55 | 10000 | 41% |
| 4 | 0.7 | 7000 | 59% |
| 8 | 0.8 | 5000 | 71% |
| 12+ | 0.85+ | 4000 | 76% |

**Baseline**: 17000 tokens/task (Claude không có Kiwi)

**Break-even**: Tuần 1 — ngay cả trust 0.4 cũng tiết kiệm vì context assembly (0 token) thay thế một phần Claude's file reads.

---

## Success Criteria

| Metric | Target | Meaning |
|--------|--------|---------|
| Brief usage rate | > 70% | Claude tin Kiwi brief 7/10 lần |
| Trust accuracy | > 85% | Khi Kiwi nói "trust" → Claude không cần re-research 85%+ |
| Token savings | > 60% | So với Claude không có Kiwi |
| Patterns learned/week | > 20 | Kiwi đang học, không stagnate |
| False confidence rate | < 10% | Kiwi nói "trust" nhưng brief sai < 10% |

**Khi nào Kiwi "thông minh":**
- Tuần 1-2: Kiwi biết đọc đúng files (context assembly works)
- Tháng 1: Kiwi biết task nào cần files nào (patterns learned)
- Tháng 2: Kiwi brief đủ tốt để Claude skip research 70% tasks
- Tháng 3+: Kiwi trust score calibrated, Claude gần như chỉ execute
- Tháng 6+: Kiwi + template engine có thể handle standard pages, Claude chỉ cho edge cases

---

## Upgrades — Giải quyết gaps còn lại

### Upgrade 1: Phase R0 — Session Capture (PREREQUISITE)

Toàn bộ learning pipeline phụ thuộc vào session log. Cần infrastructure capture trước.

**Chi tiết:** Xem [agent-reasoning-R0.md](agent-reasoning-R0.md)

---

### Upgrade 2: Graduated Autonomy — Output evolves theo trust

Plan cũ: Kiwi luôn output brief → Claude luôn code.
Plan mới: Khi trust tăng, Kiwi output **nhiều hơn brief** — tiến tới draft code.

```
Trust < 0.6   → brief only (Claude tự code)
Trust 0.6-0.85 → brief + code skeleton
Trust 0.85-0.95 → draft code (Claude review + adjust)
Trust > 0.95  → ready-to-apply (Claude approve)
```

**Chi tiết:** Xem [agent-reasoning-R6.md](agent-reasoning-R6.md)

---

### Upgrade 3: Output Versioning — Đo "thông minh dần" bằng số

Thêm table đo chất lượng output theo thời gian. Nếu curve flat → Kiwi không học → debug.

**Chi tiết:** Xem [agent-reasoning-R7.md](agent-reasoning-R7.md)

---

### Upgrade 4: Replace compute_divergence/alignment

Bỏ semantic comparison (cần LLM). Thay bằng 3 binary signals đo được bằng Python thuần:

```python
brief_ignored = len(re_reads) > len(brief.source_files) * 0.5
multiple_rewrites = count_edits_same_file > 2
kiwi_violations_after = scan_found_criticals
```

Đã integrate vào Phase R3 (Trust Calibration).

---

### Upgrade 5: Adjusted Timeline (realistic)

| Tuần | Avg Trust | Savings | Note |
|------|-----------|---------|------|
| 1-2 | 0.4 | 15-20% | Context assembly chỉ giúp file reads |
| 4 | 0.55 | 30-40% | Common tasks (fix CSS, add component) |
| 8 | 0.65 | 40-50% | Level 1-2 briefs cho repeated tasks |
| 16 | 0.75 | 55-65% | Cross-theme bắt đầu kick in |
| 24+ | 0.85 | 70-80% | Level 3 + graduated autonomy |

Page-level tasks (checkout, cart) cần 6-12 tháng để đạt trust cao (chỉ code 1 lần/theme).
Micro-tasks (fix CSS, add component) đạt trust cao trong 4-8 tuần.

---

## Phase Files — Danh sách đầy đủ

| File | Phase | Nội dung | Timeline |
|------|-------|----------|----------|
| [agent-reasoning-R0.md](agent-reasoning-R0.md) | R0 | Session Capture Infrastructure | 3 ngày |
| [agent-reasoning-R1.md](agent-reasoning-R1.md) | R1 | Context Assembly + Trust Score | 1 tuần |
| [agent-reasoning-R2.md](agent-reasoning-R2.md) | R2 | Passive Learning Engine | 1 tuần |
| [agent-reasoning-R3.md](agent-reasoning-R3.md) | R3 | Trust Calibration (binary signals) | 3-5 ngày |
| [agent-reasoning-R4.md](agent-reasoning-R4.md) | R4 | Active Learning Hooks | 1 tuần |
| [agent-reasoning-R5.md](agent-reasoning-R5.md) | R5 | Brief Quality + Smart Forgetting | ongoing |
| [agent-reasoning-R6.md](agent-reasoning-R6.md) | R6 | Graduated Autonomy | 1 tuần |
| [agent-reasoning-R7.md](agent-reasoning-R7.md) | R7 | Output Versioning + Metrics | 3 ngày |

**Tổng timeline:** ~6 tuần cho R0-R7. Sau đó R5 chạy liên tục (self-improving).

**Dependency graph:**
```
R0 (Session Capture) → R2 (Passive Learning) → R3 (Trust Calibration)
                     ↘ R4 (Active Learning)  ↗
R1 (Context Assembly) → R5 (Brief Quality) → R6 (Graduated Autonomy)
                                            → R7 (Output Versioning)
```
