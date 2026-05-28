# A5 — Freemium Gating (2 days)

## Mục tiêu
Giới hạn Free tier đủ để thấy value, muốn upgrade. Zero LLM tokens at runtime.

## Architecture

```
core/
├── tier_config.py         # TIER_LIMITS dict + TierConfig dataclass
├── tier_manager.py        # singleton: resolve tier, check limits, count usage
├── gating.py              # @gated decorator + gate_check() for inline use
└── upgrade_prompts.py     # context-aware upgrade messages

Config resolution order:
  1. ENV: KIWI_TIER=pro (override for CI/testing)
  2. File: .kiwi/license.json {"tier": "starter", "key": "..."}
  3. Default: "free"
```

## Tier Limits

```python
TIER_LIMITS = {
    'free': {
        'max_patterns': 30,        # pattern_miner stops learning
        'max_conventions': 5,      # convention_learner stops learning
        'trust_cap': 0.6,          # quality_base caps confidence
        'code_generation': False,  # drafter disabled
        'cross_project': False,    # no cross-project analysis
        'session_learning': False, # no session log learning
        'max_scans_day': 20,       # daily scan limit
        'agent_mode': False,       # no autonomous agent
    },
    'starter': {
        'max_patterns': 200,
        'max_conventions': 20,
        'trust_cap': 0.8,
        'code_generation': 'skeleton',
        'cross_project': False,
        'session_learning': 'basic',
        'max_scans_day': 100,
        'agent_mode': 'review',
    },
    'pro': {
        'max_patterns': None,      # unlimited
        'max_conventions': None,
        'trust_cap': 1.0,
        'code_generation': 'full',
        'cross_project': True,
        'session_learning': 'full',
        'max_scans_day': None,
        'agent_mode': 'auto',
    },
}
```

## Tasks (ordered)

### T1: core/tier_config.py — Tier definitions (30 min)
- `TIER_LIMITS` dict (above)
- `TierConfig` dataclass: tier name, limits dict, resolved from
- `get_limit(tier, key)` → value or None (unlimited)
- Pure data, no I/O

### T2: core/tier_manager.py — Singleton manager (1.5 hr)
- `TierManager` singleton (same pattern as UsageTracker)
- `resolve_tier()`: ENV → file → "free"
- `get_current_tier()` → TierConfig
- `check_limit(feature, current_count)` → (allowed: bool, remaining: int, limit: int|None)
- `get_usage_counts()` → dict from SQLite (patterns learned, conventions, scans today)
- Count queries reuse `tracking/usage_tracker.py` DB (usage_events table)
- License file: `.kiwi/license.json` — `{"tier": "starter", "key": "sk-kiwi-...", "expires": "2026-12-31"}`

### T3: core/gating.py — Gate enforcement (1 hr)
- `@gated(feature)` decorator for plugin methods
- `gate_check(feature)` → GateResult(allowed, message, upgrade_hint)
- Integration points:
  - `plugins/generic/pattern_miner.py:mine()` → gate `max_patterns`
  - `plugins/generic/convention_learner.py:learn()` → gate `max_conventions`
  - `core/drafter_base.py` → gate `code_generation`
  - `mcp_server.py:_handle_agent()` → gate `agent_mode`
  - `mcp_server.py:_handle_scan()` → gate `max_scans_day`
- GateResult includes: what was blocked, current count, limit, upgrade tier needed

### T4: core/upgrade_prompts.py — Smart messages (45 min)
- Context-aware: knows what was blocked + what user would get
- Uses A4 savings data: "You saved $12.40 this week. Starter unlocks 6x more patterns → est. $45/week savings"
- Templates:
  - `pattern_limit_hit`: "Found 12 new patterns but can't learn them (30/30 used). Upgrade to Starter for 200 patterns."
  - `scan_limit_hit`: "Daily scan limit reached (20/20). Upgrade for 100/day."
  - `feature_locked`: "Code generation requires Starter tier. See what you'd get: `kiwi dashboard --upgrade`"
- `get_upgrade_prompt(context)` → formatted string for MCP response

### T5: Integration — Wire into existing code (1.5 hr)
- `plugins/generic/pattern_miner.py`: add gate check at top of `mine()`
  - If over limit: return existing patterns only, append upgrade message
- `plugins/generic/convention_learner.py`: add gate check at top of `learn()`
- `mcp_server.py`: add tier check in dispatch (before tool execution)
  - Gated tools: `kiwi_agent`, `kiwi_scan` (daily limit), `kiwi_learn_session`
  - Non-gated (always free): `kiwi_check`, `kiwi_context`, `kiwi_query`, `kiwi_lesson`, `kiwi_stats`
- `tracking/dashboard.py`: add upgrade estimate section
  - "If Starter: est. $X/mo additional savings based on blocked patterns"

### T6: MCP tool — kiwi_tier (30 min)
- New tool in mcp_server.py: `kiwi_tier`
- Shows: current tier, usage vs limits, upgrade options
- Subcommands via args: `status` (default), `activate <key>`
- Activate: write key to `.kiwi/license.json`, verify format

### T7: Tests — test_a5_freemium_gating.py (1.5 hr)
- GROUP 1: Module structure (files exist, importable)
- GROUP 2: Tier resolution (ENV override, file, default)
- GROUP 3: Limit enforcement (pattern cap, convention cap, scan daily)
- GROUP 4: Gate decorator (blocks correctly, passes when under limit)
- GROUP 5: Upgrade prompts (context-aware, includes savings data)
- GROUP 6: Integration (pattern_miner respects gate, convention_learner respects gate)
- GROUP 7: MCP tool (kiwi_tier status, activate)
- GROUP 8: Backward compat (A4 tests still pass, existing behavior unchanged for "pro" default in dev)
- Target: 80+ checks, 0 failures

## Integration Points (detailed)

| File | Change | Risk |
|------|--------|------|
| `plugins/generic/pattern_miner.py:mine()` | Add `gate_check("max_patterns")` at L23 | Low — early return |
| `plugins/generic/convention_learner.py:learn()` | Add `gate_check("max_conventions")` | Low — early return |
| `core/drafter_base.py` | Add `@gated("code_generation")` | Low — decorator |
| `mcp_server.py` dispatch | Add tier check before gated tools | Med — affects all calls |
| `tracking/dashboard.py:format_compact()` | Append upgrade estimate | Low — additive |
| `tracking/usage_tracker.py` | No changes needed (reuse existing DB) | None |

## Dev-mode Behavior

**CRITICAL**: During development (no license file, no ENV), default tier = "free" BUT:
- First-run grace period: 7 days unlimited (stored in `.kiwi/trial.json`)
- After grace: enforce free limits
- `KIWI_DEV=1` ENV → bypass all gates (for Kiwi development itself)

## Dependencies
- A4 Usage Tracking (savings data for upgrade prompts) ✅ DONE
- A3 Generic Plugin (pattern_miner, convention_learner to gate) ✅ DONE

## Done khi
- [ ] Free user hits 30 patterns → mine() returns existing only + upgrade prompt
- [ ] Free user hits 5 conventions → learn() returns existing only + upgrade prompt
- [ ] Free user hits 20 scans/day → scan returns error + upgrade prompt
- [ ] Trust score capped at 0.6 for free tier
- [ ] `kiwi_tier` MCP tool shows status + usage
- [ ] Dashboard shows: "Estimated savings if Starter: $X/mo"
- [ ] `KIWI_DEV=1` bypasses all gates (for internal development)
- [ ] 80+ QA checks pass, A4 backward compat maintained
- [ ] Zero LLM tokens consumed by gating logic