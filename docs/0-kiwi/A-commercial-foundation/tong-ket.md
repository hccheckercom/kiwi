Tổng kết A-series:

A1 Core/Plugin Separation đã hoàn thành:

core/ (11 files): plugin_base, checker_base, drafter_base, quality_base, plugin_loader, plugin_registry, integration, scanner/engine
plugins/wezone_wp/ (plugin.py + manifest.json): wrap 740 lessons, 6 checkers, 67 context keywords, 5 quality rules
21 tests pass, zero regression, backward compat confirmed
A2 Classify Lessons đã hoàn thành:

379 universal lessons → plugins/generic/ (plugin.py + manifest.json + lessons/)
361 wezone-specific lessons giữ nguyên trong plugins/wezone_wp/
3-layer classification (category → keyword case-insensitive → regex)
Zero wz_/wezone contamination in generic, 36/36 QA pass
Tools: classify_lessons.py, copy_universal_lessons.py, classification_report.json
A3 Generic Plugin Auto-Learn đã hoàn thành:

auto_detector.py: detect language/framework/tooling từ config + extensions (React, Python, Go, Rust, PHP...)
convention_learner.py: extract naming/indent/import/structure conventions
pattern_miner.py: mine empty catch, magic numbers, dead code, DRY violations, debug statements
checkers.py: generic checks (naming consistency, error handling, dead code, file size)
drafter.py: skeleton generator cho Python/JS/TS/TSX/PHP/Go/Rust
plugin.py v2.0: smart detect_project() + analyze_project() + run_generic_checks()
core/plugin_registry.py: fixed relative imports (parent package setup in sys.modules)
0 LLM tokens at runtime, 45/45 QA pass, A2 backward compat 36/36 pass
A4 Usage Tracking + Dashboard đã hoàn thành:

tracking/usage_tracker.py: singleton UsageTracker, records mọi MCP tool call vào SQLite
tracking/baseline_estimator.py: 16 operation formulas, reuse agent/cost.py PRICING (Sonnet baseline)
tracking/savings.py: actual vs baseline calculator, daily + cumulative views
tracking/dashboard.py: CLI + MCP formatted output (compact/detail/json)
tracking/schema.sql: usage_events table + savings_daily + savings_cumulative views
mcp_server.py: kiwi_dashboard tool + auto-tracking tại dispatch level
76/76 QA pass, A3 backward compat 45/45 pass, zero regression
A5 Freemium Gating đã hoàn thành:

core/tier_config.py: TIER_LIMITS (free/starter/pro), TierConfig dataclass, FREE_TOOLS/GATED_TOOLS
core/tier_manager.py: singleton resolve tier (ENV → license → trial → free), check_limit(), activate_license()
core/gating.py: gate_check(), gate_tool(), @gated decorator
core/upgrade_prompts.py: context-aware messages with savings estimates, format_tier_status()
mcp_server.py: _check_tier_gate in dispatch + kiwi_tier tool
plugins/generic/pattern_miner.py + convention_learner.py: gate integration
7-day grace period, KIWI_DEV=1 bypass, license.json activation
96/96 QA pass, A4+A3 backward compat maintained, zero regression
A6 CLI Packaging đã hoàn thành:

cli/init.py, cli/main.py, cli/helpers.py: click group entry point
cli/commands/: init_cmd.py, scan.py, check.py, dashboard.py, status.py, upgrade.py
pyproject.toml: PEP 621, pip-installable, entry point kiwi = cli.main:cli
All 6 commands reuse existing modules (scanner, tracking, tier_manager, plugin_registry, auto_detector) — zero duplication
77/77 QA pass, A5+A4+A3 backward compat maintained, zero regression
A7 HTTP Server + WebSocket đã hoàn thành:

server/init.py, app.py, auth.py, models.py, ws.py, watcher.py
server/routes/: init.py, scan.py, knowledge.py, fix.py, dashboard.py, tier.py, health.py
cli/commands/serve.py: kiwi serve command (FastAPI + uvicorn + watchdog)
REST API 1:1 với MCP tools, WebSocket real-time events, file watcher auto-check on save
Optional Bearer token auth, OpenAPI docs at /docs, local-only by default
42/42 QA pass, A6 backward compat 77/77 pass, zero regression
Bước 1: audit plan và hoàn thiện plan C0: D:\projects\wezone.claude\kiwi\docs\0-kiwi\C-extension\C0-LSP-UNIVERSAL-SUPPORT.md