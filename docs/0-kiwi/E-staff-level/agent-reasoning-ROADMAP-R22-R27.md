# Phase R22-R27 — From Mid-Level to Staff: System-Level Intelligence

## Overview

R0-R21 biến Kiwi từ "pattern matcher" thành "near-senior dev tự học từ senior".
R22-R27 nâng lên "staff-level" — hiểu hệ thống, không chỉ files.

```
R0-R6:   Foundation (code generation)
R7-R15:  Self-improvement (metrics, thinking, prediction, teaching)
R16-R21: Senior-level (decompose, reason, create, learn from Claude)
R22-R27: Staff-level (system thinking, architecture, collaboration)
```

---

## R22 — Real-time Learning [3 ngày]

**Mục đích:** Học ngay trong session, không đợi post-session pipeline.

**Vấn đề hiện tại:** Kiwi learn sau khi session kết thúc (R2 learner chạy post-session). Nếu Claude fix bug ở file A, Kiwi không biết cho đến session sau — dù file B cùng session có cùng bug.

**Core idea:**
- Mỗi Write/Edit trong session → immediate pattern extraction
- Nếu Claude fix pattern X ở file A → Kiwi warn ngay khi Claude mở file B có cùng pattern
- "Hot knowledge" — valid chỉ trong session hiện tại, merge vào long-term sau

**Modules:**
```
agent/reasoning/
├── realtime_learner.py    # immediate pattern extraction per Write/Edit
├── session_knowledge.py   # hot knowledge store (in-memory, session-scoped)
└── test_r22.py
```

**Flow:**
```
Claude edits file A (fix: $product->price → $product['price'])
  → realtime_learner detects: accessor pattern changed
  → session_knowledge stores: {pattern: "product_accessor", fix: "arrow_to_bracket"}
  
Claude opens file B (has $product->name)
  → kiwi_reason checks session_knowledge
  → injects warning: "Same accessor pattern found — fix applied in file A this session"
```

**Key constraint:** Must be < 5ms overhead per Write/Edit. In-memory dict, no DB writes during session.

---

## R23 — Code Review Mode [1 tuần]

**Mục đích:** Kiwi review code Claude viết — phát hiện inconsistency, performance issues, missing patterns TRƯỚC khi commit.

**Vấn đề hiện tại:** Kiwi chỉ check CRITICAL violations (post-edit hook). Không review logic, consistency, performance.

**Core idea:**
- Sau Claude hoàn thành task → Kiwi review toàn bộ changes
- Check: style consistency với theme, missing error handling, performance anti-patterns
- Check: cross-file consistency (nếu sửa function signature → callers updated?)
- Output: review comments (approve / request changes / suggest improvements)

**Modules:**
```
agent/reasoning/
├── reviewer.py            # orchestrate review pipeline
├── consistency_checker.py # cross-file consistency
├── perf_checker.py        # performance anti-patterns
├── style_reviewer.py      # style consistency with theme patterns
└── test_r23.py
```

**Review levels:**
```
Level 1 (always): CRITICAL violations (existing Kiwi scan)
Level 2 (trust > 0.7): Style consistency + naming conventions
Level 3 (trust > 0.85): Performance patterns + cross-file impact
Level 4 (trust > 0.95): Architecture alignment + suggest refactoring
```

**Output format:**
```
KIWI REVIEW (3 findings):
  [WARN] templates/cart.php:45 — inconsistent spacing (py-6 here, py-8 everywhere else)
  [PERF] templates/archive.php:23 — N+1 query in loop (use wz_bulk_get instead)
  [STYLE] inc/helpers.php:12 — function name get_data() doesn't match wz_ prefix convention
```

**Token cost:** 0 (deterministic checks from learned patterns). LLM only for ambiguous cases.

---

## R24 — Architecture Reasoning [1 tuần]

**Mục đích:** Hiểu relationships giữa modules. Warn khi new code vi phạm architecture boundaries.

**Core idea:**
- Build dependency graph từ code (imports, function calls, hooks)
- Detect: circular dependencies, layer violations, coupling increase
- Suggest: where new code should live based on existing architecture
- Warn: "This function in templates/ calls directly into inc/admin/ — layer violation"

**Modules:**
```
agent/reasoning/
├── arch_graph.py          # build + maintain dependency graph
├── boundary_checker.py    # detect layer/boundary violations
├── placement_advisor.py   # suggest where new code belongs
└── test_r24.py
```

**Architecture rules (learned from codebase):**
```python
LAYER_RULES = {
    'templates/': ['can call inc/', 'can call template-parts/', 'CANNOT call admin/'],
    'inc/': ['can call shared/', 'CANNOT call templates/'],
    'admin/': ['can call inc/', 'can call shared/', 'CANNOT call templates/'],
    'template-parts/': ['can call inc/', 'CANNOT call admin/'],
}
```

**Auto-learning:** Kiwi infer rules từ existing code (what calls what). Nếu 95% files in templates/ never import from admin/ → that's a boundary.

---

## R25 — Test Strategy [3 ngày]

**Mục đích:** Từ code changes → suggest test cases. Biết edge cases nào hay bị miss.

**Core idea:**
- Claude writes/edits code → Kiwi analyze: what could break?
- Suggest test cases based on: data types involved, branching logic, external dependencies
- Prioritize: tests that would have caught past bugs (from failure history R20)

**Modules:**
```
agent/reasoning/
├── test_strategist.py     # analyze changes → suggest tests
├── coverage_analyzer.py   # what's tested vs what's not
├── past_failures.py       # tests that would have caught historical bugs
└── test_r25.py
```

