# B3 — Predictive Prefetch / R11 (3 days)

## Mục tiêu
Dự đoán task tiếp theo từ session patterns, pre-compute brief + skeleton. Latency gần 0 cho predicted tasks.

---

## Current State (pre-B3)

| Component | Status |
|-----------|--------|
| R0 Session Logger | Done — `session_logger.py` logs tool calls per session |
| R1 Context Assembly | Done — `context_assembler.py` builds brief |
| R6 Code Generation | Done — `code_drafter.py` generates skeleton from brief |
| Task sequence data | Available — `context_patterns` table in `memory/reasoning.db` |
| Prediction engine | **Missing** — no Markov chain or prefetch |
| Prefetch cache | **Missing** — no pre-computed briefs stored |

### Gap analysis
- `context_patterns` table has: `(task_type, files_read, files_written, read_order, theme, session_id, created_at)`
- Bindings stored separately in `binding_knowledge` table: `(task_type, binding, theme, times_seen)`
- Sequence data exists but not analyzed: "after home_page → usually product_page"
- `context_assembler.assemble()` takes ~200-500ms (DB queries + file reads)
- If predicted correctly → save that latency entirely

---

## Tasks

### T1: Task Sequence Analyzer (0.5 day)
- Parse `context_patterns` → extract task transitions
- Build transition matrix: P(next_task | current_task, theme_type)
- Store as: `task_transitions(from_task, to_task, theme_type, count, probability)`
- Update incrementally after each session (not full rebuild)

### T2: Predictor Engine (1 day)
- Markov chain (deterministic, 0 token):
  - Input: current_task + theme_type
  - Output: top 2 predictions with probability
  - Only predict if P > 0.6 (configurable threshold)
- Trigger: when current task completes (session observer hook)
- Consider theme_type as context: beauty themes have different flows than tech themes

### T3: Prefetch Cache (1 day)
- When prediction fires → background compute brief for predicted task
- Store in memory (not disk — ephemeral, session-scoped)
- Cache entry: `{task_type, theme, brief, skeleton_hint, computed_at, ttl}`
- TTL: 10 minutes (stale brief worse than no brief)
- Invalidation: if theme files change after prefetch → discard
- Max cache size: 2 entries (top 2 predictions)

### T4: Integration + Tests (0.5 day)
- Wire into `context_assembler`: check cache before computing
- If cache hit → return instantly (log: "prefetch hit")
- If cache miss → compute normally (log: "prefetch miss")
- Metrics: hit_rate, avg_latency_saved, prediction_accuracy
- Tests: mock session sequence → verify prediction → verify cache hit

---

## Output Structure

```
agent/reasoning/
├── predictor.py            # T1+T2: analyze sequences + predict next task
├── prefetch_cache.py       # T3: store pre-computed briefs
└── test_r11.py             # T4: unit + integration tests
```

---

## Dependencies

| Dependency | From | What's needed |
|------------|------|---------------|
| R0 Session Logger | `agent/reasoning/session_logger.py` | Session task sequence data (session_log + sessions tables) |
| R1 Context | `agent/reasoning/context_assembler.py` | assemble() to pre-compute briefs |
| SQLite memory | `memory/reasoning.db` (via `session_logger._get_conn()`) | context_patterns table access |
| R6 Code Gen | `agent/reasoning/code_drafter.py` | Optional: pre-generate skeleton |

---

## Done Criteria

- [ ] Transition matrix built from historical sessions (10+ data points per transition)
- [ ] Predictor returns top 2 predictions with probability scores
- [ ] Only prefetch when P > 0.6 (no wasted computation)
- [ ] Cache hit → context assembly latency drops to ~0ms
- [ ] Cache invalidation works: file change → discard stale brief
- [ ] Prediction accuracy > 60% (measured over 20+ sessions)
- [ ] Zero token cost (entire system is deterministic)
- [ ] Graceful degradation: if no history → skip prediction, compute normally

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Low prediction accuracy | Wasted computation | Only prefetch at P > 0.6; track accuracy, raise threshold if needed |
| Stale cache served | Wrong brief | TTL 10min + invalidate on file change |
| Cold start (new theme) | No predictions | Fallback to theme_type-level predictions (cross-theme) |
| Memory overhead | RAM usage | Max 2 cache entries, each ~5KB → negligible |