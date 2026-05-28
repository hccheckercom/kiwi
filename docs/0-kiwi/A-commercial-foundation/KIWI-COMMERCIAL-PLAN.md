# Kiwi Commercial Plan — "Claude's Child" Cost Optimizer

## Vision

**Kiwi = Local intelligence layer giữa user và Claude.**

User không cần gọi Claude cho mọi thứ. Kiwi handle 80% work locally (0 cost), chỉ escalate 20% lên Claude (paid). Kết quả: user tiết kiệm 75-90% chi phí Claude mà output quality không giảm.

```
Trước Kiwi:  User → Claude (100% requests, 100% cost)
Sau Kiwi:    User → Kiwi (80% handled locally, 0 cost) → Claude (20% escalated, 20% cost)
```

---

## Value Proposition

| Audience | Pain | Kiwi solves |
|----------|------|-------------|
| Solo dev | Claude API bill $50-200/tháng | Giảm xuống $10-40/tháng |
| Agency/team | 5 devs × $100 = $500/tháng | Giảm xuống $100-150/tháng |
| Enterprise | Thousands of API calls/day | 80% handled locally, compliance + cost control |

**One-liner:** "Kiwi learns your codebase so Claude doesn't have to re-learn it every session."

---

## How It Works (User Perspective)

```
1. User installs Kiwi (CLI tool hoặc VS Code extension)
2. Kiwi scans codebase → builds local knowledge base
3. User asks question/task
4. Kiwi decides:
   - "I know this" → answer locally (0 cost)
   - "I'm 80% sure" → answer + flag for review (0 cost)
   - "I need Claude" → forward to Claude with context (reduced tokens)
5. After Claude responds → Kiwi learns from response (next time handles locally)
```

**User experience:** Giống hệt dùng Claude, nhưng bill thấp hơn 75-90%.

---

## 3 Tiers of Product

### Tier 1: Kiwi Free — Context Optimizer
- Giảm tokens gửi lên Claude bằng cách inject context thông minh
- Thay vì Claude đọc 50 files → Kiwi chọn đúng 5 files cần thiết
- **Savings: 30-50%** (vẫn gọi Claude mọi request, nhưng ít tokens hơn)
- **Monetization:** Free, dùng làm funnel

### Tier 2: Kiwi Pro — Local Intelligence ($19/tháng)
- Kiwi tự trả lời questions về codebase (0 Claude calls)
- Kiwi generate boilerplate/skeleton code locally
- Kiwi review code locally (style, patterns, common bugs)
- Chỉ escalate complex tasks lên Claude
- **Savings: 60-75%**
- **Monetization:** Subscription

### Tier 3: Kiwi Team — Shared Learning ($49/user/tháng)
- Shared knowledge base across team
- Kiwi learns from ALL team members' Claude sessions
- Cross-project pattern transfer
- Admin dashboard: cost tracking, usage analytics
- **Savings: 80-90%**
- **Monetization:** Per-seat subscription

---

## Technical Architecture (Commercial)

```
┌─────────────────────────────────────────────────┐
│                    USER                           │
├─────────────────────────────────────────────────┤
│              KIWI CLIENT                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │ VS Code  │  │   CLI    │  │  Web UI  │     │
│  │Extension │  │  (local) │  │(dashboard)│     │
│  └──────────┘  └──────────┘  └──────────┘     │
├─────────────────────────────────────────────────┤
│              KIWI ENGINE (local)                  │
│  ┌──────────────────────────────────────────┐   │
│  │  Reasoning Layer (R0-R27)                 │   │
│  │  ├── Context Assembly                     │   │
│  │  ├── Trust Scoring                        │   │
│  │  ├── Code Generation                     │   │
│  │  ├── Pattern Matching                    │   │
│  │  └── Decision Engine (route or handle)   │   │
│  ├──────────────────────────────────────────┤   │
│  │  Knowledge Base (SQLite)                  │   │
│  │  ├── Lessons (bug patterns)              │   │
│  │  ├── Style Knowledge                     │   │
│  │  ├── Binding Knowledge                   │   │
│  │  ├── Cross-theme Patterns                │   │
│  │  └── Session History                     │   │
│  └──────────────────────────────────────────┘   │
├─────────────────────────────────────────────────┤
│              ROUTING LAYER                        │
│  ┌──────────────────────────────────────────┐   │
│  │  "Can I handle this locally?"             │   │
│  │  YES (80%) → respond directly             │   │
│  │  NO  (20%) → forward to Claude API        │   │
│  │              (with optimized context)      │   │
│  └──────────────────────────────────────────┘   │
├─────────────────────────────────────────────────┤
│              CLAUDE API (paid)                    │
│  Only called for:                                │
│  - Novel tasks (no pattern match)               │
│  - Complex reasoning (architecture, debugging)  │
│  - Creative decisions (UX, design)              │
│  - User explicitly requests Claude              │
└─────────────────────────────────────────────────┘
```

