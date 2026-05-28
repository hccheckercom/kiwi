# Kiwi Reasoning Roadmap — R9 to R15

## Overview

```
R0-R6: Foundation (done) — observe, learn, calibrate, act, self-improve, generate
R7:    Metrics (planned)  — đo lường intelligence score
R8:    Thinking (planned) — selective LLM reasoning cho edge cases
R9-R15: Advanced (future) — self-reflection, routing, prediction, cross-project, autonomy
```

---

## R9 — Reflective Learning [1 tuần]

**Mục đích:** Think results (R8) feed back vào trust calibration. Kiwi học từ chính decisions của mình.

**Core idea:**
- Sau mỗi think() call → track outcome (decision dẫn đến session thành công hay thất bại?)
- Nếu think decision → positive calibration → tăng confidence cho trigger đó
- Nếu think decision → negative calibration → giảm confidence, có thể disable trigger
- Over time: Kiwi biết khi nào nên think và khi nào deterministic đủ tốt

**Modules:**
```
agent/reasoning/
├── think_evaluator.py     # evaluate think outcomes post-session
├── think_calibrator.py    # adjust think trigger thresholds
└── test_r9.py
```

**Key metrics:**
- Think accuracy: % decisions dẫn đến positive outcome
- Think ROI: token cost vs quality improvement
- Trigger precision: % times should_think() đúng

**Dependencies:** R8 (thinking), R3 (calibration), R7 (metrics)

---

## R10 — Multi-Model Routing [1 tuần]

**Mục đích:** Chọn model phù hợp cho từng think call. Haiku cho simple, Sonnet cho complex.

**Core idea:**
- Router phân loại think request theo complexity
- Simple (pattern choice, style inference) → Haiku (~$0.0002)
- Complex (architecture decision, multi-file refactor plan) → Sonnet (~$0.003)
- Critical (security review, data migration) → Opus (~$0.015)
- Budget tracking: daily/weekly cap per model tier

**Modules:**
```
agent/reasoning/
├── model_router.py        # classify complexity → select model
├── budget_tracker.py      # track spend per model, enforce caps
└── test_r10.py
```

**Routing signals:**
- Token count of context (more context → needs bigger model)
- Number of files involved (multi-file → Sonnet+)
- Task type risk level (security → Opus)
- Historical accuracy per model for this trigger type

**Dependencies:** R8 (thinking), R9 (think evaluation for routing feedback)

---

## R11 — Predictive Prefetch [3 ngày]

**Mục đích:** Dự đoán task tiếp theo, pre-compute brief + skeleton. Latency gần 0 cho predicted tasks.

**Core idea:**
- Từ session patterns: sau home_page thường là product_page (70% probability)
- Khi Claude xong home_page → background compute brief cho product_page
- Khi Claude hỏi product_page → instant response (đã compute sẵn)
- Cache invalidation: nếu prediction sai → discard, không waste

**Modules:**
```
agent/reasoning/
├── predictor.py           # predict next task from session history
├── prefetch_cache.py      # store pre-computed briefs
└── test_r11.py
```

**Prediction model (deterministic, 0 token):**
- Markov chain từ `context_patterns` table
- P(next_task | current_task, theme) → top 2 predictions
- Only prefetch if P > 0.6 (confident enough)

**Dependencies:** R0 (session data), R1 (context assembly), R6 (code generation)

---

## R12 — Cross-Project Transfer [1 tuần]

**Mục đích:** Học từ project A, apply cho project B. Kiwi trở thành "platform expert" thay vì chỉ "theme expert".

**Core idea:**
- Hiện tại: cross-theme transfer (cùng project, khác theme)
- R12: cross-project transfer (khác project hoàn toàn)
- Shared knowledge: security patterns, API conventions, performance tricks
- Project-specific knowledge: style tokens, business logic, domain terms

**Modules:**
```
agent/reasoning/
├── project_registry.py    # register projects + their domains
├── knowledge_router.py    # decide what transfers vs what's project-specific
├── shared_knowledge.py    # global patterns applicable everywhere
└── test_r12.py
```

**Transfer rules:**
- Security patterns → always transfer (XSS, injection, auth)
- API conventions → transfer within same platform (wp→wp, nextjs→nextjs)
- Style tokens → NEVER transfer (each project has own design)
- Performance patterns → transfer if same stack

**Schema addition:**
```sql
CREATE TABLE project_knowledge (
    id INTEGER PRIMARY KEY,
    project TEXT NOT NULL,
    knowledge_type TEXT NOT NULL,  -- "security", "api", "performance", "style"
    transferable INTEGER DEFAULT 0,
    pattern TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    UNIQUE(project, knowledge_type, pattern)
);
```

**Dependencies:** R2 (learner), R5 (cross-theme), R8 (thinking for ambiguous transfers)

---

## R13 — Autonomous Fix Loop [3 ngày]

**Mục đích:** Khi code gen fail quality check → think → fix → re-check → loop. Không cần Claude intervention.

