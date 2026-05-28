# B6 — Multi-Model Routing / R10 (5 days)

## Mục tiêu
Chọn model phù hợp cho từng think() call. Haiku cho simple, Sonnet cho complex, Opus cho critical. Budget tracking + daily/weekly caps per tier.

---

## Current State (pre-B6)

| Component | Status |
|-----------|--------|
| R8 Thinking | Done — `thinker.py` always uses same model (Sonnet) |
| B1 (R9) Reflective | Done — evaluates think outcomes |
| Budget awareness | **Missing** — no cost tracking per think call |
| Complexity classification | **Missing** — all thinks treated equally |
| Model selection | **Missing** — hardcoded single model |

### Gap analysis
- `thinker.py` calls one model for all think() requests regardless of complexity.
- Simple decisions (pattern choice, style inference) waste tokens on Sonnet.
- Critical decisions (security review) might benefit from Opus but never get it.
- No budget cap → uncontrolled spend if many think() calls in one day.
- B1 (R9) provides accuracy data per trigger type — can inform routing.

---

## Tasks

### T1: Complexity Classifier (1.5 days)
- Classify think requests into tiers:
  - **Simple** (Haiku ~$0.0002): pattern choice, style inference, single-file decision
  - **Complex** (Sonnet ~$0.003): architecture decision, multi-file refactor, ambiguous transfer
  - **Critical** (Opus ~$0.015): security review, data migration, breaking change assessment
- Signals for classification:
  - Token count of context (more → bigger model)
  - Number of files involved (multi-file → Sonnet+)
  - Task type risk level (security → Opus)
  - Historical accuracy per model for this trigger type (from B1)
- Deterministic rules first, LLM classification only for edge cases

### T2: Model Router (1.5 days)
- Interface: `route(think_request) → ModelChoice(model_id, tier, estimated_cost)`
- Routing logic:
  1. Classify complexity (T1)
  2. Check budget (T3) — if tier budget exhausted → downgrade
  3. Check historical accuracy (from B1) — if Haiku was 95% accurate for this trigger → use Haiku
  4. Return model choice + log decision
- Override: user can force tier via config (`min_model_tier: "sonnet"`)
- Fallback: if API error on chosen model → retry with next tier up

### T3: Budget Tracker (1 day)
- Track spend per model tier: daily + weekly + monthly
- Schema: `model_budget(date, tier, calls_count, tokens_used, estimated_cost)`
- Configurable caps: `{haiku_daily: $0.50, sonnet_daily: $2.00, opus_daily: $5.00}`
- When cap reached → downgrade to lower tier (not block entirely)
- Dashboard metric: cost breakdown by tier + ROI per tier

### T4: Routing Feedback Loop (0.5 day)
- After think outcome evaluated (B1) → feed back into router
- If Haiku was accurate for trigger X → lower complexity score for X
- If Sonnet failed for trigger Y → raise complexity score for Y
- Adaptive: routing improves over time without manual tuning

### T5: Tests + Integration (0.5 day)
- Unit test: simple request → routes to Haiku
- Unit test: security request → routes to Opus
- Unit test: budget exhausted → downgrades gracefully
- Integration: mock think pipeline → verify correct model selected
- Verify: existing think() behavior unchanged when routing disabled

---

## Output Structure

```
agent/reasoning/
├── model_router.py         # T2: classify complexity → select model
├── budget_tracker.py       # T3: track spend per model, enforce caps
├── complexity_classifier.py # T1: determine think request complexity
└── test_r10.py             # T5: unit + integration tests

memory/
└── schema additions:
    - model_budget table
    - routing_history table (for feedback loop)
```

---

## Dependencies

| Dependency | From | What's needed |
|------------|------|---------------|
| R8 Thinking | `agent/reasoning/thinker.py` | think() interface, inject model choice |
| B1 (R9) | `think_evaluator.py` | Historical accuracy per trigger per model |
| A5 Freemium | `core/gating.py` | Tier limits (free users → Haiku only) |
| Config | `core/config.py` | Budget caps, min_model_tier setting |

---

## Done Criteria

- [ ] Think requests classified into 3 tiers (simple/complex/critical)
- [ ] Router selects appropriate model based on complexity + budget + history
- [ ] Budget tracking: daily/weekly caps per tier, enforced
- [ ] Cap exceeded → graceful downgrade (not block)
- [ ] Routing feedback: accuracy data from B1 improves routing over time
- [ ] Cost reduction: 40%+ vs always-Sonnet baseline (measured over 50+ thinks)
- [ ] Quality maintained: no accuracy drop for critical decisions
- [ ] Feature flag: `MODEL_ROUTING_ENABLED` (default True)
- [ ] Dashboard shows: cost breakdown, routing decisions, accuracy per tier

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Haiku too weak for "simple" tasks | Wrong decisions | Conservative initial classification; only route to Haiku after 10+ successful samples |
| Budget too restrictive | Blocks important thinks | Downgrade, never block; critical tier has 3x budget of others |
| Routing overhead | Latency | Classification is deterministic (<1ms); no LLM call for routing itself |
| Model API changes pricing | Budget inaccurate | Store pricing in config, update quarterly |
