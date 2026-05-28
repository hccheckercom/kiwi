# B7 — Spec Synthesis / R14 (5 days)

## Mục tiêu
Từ nhiều sessions cùng task_type → tự tổng hợp spec. Kiwi viết documentation cho chính nó — replace manual blueprint specs over time.

---

## Current State (pre-B7)

| Component | Status |
|-----------|--------|
| R2 Learner | Done — stores patterns per session |
| R3 Trust | Done — confidence scoring per pattern |
| R7 Metrics | Done — quality metrics per task_type |
| Blueprint specs | Manual — `.claude/blueprint/pages/` written by hand |
| Pattern aggregation | **Missing** — no mechanism to synthesize across sessions |
| Spec versioning | **Missing** — no auto-generated specs |

### Gap analysis
- `context_patterns` table has per-session data: files_needed, bindings, layout choices.
- After 10+ sessions for `checkout_page`, patterns are highly consistent (80%+).
- But this consistency is never surfaced as a synthesized spec.
- Blueprint specs are manually written — expensive to maintain, can drift from reality.
- Need: auto-generate specs from observed patterns, validate against outcomes.

---

## Tasks

### T1: Pattern Aggregator (1.5 days)
- Query `context_patterns` grouped by task_type
- For each task_type with 10+ sessions:
  - files_needed: frequency analysis → "always" (>80%), "usually" (50-80%), "sometimes" (<50%)
  - bindings: which data bindings appear consistently
  - layout: dominant layout pattern (e.g., "2-col main+sidebar" for checkout)
  - components: which wz_component() calls appear in 80%+ of sessions
  - common_mistakes: violations that appeared in 30%+ of sessions
- Output: `AggregatedPattern(task_type, files, bindings, layout, components, mistakes, sample_count)`

### T2: Spec Generator (1.5 days)
- From AggregatedPattern → generate Markdown spec document
- Template:
  ```markdown
  # {task_type} — Auto-Synthesized Spec
  
  ## Files Required
  - [always] cart.php, shipping.php, payment.php
  - [usually] order-summary.php
  
  ## Data Bindings
  - $cart_items (array), $shipping_methods (array), $payment_gateways (array)
  
  ## Layout
  - 2-column: main (checkout form) + sidebar (order summary)
  
  ## Components
  - wz_cart_summary(), wz_payment_form(), wz_shipping_selector()
  
  ## Common Mistakes (avoid)
  - Missing shipping validation before payment
  - Wrong total calculation (tax not included)
  
  ## Confidence: 0.85 (based on 14 sessions)
  ## Last updated: 2026-05-28
  ```
- Versioned: each generation creates new version, keeps history

### T3: Spec Validator (1 day)
- After spec generated → validate against next N sessions
- If spec predicts files_needed correctly 80%+ → confidence increases
- If spec diverges from reality → flag for review, don't auto-update
- Validation metrics: precision (spec items that were used), recall (used items in spec)

### T4: Context Integration (0.5 day)
- Wire into `context_assembler.py`:
  - If blueprint spec exists for task_type → use blueprint (manual takes priority)
  - If NO blueprint spec but synthesized spec exists with confidence > 0.7 → use synthesized
  - If neither → fall back to pattern-based assembly (current behavior)
- Log: "Using synthesized spec for {task_type} (confidence: {score})"

### T5: Tests + Storage (0.5 day)
- Unit test: 10 mock sessions → aggregator produces correct pattern
- Unit test: pattern → spec generator produces valid markdown
- Unit test: validator correctly scores spec against new session
- Integration: full pipeline mock → spec generated → used in context assembly
- Storage: `synthesized_specs` table (task_type, version, content, confidence, validated_count)

---

## Output Structure

```
agent/reasoning/
├── spec_synthesizer.py     # T2: aggregate patterns → generate spec
├── spec_validator.py       # T3: validate synthesized spec against outcomes
├── spec_store.py           # T5: store + version synthesized specs
├── pattern_aggregator.py   # T1: analyze context_patterns for consistency
└── test_r14.py             # T5: unit + integration tests

memory/
└── schema additions:
    - synthesized_specs table
    - spec_validations table
```

---

## Dependencies

| Dependency | From | What's needed |
|------------|------|---------------|
| R2 Learner | `agent/reasoning/learner.py` | context_patterns data |
| R3 Trust | `agent/reasoning/calibrator.py` | Confidence scoring |
| R7 Metrics | `agent/reasoning/metrics.py` | Quality metrics for validation |
| R1 Context | `agent/reasoning/context_assembler.py` | Integration point for specs |
| Blueprint | `.claude/blueprint/pages/` | Manual specs (take priority) |

---

## Done Criteria

- [ ] Pattern aggregation works for task_types with 10+ sessions
- [ ] Spec generated includes: files, bindings, layout, components, mistakes
- [ ] Spec confidence score reflects sample count + consistency
- [ ] Validator tracks precision/recall against new sessions
- [ ] Context assembler uses synthesized spec when no blueprint exists
- [ ] Manual blueprint always takes priority over synthesized
- [ ] Specs versioned: history preserved, can rollback
- [ ] Zero token cost for synthesis (all deterministic aggregation)
- [ ] Synthesis triggers automatically when threshold met (10 sessions, 80% consistency)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Synthesized spec wrong | Bad code generated | Confidence threshold 0.7; validator catches drift; manual always wins |
| Spec becomes stale | Outdated recommendations | Re-synthesize monthly; validator flags divergence |
| Too few sessions | Low confidence | Require 10+ sessions minimum; show confidence prominently |
| Spec conflicts with blueprint | Confusion | Clear priority: blueprint > synthesized > pattern-based |
| Over-fitting to one theme | Not generalizable | Aggregate across themes for same task_type; flag if only 1 theme contributes |
