# Implementation Order — Milestones & Dependencies

## Dependency Graph

```
                    Phase 4: Learning & Memory
                         │ enhances
                         ▼
                    Phase 3: Agent Loop
                         │ requires
                    ┌────┴────┐
                    ▼         ▼
         Phase 2: Auto-Fix   Phase 1: MCP Server
                    │              │
                    └──────┬───────┘
                           ▼
                  Existing: Scanner v3
```

**Phase 1 (MCP)** và **Phase 2 (Auto-Fix)** độc lập nhau — có thể build song song.
**Phase 3 (Agent)** cần cả Phase 1 + Phase 2.
**Phase 4 (Learning)** enhances Phase 3, nhưng có thể ship basic version sớm hơn.

## Milestones

### M1: MCP Server (Phase 1) — ~200 lines code

| Step | Task | Effort | Dependency |
|------|------|--------|------------|
| 1.1 | Tạo `mcp_server.py` skeleton (JSON-RPC loop, initialize, tools/list) | 30 min | None |
| 1.2 | Implement `kiwi_scan` (wrap scan_theme) | 30 min | 1.1 |
| 1.3 | Implement `kiwi_query` (search lessons) | 20 min | 1.1 |
| 1.4 | Implement `kiwi_lesson` (read full lesson) | 15 min | 1.1 |
| 1.5 | Implement `kiwi_stats` (wrap stats.py) | 10 min | 1.1 |
| 1.6 | Implement `kiwi_fix` (read-only: Good section) | 15 min | 1.1 |
| 1.7 | Implement `kiwi_add` (wrap add.py) | 20 min | 1.1 |
| 1.8 | Implement `kiwi_template` (wrap query.py) | 15 min | 1.1 |
| 1.9 | Register in `.mcp.json` | 5 min | 1.1-1.8 |
| 1.10 | Test: JSON-RPC manual + Claude Code integration | 30 min | 1.9 |

**Total: ~3 hours | Deliverable: 7 MCP tools hoạt động**

### M2: Auto-Fix Engine (Phase 2) — ~150 lines code

| Step | Task | Effort | Dependency |
|------|------|--------|------------|
| 2.1 | Tạo `scanner/fixer.py` — FixResult dataclass | 15 min | None |
| 2.2 | Implement `_apply_replace()` | 30 min | 2.1 |
| 2.3 | Implement `_apply_template()` | 30 min | 2.1 |
| 2.4 | Implement `_apply_llm()` — placeholder | 10 min | 2.1 |
| 2.5 | Add `fix` field to 10 CRITICAL lessons (Batch 1: php-security) | 45 min | 2.2 |
| 2.6 | Add `fix` field to 10 HIGH lessons (Batch 2: wezone-api) | 30 min | 2.2 |
| 2.7 | Update `kiwi_fix` MCP tool — add `apply` option | 15 min | M1 + 2.2 |
| 2.8 | Test: dry-run + apply + re-scan | 30 min | 2.7 |

**Total: ~3.5 hours | Deliverable: 20 lessons with auto-fix**

### M3: Agent Loop (Phase 3) — ~300 lines code

| Step | Task | Effort | Dependency |
|------|------|--------|------------|
| 3.1 | Install `anthropic` package | 5 min | None |
| 3.2 | Create `agent/` package structure | 10 min | None |
| 3.3 | Write `prompts.py` — system prompt + few-shot | 30 min | None |
| 3.4 | Write `tools.py` — tool definitions + execute_tool | 45 min | M1 + M2 |
| 3.5 | Write `state.py` — AgentState dataclass | 15 min | None |
| 3.6 | Write `loop.py` — main agent loop | 60 min | 3.3-3.5 |
| 3.7 | Write `cli.py` — CLI entry point | 15 min | 3.6 |
| 3.8 | Add `kiwi_agent` MCP tool | 20 min | 3.7 + M1 |
| 3.9 | Test: review mode on wezone-plugins | 30 min | 3.8 |
| 3.10 | Test: auto mode on test theme | 30 min | 3.9 |

**Total: ~4.5 hours | Deliverable: Working agent with 3 modes**