**Output format:**
```
KIWI TEST SUGGESTIONS for checkout.php changes:
  [HIGH] Test: empty cart → should redirect (edge case missed in 2 past sessions)
  [MED]  Test: shipping = 0 → total should equal subtotal
  [LOW]  Test: coupon code with special characters → should sanitize
```

**Learning:** Track which suggested tests actually caught bugs → increase priority for similar suggestions.

---

## R26 — Multi-Agent Collaboration [1 tuần]

**Mục đích:** Nhiều Kiwi "specialists" chạy parallel, merge insights.

**Core idea:**
- Thay vì 1 Kiwi biết mọi thứ → 4 specialists focus vào domain riêng:
  - **Security-Kiwi:** XSS, injection, auth, CSRF
  - **Performance-Kiwi:** N+1, caching, lazy loading, bundle size
  - **UI-Kiwi:** responsive, accessibility, dark mode, consistency
  - **Architecture-Kiwi:** boundaries, coupling, naming, patterns
- Mỗi specialist có own trust scores, own learned patterns
- Orchestrator merge results, resolve conflicts (security > performance > UI > architecture)

**Modules:**
```
agent/reasoning/
├── orchestrator.py        # dispatch to specialists, merge results
├── specialists/
│   ├── security.py
│   ├── performance.py
│   ├── ui.py
│   └── architecture.py
├── conflict_resolver.py   # when specialists disagree
└── test_r26.py
```

**Parallel execution:**
```
kiwi_reason(task, theme)
  → [parallel]
      security_kiwi.check(code)    → 2 findings
      performance_kiwi.check(code) → 1 finding
      ui_kiwi.check(code)          → 3 findings
      arch_kiwi.check(code)        → 0 findings
  → merge: 6 findings, prioritized by severity
  → output: unified brief with specialist insights
```

**Value:** Deeper expertise per domain. Security-Kiwi knows 200+ security patterns deeply vs general Kiwi knowing 726 patterns shallowly.

---

## R27 — Intent Prediction [3 ngày]

**Mục đích:** Dự đoán user muốn gì TRƯỚC khi họ type. Pre-compute everything.

**Core idea:**
- Signals: file đang mở, git diff, time of day, recent session pattern
- Predict: "user sắp fix responsive bug" (vì đang mở mobile CSS + last commit was responsive fix)
- Pre-compute: brief + skeleton + relevant lessons → ready khi user asks
- If prediction wrong → discard silently (no cost to user)

**Modules:**
```
agent/reasoning/
├── intent_predictor.py    # predict next task from signals
├── signal_collector.py    # collect IDE signals (open files, cursor, git)
├── precompute_engine.py   # background compute for predicted tasks
└── test_r27.py
```

**Prediction signals:**
```python
SIGNALS = {
    'open_file': 0.3,        # file type/path hints at task
    'recent_git_diff': 0.25, # what was just changed
    'time_pattern': 0.15,    # user tends to do X at this time
    'session_sequence': 0.2, # after task A, usually does task B
    'cursor_position': 0.1,  # where in file = what section
}
```

**Accuracy target:** 60%+ prediction accuracy. Even 60% means 60% of tasks get instant response.

**Latency impact:** Predicted tasks → 0ms (already computed). Unpredicted → normal ~80ms. Average: ~30ms.

---

## Evolution Summary (Complete R0-R27)

| Phase | Kiwi level | Token split (Kiwi/Claude) |
|-------|-----------|--------------------------|
| R0-R6 | Junior dev | 30/70 |
| R7-R15 | Mid-level dev | 60/40 |
| R16-R21 | Senior dev | 85/15 |
| R22-R27 | Staff dev | 92/8 |

**After R27:** Kiwi handles 92% of work. Claude's remaining 8%:
- Truly novel business requirements (first-time features with no precedent)
- High-stakes architecture decisions (new system design)
- Stakeholder communication (requirements negotiation)
- Creative UX innovation (not variation of existing patterns)

---

## Token Trajectory (Complete)

```
R0:   10,000 tok/session (baseline)
R6:    3,000-5,000 (code generation)
R13:   1,500-2,500 (autonomous fix loop)
R21:   500-1,500 (learning from senior)
R27:   200-800 (intent prediction + specialists)
```

**Asymptote:** ~300 tokens/session for familiar tasks (Claude just approves). ~2,000 for novel tasks.

---

## Priority & Timeline

| Phase | Value | Effort | When |
|-------|-------|--------|------|
| R22 Real-time Learning | High | 3 days | After R21 |
| R23 Code Review Mode | Very High | 1 week | After R22 |
| R24 Architecture Reasoning | High | 1 week | After R23 |
| R25 Test Strategy | Medium-High | 3 days | After R24 |
| R26 Multi-Agent Collaboration | Medium | 1 week | After R25 |
| R27 Intent Prediction | High | 3 days | After R26 |

**Total R22-R27:** ~5 weeks.

---

## True Ceiling (After R27)

Kiwi sau R27 vẫn KHÔNG thể:
- Invent new algorithms or data structures
- Understand business politics or organizational dynamics
- Make ethical/legal judgments about features
- Handle ambiguity that requires human empathy

Đây không phải technical limitations — đây là **scope boundaries**. Kiwi là code generation + review engine, không phải general AI. Nó optimize 92% of coding work để Claude + human focus vào 8% that requires true intelligence.

**Practical ceiling:** Kiwi plateaus khi:
1. All common task_types have trust > 0.9 (nothing left to learn)
2. Novel tasks drop below 5% of total (codebase is mature)
3. Prediction accuracy hits 80%+ (diminishing returns on more signals)

At that point, Kiwi is "done learning" for this project. Value shifts to cross-project transfer (R12) — applying everything learned here to new projects.