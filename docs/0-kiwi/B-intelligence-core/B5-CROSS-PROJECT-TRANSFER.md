# B5 — Cross-Project Transfer / R12 (5 days)

## Mục tiêu
Học từ project A, apply cho project B. Kiwi trở thành "platform expert" — biết security patterns, API conventions, performance tricks áp dụng cross-project. Giữ riêng style tokens + business logic.

---

## Current State (pre-B5)

| Component | Status |
|-----------|--------|
| R2 Learner | Done — learns patterns within single project |
| R5 Cross-Theme | Done — transfers knowledge between themes (same project) |
| R8 Thinking | Done — handles ambiguous decisions |
| Multi-project support | **Missing** — Kiwi assumes single project context |
| Knowledge classification | **Partial** — lessons tagged by category, not by transferability |
| Project registry | **Missing** — no concept of "project identity" |

### Gap analysis
- `learner.py` stores patterns in `context_patterns` table — no `project` column.
- `cross_theme.py` (R5) transfers within same project (themes share same DB).
- No mechanism to say "security pattern from project A applies to project B".
- Lessons have `category` but not `transferable` flag.
- Need: project isolation + selective sharing.

---

## Tasks

### T1: Project Registry (1 day)
- Register projects with metadata: name, platform, domain, path
- Schema: `projects(id, name, platform, domain, path, registered_at)`
- Auto-detect on first scan: infer platform from file structure
- Domain classification: ecommerce, blog, saas, api, etc.

### T2: Knowledge Classification (1.5 days)
- Classify existing knowledge by transferability:
  - **Always transfer**: security (XSS, injection, auth, CSRF)
  - **Platform transfer**: API conventions (wp→wp, nextjs→nextjs)
  - **Stack transfer**: performance patterns (same stack only)
  - **Never transfer**: style tokens, business logic, domain terms
- Schema: `project_knowledge(id, project, knowledge_type, transferable, pattern, confidence)`
- Auto-classify: use lesson category → transferability mapping
- Manual override: user can mark specific knowledge as transferable/private

### T3: Knowledge Router (1.5 days)
- When assembling context for project B:
  1. Load project B's own knowledge (always)
  2. Query transferable knowledge from all other projects
  3. Filter by: same platform? same stack? always-transfer category?
  4. Rank by confidence + relevance
  5. Inject top-N transferable patterns into brief
- Conflict resolution: if project B has own pattern for same thing → prefer local

### T4: Transfer Validation (0.5 day)
- After applying transferred knowledge → track outcome
- If transfer leads to violation → mark as "not transferable for this project"
- Confidence decay: transferred knowledge starts at 0.5, grows with positive outcomes
- Feed into B1 (R9): think() decisions about transfers get evaluated

### T5: Tests + Integration (0.5 day)
- Unit test: register 2 projects, learn pattern in A, verify available in B
- Unit test: style token in A → NOT available in B
- Unit test: security pattern in A → available in B (always transfer)
- Integration: scan project B → transferred knowledge prevents violation
- Edge case: conflicting patterns between projects → local wins

---

## Output Structure

```
agent/reasoning/
├── project_registry.py     # T1: register + detect projects
├── knowledge_router.py     # T3: decide what transfers between projects
├── shared_knowledge.py     # T2: classify + store transferable patterns
└── test_r12.py             # T5: unit + integration tests

memory/
└── schema additions:
    - projects table
    - project_knowledge table
```

---

## Dependencies

| Dependency | From | What's needed |
|------------|------|---------------|
| R2 Learner | `agent/reasoning/learner.py` | Pattern storage + learning API |
| R5 Cross-Theme | `agent/reasoning/cross_theme.py` | Transfer mechanism (extend to cross-project) |
| R8 Thinking | `agent/reasoning/thinker.py` | Resolve ambiguous transfer decisions |
| B1 (R9) | `think_evaluator.py` | Evaluate transfer decisions |
| R1 Context | `agent/reasoning/context_assembler.py` | Inject transferred knowledge |

---

## Done Criteria

- [ ] Projects registered with platform + domain metadata
- [ ] Knowledge classified: always/platform/stack/never transfer
- [ ] Security patterns transfer across ALL projects (regardless of platform)
- [ ] API patterns transfer within same platform only
- [ ] Style tokens NEVER transfer between projects
- [ ] Transferred knowledge starts at confidence 0.5, adjusts with outcomes
- [ ] Local knowledge always takes priority over transferred
- [ ] Works with 2+ projects registered simultaneously
- [ ] Zero token cost for classification (rule-based, not LLM)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Wrong transfer (style leaks) | Bad code in project B | Never-transfer list is strict; only security/API/perf transfer |
| Too much transferred knowledge | Context overload | Max 5 transferred patterns per brief |
| Conflicting patterns | Confusion | Local always wins; transferred only fills gaps |
| Cold start (new project) | No local knowledge | Transferred knowledge is the bootstrap mechanism |