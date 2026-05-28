# B2 — Autonomous Fix Loop / R13 (3 days)

## Mục tiêu
Khi code gen fail quality check → think → fix → re-check → loop (max 3 iterations). Self-healing code generation không cần Claude intervention.

---

## Current State (pre-B2)

| Component | Status |
|-----------|--------|
| R6 Code Generation | Done — `agent/reasoning/code_drafter.py` generates code |
| R8 Thinking | Done — `agent/reasoning/thinker.py` think() cho edge cases |
| Quality checker | Done — `code_drafter.check_code_quality()` returns **bool only** (True/False) |
| Current fallback | quality fail → `brief_only` in `autonomy.py:96-100` (give up) |
| Deterministic fixes | **Partial** — `scanner/fixer.py` has replace/template/wrap/delete types, not integrated with gen loop |

### Gap analysis
- `code_drafter.py`: `check_code_quality()` returns bool — no violation details (which pattern, where, what fix). Fix loop needs structured output.
- `autonomy.py:96-100`: the actual fallback point — sets `output.level = "brief_only"`, clears code. This is where fix loop must integrate.
- `scanner/fixer.py`: has fix infrastructure (FixResult dataclass, rollback, 5 fix types) but not called during generation.
- No loop orchestrator connecting: generate → check → fix → re-check.
- `think_evaluator.py` referenced in B1 does NOT exist yet — B1 dependency is soft (logging only, can stub).

---

## Tasks

### T1: Upgrade check_code_quality() to return structured violations (0.5 day)
- Current: `check_code_quality(code) → bool` — no info on WHAT failed or WHERE
- New: `check_code_quality(code) → QualityResult(passed: bool, violations: list[QualityViolation])`
- `QualityViolation`: `pattern_name`, `match_text`, `line_number`, `fix_type` (maps to strategy)
- Backward-compatible: callers using `if not check_code_quality(code)` still work via `__bool__`
- Reuse existing `critical_patterns` list, enrich with fix metadata

### T2: Fix Strategies Registry (0.5 day)
- Lightweight wrappers that operate on **in-memory code strings** (NOT files on disk)
- Distinct from `scanner/fixer.py` which operates on **files** with rollback/git integration
- Catalog deterministic fixes (0 token cost):
  - Missing `wezone_is_active` guard → inject at top of file
  - `$product->key` → replace with `$product['key']`
  - BEM class `__x--y` → remove or replace with Tailwind equivalent
  - WooCommerce ref `wc_*` → replace with `wz_*`
  - Missing nonce check → inject `wp_verify_nonce()` block
  - Hardcoded hex color → replace with CSS variable
- Interface: `FixStrategy.can_fix(violation: QualityViolation) → bool`, `FixStrategy.apply(code: str, violation) → str`
- Reuse patterns from `scanner/fixer.py` where applicable, but NO file I/O

### T3: Fix Loop Orchestrator (1 day)
- Orchestrate: generate → check → fix → re-check cycle
- Max 3 iterations (configurable)
- Iteration 1: try deterministic fixes only (0 token)
- Iteration 2: if still failing → think() for creative fix (token cost)
- Iteration 3: last attempt with think() + broader context
- After 3 fails → fallback to brief_only + log failure for learning
- Track: iterations_used, fixes_applied, final_outcome

### T4: Integration into autonomy.py (0.5 day)
- Integration point: `autonomy.py:96-100` — currently:
  ```python
  from .code_drafter import check_code_quality
  if not check_code_quality(output.code):
      output.level = "brief_only"
      output.code = None
      output.confidence = 0.0
  ```
- Replace with: `if not check_code_quality(output.code): output = fix_loop(output)`
- Preserve existing behavior when fix_loop disabled (feature flag `FIX_LOOP_ENABLED`)
- Log each iteration: violation_count_before, fixes_attempted, violation_count_after

### T5: Tests + Metrics (0.5 day)
- Unit tests per fix strategy (input violation → expected output)
- Integration test: generate bad code → fix loop → verify clean output
- Metrics: fix_loop_success_rate, avg_iterations, token_cost_per_fix
- Edge case: fix introduces new violation → detect and revert that fix

---

## Output Structure

```
agent/reasoning/
├── fix_loop.py             # T3: orchestrate fix → check → fix cycle
├── fix_strategies.py       # T2: deterministic fix patterns (0 token, in-memory)
├── quality_result.py       # T1: QualityResult + QualityViolation dataclasses
└── test_r13.py             # T5: unit + integration tests

Modified files:
├── code_drafter.py         # T1: check_code_quality() returns QualityResult
└── autonomy.py:96-100      # T4: wire fix_loop into fallback path
```

### Relationship to scanner/fixer.py
- `scanner/fixer.py` = **file-level** fixes with git rollback, disk I/O, FixResult dataclass
- `fix_strategies.py` = **string-level** fixes during code generation (in-memory, no I/O)
- Both share the same fix PATTERNS (regex, replacements) but different execution contexts
- Future: extract shared pattern definitions into `scanner/fix_patterns.py` (not in scope for B2)

---

## Dependencies

| Dependency | From | What's needed |
|------------|------|---------------|
| R6 Code Gen | `agent/reasoning/code_drafter.py` | generate_draft() + check_code_quality() |
| R6 Autonomy | `agent/reasoning/autonomy.py:96-100` | Integration point (brief_only fallback) |
| R8 Thinking | `agent/reasoning/thinker.py` | think() for creative fixes (iteration 2-3) |
| Scanner fixer | `scanner/fixer.py` | Reuse fix PATTERNS (regex/replacements), NOT the file-level executor |
| B1 Learner | `agent/reasoning/learner.py` | Log fix outcomes for session learning (soft dep — stub if B1 not ready) |

**Note:** B1 plan references `think_evaluator.py` which does NOT exist. The actual learning entry point is `learner.py` (session-based pattern extraction). Fix loop logging should write to the same SQLite tables that `learner.py` reads.

---

## Done Criteria

- [ ] `check_code_quality()` returns `QualityResult` with structured violations (T1)
- [ ] Backward-compatible: `if not check_code_quality(code)` still works via `__bool__` (T1)
- [ ] 6+ deterministic fix strategies registered and tested — operate on strings, no file I/O (T2)
- [ ] Fix loop runs max 3 iterations, respects budget (T3)
- [ ] Iteration 1 uses 0 tokens (deterministic only) (T3)
- [ ] Iteration 2-3 use think() only if deterministic fails (T3)
- [ ] Fix loop success rate > 60% (vs current 0% — always fallback) (T3)
- [ ] `autonomy.py:96-100` wired to fix_loop instead of immediate brief_only (T4)
- [ ] No regression: code that passes quality check on first try → no loop triggered (T4)
- [ ] Failure logging writes to SQLite for `learner.py` consumption (T4)
- [ ] Feature flag: `FIX_LOOP_ENABLED` (default True, can disable) (T4)
- [ ] All existing `test_r6.py` + `test_r6_qa.py` tests still pass (T5)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Fix introduces new violation | Infinite loop | Track violation count per iteration; if increases → revert + stop |
| Think() fix is wrong | Wasted tokens | Validate think output before applying; reject if quality worse |
| 3 iterations too slow | Latency | Iteration 1 is instant (deterministic); only 2-3 cost time |
| Fix strategies too rigid | Low success rate | Start with high-confidence patterns; expand based on failure logs |
| QualityResult breaks callers | Regression in autonomy.py, tests | `__bool__` method ensures backward compat; run test_r6 + test_r6_qa |
| Duplicate logic with scanner/fixer.py | Maintenance burden | Share pattern definitions, keep execution contexts separate (string vs file) |