---

## Routing Decision Engine

```python
def should_escalate_to_claude(task, context) -> bool:
    """Core routing logic — determines if Claude is needed."""
    
    # Always escalate
    if user_explicitly_requests_claude(task):
        return True
    if task_is_security_critical(task):
        return True
    
    # Never escalate (handle locally)
    if task_is_simple_lookup(task):  # "where is function X defined?"
        return False
    if task_is_pattern_match(task) and trust > 0.85:
        return False
    if task_is_boilerplate(task):  # CRUD, forms, standard pages
        return False
    
    # Decision based on trust + complexity
    trust = compute_trust(task, context)
    complexity = estimate_complexity(task)
    
    if trust > 0.8 and complexity < 0.5:
        return False  # Kiwi handles
    if trust < 0.4 or complexity > 0.8:
        return True   # Claude handles
    
    # Borderline: Kiwi attempts, flags for review
    return False  # but mark output as "unverified"
```

---

## What Kiwi Handles Locally (0 cost)

| Category | Examples | % of requests |
|----------|----------|---------------|
| Code navigation | "Where is X defined?", "Who calls Y?" | 15% |
| Pattern code gen | CRUD, forms, standard pages, boilerplate | 25% |
| Bug pattern detection | Known anti-patterns, style violations | 15% |
| Code review | Style consistency, naming, common bugs | 10% |
| Refactoring | Rename, extract function, move file | 10% |
| Documentation | Generate docs from code, explain function | 5% |
| **Total local** | | **80%** |

## What Gets Escalated to Claude (paid)

| Category | Examples | % of requests |
|----------|----------|---------------|
| Novel features | First-time implementations, new architecture | 8% |
| Complex debugging | Multi-file bugs, race conditions | 5% |
| Creative decisions | UX design, API design, naming | 4% |
| Security review | Auth flows, data handling, encryption | 3% |
| **Total escalated** | | **20%** |

---

## Revenue Model

### Pricing

| Plan | Price | Target | Features |
|------|-------|--------|----------|
| Free | $0 | Solo devs trying out | Context optimization only, 30% savings |
| Pro | $19/mo | Active solo devs | Full local intelligence, 60-75% savings |
| Team | $49/user/mo | Agencies, startups | Shared learning + dashboard, 80-90% savings |
| Enterprise | Custom | Large orgs | On-prem, SSO, audit logs, compliance |

### Unit Economics

```
Average Claude user spends: $100/month
With Kiwi Pro: saves $60-75/month → pays $19 → net savings $41-56/month
ROI for user: 3-4x return on Kiwi subscription

Kiwi revenue per user: $19/month
Kiwi cost per user: ~$2/month (hosting, sync, support)
Gross margin: ~89%
```

### Growth Model

```
Year 1: 1,000 Pro users × $19 = $19K MRR ($228K ARR)
Year 2: 5,000 Pro + 500 Team = $120K MRR ($1.4M ARR)
Year 3: 15,000 Pro + 2,000 Team + 50 Enterprise = $500K+ MRR
```

---

## Competitive Positioning

| Competitor | What they do | Kiwi difference |
|-----------|-------------|-----------------|
| Cursor | AI IDE (uses Claude/GPT) | Kiwi reduces cost OF using Cursor |
| Copilot | Code completion | Kiwi is full-task, not just autocomplete |
| Cody (Sourcegraph) | Codebase-aware AI | Kiwi learns over time, gets smarter |
| Continue.dev | Open-source AI IDE | Kiwi has reasoning layer, not just proxy |
| Aider | CLI coding assistant | Kiwi handles locally first, escalates smart |