### M4: Learning & Memory (Phase 4) — ~250 lines code

| Step | Task | Effort | Dependency |
|------|------|--------|------------|
| 4.1 | Create `memory/` package + `db.py` schema | 30 min | None |
| 4.2 | Implement scan logging (log_scan, get_history) | 20 min | 4.1 |
| 4.3 | Implement false positive tracking (dismiss, is_dismissed) | 20 min | 4.1 |
| 4.4 | Write `confidence.py` — scoring algorithm | 30 min | 4.1 |
| 4.5 | Write `trends.py` — violation_trend, regression_check | 30 min | 4.1 |
| 4.6 | Integrate memory into scanner (scan_with_memory) | 20 min | M1 + 4.2-4.3 |
| 4.7 | Add MCP tools: kiwi_dismiss, kiwi_trends, kiwi_confidence | 20 min | M1 + 4.2-4.5 |
| 4.8 | Integrate into agent loop (learn step) | 20 min | M3 + 4.2-4.4 |
| 4.9 | Test: full cycle (scan → dismiss → re-scan → confidence) | 30 min | 4.6-4.8 |

**Total: ~3.5 hours | Deliverable: Persistent memory system**

## Overall Timeline

```
Session 1: Phase 1 (MCP Server)           3h    ████████████
Session 2: Phase 2 (Auto-Fix)             3.5h  █████████████
Session 3: Phase 3 (Agent Loop)           4.5h  █████████████████
Session 4: Phase 4 (Learning)             3.5h  █████████████
                                          ─────
                                  Total: ~14.5h
```

## Build Order (recommended)

```
1. Phase 1: MCP Server  ← START HERE
   ↓ ship & verify
2. Phase 2: Auto-Fix    ← can start while testing Phase 1
   ↓ ship & verify  
3. Phase 4: Learning    ← ship basic DB + scan logging first
   ↓ ship & verify      (before agent, so agent can log from day 1)
4. Phase 3: Agent Loop  ← last, builds on everything
   ↓ ship & verify
```

**Lý do đảo Phase 3↔4:** Ship learning (basic: scan history + false positives) trước agent. Khi agent ship, nó đã có memory từ ngày đầu — không cần retrofit.

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| `anthropic` package not installed | Phase 3 blocked | Install early: `pip install anthropic` |
| API key configuration | Phase 3 blocked | Reuse orbit-provider config from settings.local.json |
| MCP server import path issues | Phase 1 blocked | Test `sys.path` setup carefully, lazy imports |
| False positive in auto-fix | Data loss | Git stash + dry-run default + max_fixes limit |
| Scanner breaking changes | All phases | MCP wraps existing code, doesn't modify scanner core |
| Large scan output overwhelming Claude | Phase 3 | max_per_lesson cap, summary mode, token limits |

## Success Criteria

### Phase 1 Done When:
- [ ] All 7 MCP tools respond correctly to JSON-RPC calls
- [ ] `.mcp.json` registered, Claude Code sees tools
- [ ] `kiwi_scan` returns same results as CLI `python -m scanner.cli`
- [ ] Existing CLI, skills, hooks still work (backward compat)

### Phase 2 Done When:
- [ ] 20+ lessons have `fix` field
- [ ] `kiwi_fix` dry-run shows correct diff
- [ ] `kiwi_fix` apply modifies file correctly
- [ ] Re-scan after fix shows violation resolved
- [ ] No regression (new violations) from fix

### Phase 3 Done When:
- [ ] Agent review mode produces useful analysis
- [ ] Agent auto mode can fix 5+ CRITICAL violations in one run
- [ ] Agent detects and reports regressions
- [ ] Safety mechanisms work (git stash, max_fixes, rollback)
- [ ] Agent accessible via CLI, MCP, and Claude Code skill

### Phase 4 Done When:
- [ ] kiwi.db created with correct schema
- [ ] Scan history recorded automatically
- [ ] Dismissed violations suppressed in next scan
- [ ] Confidence scores calculated correctly
- [ ] Trend data shows meaningful patterns after 5+ scans