**Core idea:**
- Hiện tại (R6): quality fail → fallback to brief_only (give up)
- R8: quality fail → think once → fix or give up
- R13: quality fail → think → fix → re-check → think again if needed → loop (max 3 iterations)
- Self-healing code generation

**Modules:**
```
agent/reasoning/
├── fix_loop.py            # orchestrate fix → check → fix cycle
├── fix_strategies.py      # known fix patterns (no LLM needed for common fixes)
└── test_r13.py
```

**Fix strategies (deterministic, 0 token):**
- Missing `wezone_is_active` guard → inject at top
- `$product->key` → replace with `$product['key']`
- BEM class `__x--y` → remove or replace with Tailwind
- WooCommerce ref `wc_*` → replace with `wz_*` equivalent

**LLM fallback:** Only if deterministic fix doesn't resolve → think() for creative fix

**Loop budget:** Max 3 iterations. If still failing after 3 → fallback to brief_only + log failure for learning.

**Dependencies:** R6 (code generation), R8 (thinking), code_drafter.check_code_quality()

---

## R14 — Spec Synthesis [1 tuần]

**Mục đích:** Từ nhiều sessions cùng task_type → tự tổng hợp spec. Kiwi viết documentation cho chính nó.

**Core idea:**
- Sau 10+ sessions cho `checkout_page` → Kiwi biết:
  - Luôn cần files: cart.php, shipping.php, payment.php
  - Luôn dùng components: wz_cart_summary, wz_payment_form
  - Layout: always 2-col (main + sidebar)
  - Common mistakes: missing shipping validation, wrong total calculation
- Synthesize thành spec document → replace manual blueprint specs over time

**Modules:**
```
agent/reasoning/
├── spec_synthesizer.py    # aggregate patterns → generate spec
├── spec_validator.py      # validate synthesized spec against real outcomes
├── spec_store.py          # store + version synthesized specs
└── test_r14.py
```

**Synthesis triggers:**
- 10+ sessions for same task_type
- 80%+ consistency in files_needed, bindings, layout
- Trust baseline > 0.7 for that task_type

**Output:** Markdown spec stored in DB, versioned. Used by context_assembler as fallback when blueprint spec missing.

**Dependencies:** R2 (learner patterns), R3 (trust), R7 (metrics for validation)

---

## R15 — Teaching Mode [3 ngày]

**Mục đích:** Kiwi phát hiện Claude lặp sai lầm → chủ động inject warning + giải thích tại sao.

**Core idea:**
- Track: Claude made same mistake 3+ times (same violation type, same task_type)
- Instead of just warning "don't do X" → explain "don't do X because Y happened in theme Z, causing bug W"
- Contextual teaching: only teach when relevant (about to make the same mistake)
- Fade out: once Claude stops making the mistake → stop teaching (don't nag)

**Modules:**
```
agent/reasoning/
├── teacher.py             # detect repeated mistakes, generate teaching
├── mistake_tracker.py     # track mistake patterns per task_type
└── test_r15.py
```

**Teaching format:**
```
⚠️ KIWI TEACHING: Trong 3 sessions gần đây cho checkout_page, 
$product->price được dùng thay vì $product['price']. 
Lần cuối (theme funilux) gây fatal error trên production.
→ Dùng: $product['price']
```

**Fade logic:**
- Mistake seen 3+ times → start teaching
- Claude avoids mistake 5 consecutive times → stop teaching
- If mistake returns → resume teaching immediately

**Dependencies:** R0 (session log), R3 (calibration signals), R4 (proactive warnings)

---

## Priority Matrix

| Phase | Value | Effort | Priority |
|-------|-------|--------|----------|
| R9 Reflective Learning | High (self-improving thinks) | 1 week | P1 |
| R11 Predictive Prefetch | High (latency → 0) | 3 days | P1 |
| R13 Autonomous Fix Loop | High (less fallback) | 3 days | P2 |
| R15 Teaching Mode | Medium (prevent repeated mistakes) | 3 days | P2 |
| R10 Multi-Model Routing | Medium (cost optimization) | 1 week | P3 |
| R12 Cross-Project Transfer | High (platform expert) | 1 week | P3 |
| R14 Spec Synthesis | Medium (auto-documentation) | 1 week | P4 |

**Recommended order:** R9 → R11 → R13 → R15 → R10 → R12 → R14

---

## Ceiling Analysis

| Phase | Kiwi becomes... |
|-------|----------------|
| R0-R6 | Theme coding assistant (observe + generate) |
| R7-R8 | Self-aware assistant (measure + think) |
| R9-R11 | Predictive assistant (learn from thinks + prefetch) |
| R12-R13 | Platform expert (cross-project + self-healing) |
| R14-R15 | Autonomous teacher (synthesize specs + teach Claude) |

**Diminishing returns after R13** cho WordPress themes specifically. R14-R15 shine khi có nhiều projects + nhiều developers dùng Kiwi.

**True ceiling:** Kiwi không thể thay thế Claude hoàn toàn — nó optimize Claude's workflow, không replace Claude's reasoning. Asymptote: ~500 tokens/session cho familiar tasks, ~2000 tokens cho novel tasks.