**Kiwi's moat:** Learning loop. The more you use it, the less you need Claude. No competitor has this — they all proxy every request to LLM.

---

## Go-to-Market Strategy

### Phase 1: Open Source Core (Month 1-3)
- Release Kiwi reasoning engine as open source
- Free tier: context optimization (30% savings)
- Build community, get feedback, prove value
- Target: Claude Code users (already paying for Claude)

### Phase 2: Pro Launch (Month 4-6)
- Launch Pro tier ($19/mo)
- VS Code extension + CLI
- Marketing: "Save 75% on your Claude bill"
- Content: blog posts showing before/after cost comparisons
- Target: 1,000 paying users

### Phase 3: Team Launch (Month 7-12)
- Launch Team tier ($49/user/mo)
- Shared knowledge base across team
- Admin dashboard with cost analytics
- Target: agencies, startups with 5-20 devs

### Phase 4: Enterprise (Year 2)
- On-premise deployment
- SSO, audit logs, compliance
- Custom integrations
- Target: companies with 100+ devs

---

## Technical Milestones for Commercial

| Milestone | What | When |
|-----------|------|------|
| M1 | Language-agnostic engine (not just PHP/WP) | Month 1 |
| M2 | VS Code extension (seamless UX) | Month 2 |
| M3 | Routing engine (local vs Claude decision) | Month 2 |
| M4 | Usage dashboard + cost tracking | Month 3 |
| M5 | Team sync (shared knowledge base) | Month 5 |
| M6 | Multi-language support (JS, Python, Go, Rust) | Month 6 |
| M7 | Enterprise features (SSO, audit, on-prem) | Month 9 |

---

## Key Metrics to Track

| Metric | Target | Why |
|--------|--------|-----|
| Local resolution rate | > 80% | Core value prop |
| Cost savings per user | > 60% | Retention driver |
| Trust accuracy | > 90% | Quality gate |
| Time to first value | < 5 min | Onboarding |
| Churn rate | < 5%/month | Business health |
| NPS | > 50 | Word of mouth |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Claude gets cheaper (price drops) | Value prop weakens | Pivot to speed/privacy (local = faster + private) |
| Claude gets local model | Direct competition | Kiwi's learning loop is the moat, not just local execution |
| Quality issues (wrong local answers) | Trust loss, churn | Conservative routing (escalate when unsure), confidence scores |
| Anthropic blocks/restricts | Platform risk | Support multiple LLMs (OpenAI, Gemini, local models) |
| Slow adoption | Revenue miss | Free tier as funnel, prove ROI before asking for payment |

---

## Messaging

### Tagline options:
1. "Kiwi — Your AI learns so you pay less"
2. "Kiwi — Local intelligence, Claude when you need it"
3. "Kiwi — 80% of Claude's power, 20% of the cost"
4. "Kiwi — The AI that gets smarter so your bill gets smaller"

### Elevator pitch:
> "Kiwi sits between you and Claude. It learns your codebase, your patterns, your style. 
> After a week, it handles 80% of your coding tasks locally — zero API cost. 
> The other 20%? It sends to Claude with perfect context, so Claude responds faster and cheaper.
> Result: same quality, 75% less spend."

---

## Phase 0: What We Have Today (Foundation)

Kiwi đã có sẵn:
- 726 lessons (bug patterns)
- Reasoning engine R0-R6 (observe, learn, calibrate, generate)
- Trust scoring (6 dimensions)
- Cross-theme pattern transfer
- Code generation (4 levels)
- 124 tests passing

**Cần thêm cho commercial:**
1. Language-agnostic (hiện chỉ PHP/WordPress)
2. Routing engine (local vs Claude decision)
3. VS Code extension (UX layer)
4. Usage tracking + billing
5. Multi-LLM support (không chỉ Claude)
6. Onboarding flow (scan codebase → ready in 5 min)

---

## Summary

Kiwi commercial = **"Claude's child"** — học từ Claude, dần handle work locally, giảm chi phí cho user.

```
Week 1:  Kiwi handles 20% locally (user saves 20%)
Week 4:  Kiwi handles 50% locally (user saves 50%)
Week 12: Kiwi handles 80% locally (user saves 75-80%)
```

Càng dùng lâu, càng tiết kiệm. Đó là moat — không ai khác có learning loop này.